"""Domain models flowing through the News Agent pipeline.

`RawArticle`   — what source adapters emit (normalized, unclassified).
`ClassifiedArticle` — a RawArticle enriched by the classification stage.

Both are immutable: pipeline stages produce new objects rather than
mutating shared state, which keeps LangGraph state transitions auditable.
"""

import hashlib
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

from vorentice_agents.domain.enums import ImpactCategory, Region, Severity


class RawArticle(BaseModel):
    """A normalized article as emitted by any `NewsSource` adapter."""

    model_config = ConfigDict(frozen=True)

    url: str
    title: str
    source_name: str
    published_at: datetime | None = None
    snippet: str = ""
    language: str = "en"

    @field_validator("title", "snippet", mode="before")
    @classmethod
    def _clean_text(cls, value: object) -> str:
        if value is None:
            return ""
        return " ".join(str(value).split())

    @property
    def dedup_key(self) -> str:
        """Stable identity for exact deduplication.

        URL is canonicalized (scheme/host lowercased, trailing slash and
        common tracking params stripped) so syndicated re-posts of the
        same link hash identically.
        """
        return hashlib.sha256(_canonicalize_url(self.url).encode()).hexdigest()


class ClassifiedArticle(BaseModel):
    """A RawArticle after LLM (or heuristic) enrichment."""

    model_config = ConfigDict(frozen=True)

    article: RawArticle
    # Internal LLM-budget gate only — NEVER surfaced to users; the report
    # speaks exclusively in qualitative criticality descriptors.
    relevance_score: float = Field(ge=0.0, le=1.0)
    severity: Severity
    impact_category: ImpactCategory
    region: Region
    chokepoints: tuple[str, ...] = ()
    summary: str
    # How this event affects global trade and logistics right now
    # (Section 2 of the intelligence report requires it per event).
    trade_impact: str = ""
    # Watchlist fields (Section 3): a non-critical event that could
    # escalate is flagged here, with the reasoning and the tripwires.
    escalation_potential: bool = False
    watchlist_reason: str = ""
    escalation_triggers: str = ""
    classified_by: str  # model deployment name, or "heuristic"
    classified_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


def _canonicalize_url(url: str) -> str:
    """Normalize a URL for deduplication purposes."""
    from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

    parsed = urlparse(url.strip())
    # Drop tracking parameters that vary across syndication.
    tracking = {"utm_source", "utm_medium", "utm_campaign", "utm_term",
                "utm_content", "fbclid", "gclid", "ref"}
    query = [(k, v) for k, v in parse_qsl(parsed.query) if k not in tracking]
    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path.rstrip("/"),
        parsed.params,
        urlencode(query),
        "",  # fragment never affects identity
    ))
