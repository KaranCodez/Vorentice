"""OpenSanctions signal — newly sanctioned oil entities & tankers.

Screens the OpenSanctions dataset for petroleum companies and vessels
carrying the "sanction" topic, and emits a signal for those whose record
changed recently (a fresh listing or update). New sanctions on a supplier
or a tanker directly shape crude trade flows and India's sourcing options.

Free tier / key: https://www.opensanctions.org/api/
"""

from datetime import datetime, timedelta, timezone

import httpx

from vorentice_agents.domain.enums import ImpactCategory, Region, Severity
from vorentice_agents.domain.models import ClassifiedArticle
from vorentice_agents.sources.base import SourceError, USER_AGENT
from vorentice_agents.sources.signals.base import SignalSource, build_signal_item

_SEARCH_URL = "https://api.opensanctions.org/search/default"

# (query, schema) pairs — targeted so the feed stays on-mission.
_QUERIES: tuple[tuple[str, str | None], ...] = (
    ("petroleum oil crude refinery", None),
    ("crude oil tanker", "Vessel"),
)


class OpenSanctionsSignal(SignalSource):
    name = "opensanctions"

    def __init__(
        self,
        api_key: str,
        recent_days: int = 3,
        max_items: int = 8,
    ) -> None:
        self._api_key = api_key
        self._recent_days = recent_days
        self._max_items = max_items

    def is_enabled(self) -> bool:
        return bool(self._api_key)

    async def fetch(self, client: httpx.AsyncClient) -> list[ClassifiedArticle]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._recent_days)
        headers = {
            "Authorization": f"ApiKey {self._api_key}",
            "User-Agent": USER_AGENT,
        }

        by_id: dict[str, ClassifiedArticle] = {}
        errors: list[str] = []
        for query, schema in _QUERIES:
            params = {"q": query, "topics": "sanction", "limit": 25}
            if schema:
                params["schema"] = schema
            try:
                response = await client.get(_SEARCH_URL, params=params, headers=headers)
                response.raise_for_status()
                results = response.json().get("results", [])
            except httpx.HTTPError as exc:
                errors.append(f"{query!r}: {exc}")
                continue
            except ValueError as exc:
                errors.append(f"{query!r}: bad JSON {exc}")
                continue

            for entity in results:
                item = self._to_item(entity, cutoff)
                if item is not None:
                    by_id.setdefault(entity.get("id", ""), item)

        if errors and not by_id:
            raise SourceError(self.name, "; ".join(errors))

        # Most-recent changes first, capped to keep the feed proportionate.
        items = sorted(
            by_id.values(),
            key=lambda i: i.article.published_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return items[: self._max_items]

    def _to_item(self, entity: dict, cutoff: datetime) -> ClassifiedArticle | None:
        entity_id = entity.get("id")
        caption = (entity.get("caption") or "").strip()
        if not entity_id or not caption:
            return None

        changed = _parse_dt(entity.get("last_change"))
        if changed is None or changed < cutoff:
            return None  # not a recent change — nothing new to report

        schema = entity.get("schema", "Entity")
        datasets = ", ".join((entity.get("datasets") or [])[:3]) or "sanctions lists"
        kind = "tanker" if schema == "Vessel" else "entity"
        headline = f"OpenSanctions: {kind} '{caption}' newly listed/updated"
        detail = (
            f"{caption} ({schema}) appears on {datasets} with a record change on "
            f"{changed.date().isoformat()}. New sanctions on oil-sector "
            f"{kind}s reshape trade flows and India's sourcing options."
        )
        severity = Severity.HIGH if schema == "Vessel" else Severity.MEDIUM
        return build_signal_item(
            source=self.name,
            canonical_id=f"opensanctions://{entity_id}/{changed.date().isoformat()}",
            headline=headline,
            detail=detail,
            severity=severity,
            category=ImpactCategory.SANCTIONS,
            region=_region_of(entity),
            relevance=0.55,
            observed_at=changed,
        )


def _parse_dt(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _region_of(entity: dict) -> Region:
    countries = (entity.get("properties", {}) or {}).get("country", [])
    codes = {c.lower() for c in countries if isinstance(c, str)}
    if "in" in codes:
        return Region.INDIA
    if codes & {"ir", "iq", "sa", "ae", "kw", "qa"}:
        return Region.MIDDLE_EAST
    if codes & {"ru", "by"}:
        return Region.RUSSIA_CIS
    if codes & {"ve"}:
        return Region.SOUTH_AMERICA
    if codes & {"ng", "ao"}:
        return Region.WEST_AFRICA
    return Region.GLOBAL
