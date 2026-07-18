"""Open-Meteo signal — sea state at the tanker chokepoints.

For each chokepoint on India's crude-import routes we read the marine
wave forecast and surface wind. Only *notable* conditions become items
(calm seas are not news), so the feed stays meaningful. Severity is a
deterministic function of wave height and wind speed.

Keyless, free for non-commercial use: https://open-meteo.com/
"""

import asyncio
from dataclasses import dataclass
from datetime import date

import httpx

from vorentice_agents.domain.enums import ImpactCategory, Region, Severity
from vorentice_agents.domain.models import ClassifiedArticle
from vorentice_agents.sources.base import SourceError, USER_AGENT
from vorentice_agents.sources.signals.base import SignalSource, build_signal_item

_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass(frozen=True)
class Chokepoint:
    key: str
    label: str
    lat: float
    lon: float
    region: Region


_CHOKEPOINTS: tuple[Chokepoint, ...] = (
    Chokepoint("hormuz", "Strait of Hormuz", 26.57, 56.25, Region.MIDDLE_EAST),
    Chokepoint("bab_el_mandeb", "Bab el-Mandeb", 12.6, 43.4, Region.MIDDLE_EAST),
    Chokepoint("malacca", "Strait of Malacca", 2.5, 101.3, Region.ASIA_PACIFIC),
    Chokepoint("good_hope", "Cape of Good Hope", -34.35, 18.47, Region.GLOBAL),
)

# Chokepoint.label must match the domain CHOKEPOINTS vocabulary for the
# ones we tag; only Hormuz/Malacca/Cape are in that tuple.
_TAGGABLE = {
    "hormuz": "Strait of Hormuz",
    "malacca": "Strait of Malacca",
    "good_hope": "Cape of Good Hope",
    "bab_el_mandeb": "Bab el-Mandeb",
}


class ChokepointWeatherSignal(SignalSource):
    name = "open-meteo"

    async def fetch(self, client: httpx.AsyncClient) -> list[ClassifiedArticle]:
        results = await asyncio.gather(
            *(self._assess(client, cp) for cp in _CHOKEPOINTS),
            return_exceptions=True,
        )
        items: list[ClassifiedArticle] = []
        errors: list[str] = []
        for cp, result in zip(_CHOKEPOINTS, results):
            if isinstance(result, BaseException):
                errors.append(f"{cp.key}: {result}")
            elif result is not None:
                items.append(result)
        if errors and not items:
            raise SourceError(self.name, "; ".join(errors))
        return items

    async def _assess(
        self, client: httpx.AsyncClient, cp: Chokepoint
    ) -> ClassifiedArticle | None:
        wave, wind = await asyncio.gather(
            self._max_wave(client, cp),
            self._max_wind(client, cp),
        )
        severity = _severity_for_conditions(wave, wind)
        if severity is None:
            return None  # calm — not notable, skip

        parts = []
        if wave is not None:
            parts.append(f"peak wave {wave:.1f} m")
        if wind is not None:
            parts.append(f"wind to {wind:.0f} km/h")
        condition = ", ".join(parts) or "elevated sea state"
        headline = f"Rough seas at {cp.label}: {condition} forecast"
        detail = (
            f"Open-Meteo forecasts {condition} at {cp.label} over the next 24h, "
            f"a level that can slow or reroute tanker transits through this "
            f"chokepoint."
        )
        tag = _TAGGABLE.get(cp.key)
        return build_signal_item(
            source=self.name,
            canonical_id=f"openmeteo://{cp.key}/{date.today().isoformat()}",
            headline=headline,
            detail=detail,
            severity=severity,
            category=ImpactCategory.WEATHER,
            region=cp.region,
            relevance=0.5,
            chokepoints=(tag,) if tag else (),
        )

    async def _max_wave(
        self, client: httpx.AsyncClient, cp: Chokepoint
    ) -> float | None:
        try:
            response = await client.get(
                _MARINE_URL,
                params={
                    "latitude": cp.lat,
                    "longitude": cp.lon,
                    "hourly": "wave_height",
                    "forecast_days": 1,
                },
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            values = response.json().get("hourly", {}).get("wave_height", [])
        except (httpx.HTTPError, ValueError):
            return None
        return _safe_max(values)

    async def _max_wind(
        self, client: httpx.AsyncClient, cp: Chokepoint
    ) -> float | None:
        try:
            response = await client.get(
                _FORECAST_URL,
                params={
                    "latitude": cp.lat,
                    "longitude": cp.lon,
                    "hourly": "wind_speed_10m",
                    "forecast_days": 1,
                },
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            values = response.json().get("hourly", {}).get("wind_speed_10m", [])
        except (httpx.HTTPError, ValueError):
            return None
        return _safe_max(values)


def _safe_max(values: list) -> float | None:
    nums = [v for v in values if isinstance(v, (int, float))]
    return max(nums) if nums else None


def _severity_for_conditions(
    wave: float | None, wind: float | None
) -> Severity | None:
    """Notable-only. Returns None when conditions are unremarkable."""
    wave = wave or 0.0
    wind = wind or 0.0
    if wave >= 6.0 or wind >= 90:
        return Severity.CRITICAL
    if wave >= 4.0 or wind >= 65:
        return Severity.HIGH
    if wave >= 2.5 or wind >= 45:
        return Severity.MEDIUM
    return None
