"""Signal-source contract — structured data folded into the news feed.

An *article* source emits `RawArticle`s that still need the LLM to judge
them. A *signal* source emits `ClassifiedArticle`s directly: the meaning
of a data point (a 3-million-barrel crude draw, a 4-metre wave at Hormuz)
is computable, so severity/category are assigned by deterministic rules
in the adapter — no LLM, no guesswork, exact numbers.

Both kinds converge in the same store and the same feed. A signal item
carries a synthetic canonical URL (`eia://SERIES/PERIOD`) so the normal
dedup machinery stops us re-storing the same data point every cycle.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone

import httpx

from vorentice_agents.domain.enums import ImpactCategory, Region, Severity
from vorentice_agents.domain.models import ClassifiedArticle, RawArticle


class SignalSource(ABC):
    """A source of structured, deterministically-classified intelligence."""

    #: Stable identifier — also the RawArticle.source_name and the key
    #: used by trusted-source alert logic and source-health monitoring.
    name: str

    def is_enabled(self) -> bool:
        """Whether this source is configured (e.g. its API key is set).
        A disabled source is skipped cleanly, never errored."""
        return True

    @abstractmethod
    async def fetch(self, client: httpx.AsyncClient) -> list[ClassifiedArticle]:
        raise NotImplementedError


def build_signal_item(
    *,
    source: str,
    canonical_id: str,
    headline: str,
    detail: str,
    severity: Severity,
    category: ImpactCategory,
    region: Region,
    relevance: float,
    observed_at: datetime | None = None,
    chokepoints: tuple[str, ...] = (),
) -> ClassifiedArticle:
    """Assemble a signal into the same shape as a classified article.

    `canonical_id` must be stable for a given datum (e.g.
    "eia://WCESTUS1/2026-07-03") so re-fetching does not create dupes.
    """
    article = RawArticle(
        url=canonical_id,
        title=headline,
        source_name=source,
        snippet=detail,
        published_at=observed_at,
    )
    return ClassifiedArticle(
        article=article,
        relevance_score=relevance,
        severity=severity,
        impact_category=category,
        region=region,
        chokepoints=chokepoints,
        summary=detail,
        classified_by=f"rule:{source}",
        classified_at=datetime.now(timezone.utc),
    )
