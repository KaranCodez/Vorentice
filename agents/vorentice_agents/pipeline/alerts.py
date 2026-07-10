"""Alert policy — the gate between "classified critical" and "wake someone up".

A CRITICAL item raises an operator alert only when at least one of:
  (a) it is a deterministic SIGNAL from a trusted data source (EIA, FRED,
      Open-Meteo…) — the number speaks for itself;
  (b) it comes from an OFFICIAL government outlet (PIB / MoPNG);
  (c) it is corroborated by >= 2 independent sources.

Everything else — including a lone LLM-classified article, even from a
reputable outlet — waits for corroboration. This is deliberate: LLM
severity on a single headline is the least trustworthy critical signal,
so it must not page anyone on its own. (An earlier version treated the
"EIA Today in Energy" RSS as official and paged on an analytical piece
about *rising* production — exactly the false positive this split fixes.)
"""

from dataclasses import dataclass

from vorentice_agents.domain.enums import Severity
from vorentice_agents.persistence.tables import NewsItemRow

# Deterministic data feeds — their critical is a computed fact, not a guess.
TRUSTED_SIGNAL_SOURCES: frozenset[str] = frozenset(
    {"eia", "fred", "open-meteo", "noaa", "ecmwf", "opensanctions"}
)

# Official government press — a critical statement here is authoritative.
OFFICIAL_OUTLETS: frozenset[str] = frozenset({"pib_mopng"})

MIN_CORROBORATION = 2


class AlertPolicy:
    """Decides whether a stored item warrants an operator alert."""

    def __init__(
        self,
        trusted_signal_sources: frozenset[str] = TRUSTED_SIGNAL_SOURCES,
        official_outlets: frozenset[str] = OFFICIAL_OUTLETS,
        min_corroboration: int = MIN_CORROBORATION,
    ) -> None:
        self._trusted = trusted_signal_sources
        self._official = official_outlets
        self._min_corroboration = min_corroboration

    def should_alert(self, item: NewsItemRow) -> bool:
        if item.severity != Severity.CRITICAL.value or item.alert_sent:
            return False
        if item.source_name in self._trusted:
            return True
        if item.source_name in self._official:
            return True
        return item.corroboration_count >= self._min_corroboration

    def reason(self, item: NewsItemRow) -> str:
        if item.source_name in self._trusted:
            return f"critical signal from trusted data source {item.source_name}"
        if item.source_name in self._official:
            return f"critical from official outlet {item.source_name}"
        return (
            f"critical, corroborated by {item.corroboration_count} sources "
            f"({item.source_name}, {item.corroborating_sources})"
        )


@dataclass(frozen=True)
class ChokepointEvent:
    """A corroborated critical situation at one chokepoint."""

    chokepoint: str
    item_ids: tuple[int, ...]
    sources: tuple[str, ...]
    representative_id: int

    @property
    def reason(self) -> str:
        return (
            f"{self.chokepoint} event — {len(self.item_ids)} critical reports "
            f"across {len(self.sources)} independent sources "
            f"({', '.join(self.sources)})"
        )


class EventCorroborationPolicy:
    """Corroboration by *event*, not by headline wording.

    Different outlets rarely phrase the same crisis alike, so title
    matching misses genuine multi-source events. But the classifier tags
    each item with the chokepoint(s) it implicates very reliably — so we
    corroborate on that: when >= N independent sources file CRITICAL
    reports naming the same chokepoint, that is a real event and pages.

    This is the safety-critical path: for a supply-security system,
    missing a genuine Hormuz crisis is far worse than a redundant page.
    """

    def __init__(self, min_sources: int = 2) -> None:
        self._min_sources = min_sources

    def find_events(self, critical_items: list[NewsItemRow]) -> list[ChokepointEvent]:
        by_chokepoint: dict[str, list[NewsItemRow]] = {}
        for item in critical_items:
            for choke in _chokepoints_of(item):
                by_chokepoint.setdefault(choke, []).append(item)

        events: list[ChokepointEvent] = []
        for choke, items in by_chokepoint.items():
            sources = {i.source_name for i in items}
            if len(sources) < self._min_sources:
                continue
            # Representative = highest-relevance item, for the alert link.
            representative = max(items, key=lambda i: i.relevance_score)
            events.append(
                ChokepointEvent(
                    chokepoint=choke,
                    item_ids=tuple(i.id for i in items if i.id is not None),
                    sources=tuple(sorted(sources)),
                    representative_id=representative.id or 0,
                )
            )
        return events


def _chokepoints_of(item: NewsItemRow) -> list[str]:
    return [c for c in item.chokepoints.split(",") if c]
