"""EIA signal — U.S. weekly crude oil stocks.

Series WCESTUS1 (commercial crude excluding the SPR, thousand barrels).
The week-over-week change is the signal: a large *draw* points to a
tightening global balance (supply risk, price pressure); a large *build*
points to ample supply. Severity is a deterministic function of the
change magnitude and direction — no LLM involved.

Free API key: https://www.eia.gov/opendata/register.php
"""

from datetime import datetime, timezone

import httpx

from vorentice_agents.domain.enums import ImpactCategory, Region, Severity
from vorentice_agents.domain.models import ClassifiedArticle
from vorentice_agents.sources.base import SourceError, USER_AGENT
from vorentice_agents.sources.signals.base import SignalSource, build_signal_item

_EIA_URL = "https://api.eia.gov/v2/petroleum/stoc/wstk/data/"
_SERIES = "WCESTUS1"  # weekly ending stocks, crude excl. SPR (thousand bbl)


class EiaCrudeStocksSignal(SignalSource):
    name = "eia"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def is_enabled(self) -> bool:
        return bool(self._api_key)

    async def fetch(self, client: httpx.AsyncClient) -> list[ClassifiedArticle]:
        try:
            response = await client.get(
                _EIA_URL,
                params={
                    "api_key": self._api_key,
                    "frequency": "weekly",
                    "data[0]": "value",
                    "facets[series][]": _SERIES,
                    "sort[0][column]": "period",
                    "sort[0][direction]": "desc",
                    "length": "2",
                },
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            rows = response.json().get("response", {}).get("data", [])
        except httpx.HTTPError as exc:
            raise SourceError(self.name, str(exc)) from exc
        except (ValueError, KeyError) as exc:
            raise SourceError(self.name, f"unexpected payload: {exc}") from exc

        if len(rows) < 2:
            return []

        latest, prior = rows[0], rows[1]
        try:
            current = float(latest["value"])
            previous = float(prior["value"])
        except (TypeError, ValueError, KeyError):
            return []

        change = current - previous  # thousand barrels
        period = latest.get("period", "")
        severity = _severity_for_change(change)
        direction = "drew down" if change < 0 else "built"
        headline = (
            f"EIA: U.S. crude stocks {direction} "
            f"{abs(change) / 1000:.1f}M bbl to {current / 1000:.1f}M "
            f"(week of {period})"
        )
        detail = (
            f"U.S. commercial crude inventories (excl. SPR) changed by "
            f"{change / 1000:+.1f} million barrels week-over-week to "
            f"{current / 1000:.1f} million barrels. A sustained draw signals "
            f"a tightening supply balance relevant to import-dependent buyers."
        )
        return [
            build_signal_item(
                source=self.name,
                canonical_id=f"eia://{_SERIES}/{period}",
                headline=headline,
                detail=detail,
                severity=severity,
                category=ImpactCategory.SUPPLY_DISRUPTION,
                region=Region.NORTH_AMERICA,
                relevance=0.65,
                observed_at=_parse_period(period),
            )
        ]


def _severity_for_change(change_kbbl: float) -> Severity:
    """Draws (negative) are the supply-risk direction and rank higher."""
    millions = change_kbbl / 1000.0
    if millions <= -10:
        return Severity.HIGH
    if millions <= -5:
        return Severity.MEDIUM
    if abs(millions) < 5:
        return Severity.LOW
    return Severity.LOW  # a large build is reassuring, not alarming


def _parse_period(period: str) -> datetime | None:
    try:
        return datetime.strptime(period, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
