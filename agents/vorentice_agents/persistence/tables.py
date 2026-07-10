"""SQLModel table definitions.

`news_items` — one row per unique classified article (the intel record).
`agent_runs` — one row per pipeline execution (ops accountability: what
ran, how long, what it cost, what failed).

Provenance requirement: every item keeps its source, original URL, raw
snippet, classifier identity and timestamps, so any classification can
be replayed and audited later.
"""

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NewsItemRow(SQLModel, table=True):
    __tablename__ = "news_items"

    id: int | None = Field(default=None, primary_key=True)
    dedup_key: str = Field(index=True, unique=True, max_length=64)

    # ── Provenance ──
    url: str
    title: str
    source_name: str = Field(index=True)
    snippet: str = ""
    language: str = "en"
    published_at: datetime | None = None
    fetched_at: datetime = Field(default_factory=_utcnow)

    # ── Classification ──
    relevance_score: float = Field(index=True)
    severity: str = Field(index=True)
    impact_category: str = Field(index=True)
    region: str = Field(index=True)
    chokepoints: str = ""  # comma-separated; normalized table later if needed
    summary: str = ""
    classified_by: str = ""
    classified_at: datetime | None = None

    # ── Corroboration ──
    # How many independent sightings of this story we've seen (this row
    # plus collapsed near-duplicates). The future alert gate requires
    # corroboration >= 2 (or an official source) before "critical" fires.
    corroboration_count: int = 1
    corroborating_sources: str = ""  # comma-separated source names

    # ── Downstream flags ──
    alert_sent: bool = False


class AlertRow(SQLModel, table=True):
    """An operator alert raised by the AlertPolicy. Delivery transports
    (Azure Service Bus, Teams, email) consume from this table — it is
    the durable record that the alert decision was made and why."""

    __tablename__ = "alerts"

    id: int | None = Field(default=None, primary_key=True)
    news_item_id: int = Field(index=True, foreign_key="news_items.id")
    created_at: datetime = Field(default_factory=_utcnow)
    reason: str = ""
    delivered: bool = False  # flipped by the delivery transport


class AgentRunRow(SQLModel, table=True):
    __tablename__ = "agent_runs"

    id: int | None = Field(default=None, primary_key=True)
    agent: str = Field(default="news", index=True)
    started_at: datetime = Field(default_factory=_utcnow)
    finished_at: datetime | None = None
    ok: bool = True

    fetched: int = 0
    after_dedup: int = 0
    after_prefilter: int = 0
    classified: int = 0
    stored: int = 0
    llm_calls: int = 0
    source_errors: str = ""  # JSON dict of source -> error
