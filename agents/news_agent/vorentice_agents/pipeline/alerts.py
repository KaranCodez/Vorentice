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
class CriticalEvent:
    """A corroborated critical situation — in ANY monitored segment."""

    label: str  # e.g. "Strait of Hormuz" or "Wars & Geopolitical Conflicts · middle_east"
    item_ids: tuple[int, ...]
    sources: tuple[str, ...]
    representative_id: int

    @property
    def reason(self) -> str:
        return (
            f"{self.label} event — {len(self.item_ids)} critical reports "
            f"across {len(self.sources)} independent sources "
            f"({', '.join(self.sources)})"
        )


class EventCorroborationPolicy:
    """Corroboration by *event*, not by headline wording.

    Different outlets rarely phrase the same crisis alike, so title
    matching misses genuine multi-source events. Instead we group the
    open critical items by what they are about and page when >= N
    independent sources report the same thing:

    - sharpest key: a named chokepoint, when the classifier tagged one;
    - otherwise: the (segment, region) pair — so a war escalation, a
      port shutdown, or a cyclone corroborated across outlets pages
      exactly like a chokepoint crisis does.

    EVERY corroborated event is emitted — a war, a supply disruption and
    two port closures happening at once produce four distinct alerts,
    per the charter: comprehensive view, not a single headline event.
    Missing a genuine crisis is far worse than a redundant page.
    """

    def __init__(self, min_sources: int = 2) -> None:
        self._min_sources = min_sources

    def find_events(self, critical_items: list[NewsItemRow]) -> list[CriticalEvent]:
        from vorentice_agents.domain.enums import SEGMENT_LABELS, segment_of

        by_key: dict[str, list[NewsItemRow]] = {}
        for item in critical_items:
            chokes = _chokepoints_of(item)
            if chokes:
                for choke in chokes:
                    by_key.setdefault(choke, []).append(item)
            else:
                segment = segment_of(item.impact_category)
                label = f"{SEGMENT_LABELS[segment]} · {item.region}"
                by_key.setdefault(label, []).append(item)

        events: list[CriticalEvent] = []
        claimed: set[int] = set()  # an item feeds at most one event
        for label, items in by_key.items():
            fresh = [i for i in items if i.id not in claimed]
            sources = {i.source_name for i in fresh}
            if len(sources) < self._min_sources:
                continue
            # Representative = highest-relevance item, for the alert link.
            representative = max(fresh, key=lambda i: i.relevance_score)
            events.append(
                CriticalEvent(
                    label=label,
                    item_ids=tuple(i.id for i in fresh if i.id is not None),
                    sources=tuple(sorted(sources)),
                    representative_id=representative.id or 0,
                )
            )
            claimed.update(i.id for i in fresh if i.id is not None)
        return events


def _chokepoints_of(item: NewsItemRow) -> list[str]:
    return [c for c in item.chokepoints.split(",") if c]
