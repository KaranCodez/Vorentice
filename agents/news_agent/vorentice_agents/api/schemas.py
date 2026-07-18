"""API response schemas — the public contract with the dashboard.

Kept separate from DB rows on purpose: table shape can evolve without
breaking the frontend, and no internal fields leak by accident.

Charter rule enforced at this boundary: NO numerical risk/relevance
scores ever leave the API. Urgency is always a qualitative descriptor
(Critical, High, Moderate, Low, Emerging).
"""

from datetime import datetime

from pydantic import BaseModel


class NewsItemOut(BaseModel):
    id: int
    url: str
    title: str
    source_name: str
    published_at: datetime | None
    fetched_at: datetime
    severity: str
    criticality: str            # qualitative descriptor, incl. "Emerging"
    impact_category: str
    region: str
    chokepoints: list[str]
    summary: str
    trade_impact: str
    escalation_potential: bool
    watchlist_reason: str
    escalation_triggers: str
    corroboration_count: int
    corroborating_sources: list[str]


class AgentRunOut(BaseModel):
    id: int
    started_at: datetime
    finished_at: datetime | None
    ok: bool
    fetched: int
    after_dedup: int
    after_prefilter: int
    classified: int
    stored: int
    llm_calls: int


class SegmentBriefingOut(BaseModel):
    """One monitored segment's slice of the operator briefing.

    No numeric risk score by design — criticality is expressed as the
    severity level on each event; risk percentages are the Risk Agent's
    job downstream."""

    segment: str
    label: str
    counts: dict[str, int]      # severity -> item count in the window
    events: list[NewsItemOut]   # most critical developments, all of them


# ── The three-section intelligence report ────────────────────────────


class CategoryBriefOut(BaseModel):
    """Section 1 (Daily Brief): one category's narrative roundup plus
    every underlying headline — the complete newspaper replacement.
    All 8 monitored categories are always present, quiet ones included."""

    segment: str
    label: str
    digest: str
    item_count: int
    digest_generated_at: datetime | None
    counts: dict[str, int]        # severity -> item count in the window
    headlines: list[NewsItemOut]  # every item this window, newest first


class CriticalEventOut(BaseModel):
    """Section 2 (Critical Events Tracker): one significant disruptive
    event, in the charter's exact shape — category, what happened, how
    urgent, and what it does to global trade right now."""

    category: str                 # human label of the segment
    segment: str
    event_summary: str
    criticality: str              # "Critical" / "High" — never a number
    trade_impact: str
    region: str
    chokepoints: list[str]
    sources: list[str]            # reporting + corroborating outlets
    url: str
    reported_at: datetime | None


class WatchlistEntryOut(BaseModel):
    """Section 3 (Emerging Threats): not critical today, but could
    escalate — with the why and the concrete tripwires."""

    category: str
    segment: str
    summary: str
    criticality: str              # "Emerging"
    watchlist_reason: str
    escalation_triggers: str
    region: str
    url: str
    reported_at: datetime | None


class IntelligenceReportOut(BaseModel):
    """The full report: Daily Brief, Critical Events Tracker, Emerging
    Threats watchlist. This is the product's primary output."""

    generated_at: datetime
    window_hours: int
    daily_brief: list[CategoryBriefOut]       # all 8 categories, always
    critical_events: list[CriticalEventOut]   # ALL of them, worst first
    watchlist: list[WatchlistEntryOut]


class AlertOut(BaseModel):
    id: int
    created_at: datetime
    reason: str
    delivered: bool
    item: NewsItemOut


class TriggerResponse(BaseModel):
    status: str
    stats: dict
