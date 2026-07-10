"""API response schemas — the public contract with the dashboard.

Kept separate from DB rows on purpose: table shape can evolve without
breaking the frontend, and no internal fields leak by accident.
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
    relevance_score: float
    severity: str
    impact_category: str
    region: str
    chokepoints: list[str]
    summary: str
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


class AlertOut(BaseModel):
    id: int
    created_at: datetime
    reason: str
    delivered: bool
    item: NewsItemOut


class TriggerResponse(BaseModel):
    status: str
    stats: dict
