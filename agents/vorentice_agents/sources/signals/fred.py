"""FRED signal — crude oil spot prices (Brent & WTI).

Brent (DCOILBRENTEU) is the benchmark most relevant to Indian imports;
WTI (DCOILWTICO) is the US marker. The signal is the recent price move:
a sharp spike or crash is a price_movement event. Severity scales with
the magnitude of the change — deterministically, from the numbers.

Free API key: https://fredaccount.stlouisfed.org/apikeys
"""

import httpx

from vorentice_agents.domain.enums import ImpactCategory, Region, Severity
from vorentice_agents.domain.models import ClassifiedArticle
from vorentice_agents.sources.base import SourceError, USER_AGENT
from vorentice_agents.sources.signals.base import SignalSource, build_signal_item

_FRED_URL = "https://api.stlouisfed.org/fred/series/observations"

# series_id -> (human label, region relevance weight)
_SERIES = {
    "DCOILBRENTEU": "Brent crude",
    "DCOILWTICO": "WTI crude",
}


class FredOilPriceSignal(SignalSource):
    name = "fred"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def is_enabled(self) -> bool:
        return bool(self._api_key)

    async def fetch(self, client: httpx.AsyncClient) -> list[ClassifiedArticle]:
        items: list[ClassifiedArticle] = []
        errors: list[str] = []
        for series_id, label in _SERIES.items():
            try:
                item = await self._fetch_series(client, series_id, label)
                if item is not None:
                    items.append(item)
            except httpx.HTTPError as exc:
                errors.append(f"{series_id}: {exc}")
        if errors and not items:
            raise SourceError(self.name, "; ".join(errors))
        return items

    async def _fetch_series(
        self, client: httpx.AsyncClient, series_id: str, label: str
    ) -> ClassifiedArticle | None:
        response = await client.get(
            _FRED_URL,
            params={
                "series_id": series_id,
                "api_key": self._api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": "10",
            },
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        observations = response.json().get("observations", [])

        # FRED encodes missing values (holidays) as ".". Keep real prints.
        valid = [
            (obs["date"], float(obs["value"]))
            for obs in observations
            if obs.get("value") not in (".", None, "")
        ]
        if len(valid) < 2:
            return None

        (latest_date, latest_price), (_, prior_price) = valid[0], valid[1]
        pct = (latest_price - prior_price) / prior_price * 100 if prior_price else 0.0
        severity = _severity_for_move(pct)
        direction = "jumped" if pct > 0 else "fell"
        headline = (
            f"{label} {direction} {abs(pct):.1f}% to ${latest_price:.2f}/bbl "
            f"({latest_date})"
        )
        detail = (
            f"{label} spot settled at ${latest_price:.2f}/bbl on {latest_date}, "
            f"a {pct:+.1f}% move from the prior session (${prior_price:.2f}). "
            f"Sharp moves in the Brent/WTI complex feed directly into India's "
            f"import bill and retail fuel pricing."
        )
        return build_signal_item(
            source=self.name,
            canonical_id=f"fred://{series_id}/{latest_date}",
            headline=headline,
            detail=detail,
            severity=severity,
            category=ImpactCategory.PRICE_MOVEMENT,
            region=Region.GLOBAL,
            relevance=0.7,
        )


def _severity_for_move(pct: float) -> Severity:
    magnitude = abs(pct)
    if magnitude >= 10:
        return Severity.HIGH
    if magnitude >= 5:
        return Severity.MEDIUM
    return Severity.LOW
