"""Statistical context builder — fetches a live StatBundle at session init.

Injected as [LIVE MARKET DATA] into the LLM context so the agent reasons
from real current numbers, not the hardcoded estimates in the system prompt.

Sources:
  FRED API   — Brent/WTI spot prices; USD/INR exchange rate
  EIA API    — U.S. crude weekly inventory draw/build
  World Bank — India net energy imports as % of energy use (no key, annual)
"""

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
_EIA_STOCKS_URL = "https://api.eia.gov/v2/petroleum/stoc/wstk/data/"
_WB_URL = "https://api.worldbank.org/v2/country/IND/indicator/{indicator}"


class StatBundle(BaseModel):
    brent_usd: float | None = None
    brent_date: str | None = None
    brent_pct_1d: float | None = None

    wti_usd: float | None = None
    wti_date: str | None = None
    wti_pct_1d: float | None = None

    inr_per_usd: float | None = None
    inr_date: str | None = None

    us_crude_stocks_mmbbl: float | None = None
    us_crude_draw_mmbbl: float | None = None  # negative = draw (supply tightening)
    us_crude_week: str | None = None

    india_energy_import_pct: float | None = None  # % of energy use that is imported
    india_energy_import_year: int | None = None

    fetched_at: datetime


async def _fred_two(
    client: httpx.AsyncClient, api_key: str, series_id: str
) -> tuple[tuple[str, float], tuple[str, float]] | None:
    if not api_key:
        return None
    try:
        resp = await client.get(
            _FRED_URL,
            params={
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": "10",
            },
        )
        resp.raise_for_status()
        valid = [
            (obs["date"], float(obs["value"]))
            for obs in resp.json().get("observations", [])
            if obs.get("value") not in (".", None, "")
        ]
        return (valid[0], valid[1]) if len(valid) >= 2 else None
    except Exception as exc:
        logger.debug("FRED %s: %s", series_id, exc)
        return None


async def _eia_stocks(
    client: httpx.AsyncClient, api_key: str
) -> tuple[float, float, str] | None:
    if not api_key:
        return None
    try:
        resp = await client.get(
            _EIA_STOCKS_URL,
            params={
                "api_key": api_key,
                "frequency": "weekly",
                "data[0]": "value",
                "facets[series][]": "WCESTUS1",
                "sort[0][column]": "period",
                "sort[0][direction]": "desc",
                "length": "2",
            },
        )
        resp.raise_for_status()
        rows = resp.json().get("response", {}).get("data", [])
        if len(rows) < 2:
            return None
        cur = float(rows[0]["value"]) / 1000.0   # thousand bbl → MMbbl
        prev = float(rows[1]["value"]) / 1000.0
        return cur, cur - prev, rows[0].get("period", "")
    except Exception as exc:
        logger.debug("EIA stocks: %s", exc)
        return None


async def _wb_india_energy_import(
    client: httpx.AsyncClient,
) -> tuple[float, int] | None:
    """India net energy imports as % of energy use (World Bank EG.IMP.CONS.ZS)."""
    try:
        resp = await client.get(
            _WB_URL.format(indicator="EG.IMP.CONS.ZS"),
            params={"format": "json", "mrv": "5"},
        )
        resp.raise_for_status()
        payload = resp.json()
        if len(payload) < 2:
            return None
        for obs in payload[1]:
            val = obs.get("value")
            if val is not None:
                return float(val), int(obs["date"])
        return None
    except Exception as exc:
        logger.debug("World Bank energy import: %s", exc)
        return None


async def fetch_stat_bundle(fred_api_key: str, eia_api_key: str) -> StatBundle:
    """Fetch all metrics concurrently. Individual source failures leave
    those fields as None — the bundle is always returned."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        brent_r, wti_r, inr_r, eia_r, wb_r = await asyncio.gather(
            _fred_two(client, fred_api_key, "DCOILBRENTEU"),
            _fred_two(client, fred_api_key, "DCOILWTICO"),
            _fred_two(client, fred_api_key, "DEXINUS"),
            _eia_stocks(client, eia_api_key),
            _wb_india_energy_import(client),
            return_exceptions=True,
        )

    bundle = StatBundle(fetched_at=datetime.now(timezone.utc))

    def _ok(r: object):
        return r if r is not None and not isinstance(r, Exception) else None

    if b := _ok(brent_r):
        (d, p), (_, pp) = b
        bundle.brent_usd = p
        bundle.brent_date = d
        bundle.brent_pct_1d = round((p - pp) / pp * 100, 2) if pp else None

    if w := _ok(wti_r):
        (d, p), (_, pp) = w
        bundle.wti_usd = p
        bundle.wti_date = d
        bundle.wti_pct_1d = round((p - pp) / pp * 100, 2) if pp else None

    if i := _ok(inr_r):
        (d, rate), _ = i
        bundle.inr_per_usd = rate
        bundle.inr_date = d

    if e := _ok(eia_r):
        cur, draw, week = e
        bundle.us_crude_stocks_mmbbl = round(cur, 1)
        bundle.us_crude_draw_mmbbl = round(draw, 1)
        bundle.us_crude_week = week

    if wb := _ok(wb_r):
        pct, yr = wb
        bundle.india_energy_import_pct = round(pct, 1)
        bundle.india_energy_import_year = yr

    return bundle


def stat_bundle_to_context(bundle: StatBundle) -> str:
    """Render the StatBundle as a markdown block for LLM context injection."""
    as_of = bundle.fetched_at.strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"[LIVE MARKET DATA - fetched {as_of}]",
        "",
        "| Metric | Live Value | Source |",
        "|--------|-----------|--------|",
    ]

    if bundle.brent_usd is not None:
        chg = bundle.brent_pct_1d
        pct = f" ({'+' if (chg or 0) > 0 else ''}{chg:.1f}% day-on-day)" if chg is not None else ""
        lines.append(
            f"| Brent crude spot | **${bundle.brent_usd:.2f}/bbl**{pct} ({bundle.brent_date}) | FRED |"
        )

    if bundle.wti_usd is not None:
        chg = bundle.wti_pct_1d
        pct = f" ({'+' if (chg or 0) > 0 else ''}{chg:.1f}% day-on-day)" if chg is not None else ""
        lines.append(
            f"| WTI crude spot | **${bundle.wti_usd:.2f}/bbl**{pct} ({bundle.wti_date}) | FRED |"
        )

    if bundle.brent_usd is not None:
        basket = bundle.brent_usd - 3.0
        lines.append(
            f"| India crude basket (approx.) | **~${basket:.1f}/bbl** (Brent - $3 sour-grade discount) | Derived |"
        )

    if bundle.inr_per_usd is not None:
        lines.append(
            f"| USD/INR rate | **INR {bundle.inr_per_usd:.2f} per USD** ({bundle.inr_date}) | FRED |"
        )

    if bundle.us_crude_stocks_mmbbl is not None:
        draw = bundle.us_crude_draw_mmbbl or 0
        direction = "draw (supply tightening)" if draw < 0 else "build (supply loosening)"
        lines.append(
            f"| U.S. crude stocks (ex-SPR) | **{bundle.us_crude_stocks_mmbbl:.1f} MMbbl** "
            f"({direction} {draw:+.1f} MMbbl, week of {bundle.us_crude_week}) | EIA |"
        )

    if bundle.india_energy_import_pct is not None:
        lines.append(
            f"| India net energy imports | **{bundle.india_energy_import_pct:.1f}% of energy use** "
            f"({bundle.india_energy_import_year}) | World Bank |"
        )

    lines += [
        "",
        "> **Calculation mandate:** Use these live figures for all price, currency, and",
        "> supply-balance calculations this session. Do not substitute training-data estimates",
        "> for any metric listed above. India crude basket ~ Brent - $2 to $4/bbl.",
    ]

    return "\n".join(lines)
