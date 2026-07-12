"""HTTP surface of the News Agent.

GET  /health          — liveness probe (Azure Container Apps).
GET  /news/latest     — most recent classified items, filterable.
GET  /news/stream     — Server-Sent Events; pushes items as they land.
GET  /news/runs       — recent pipeline runs (ops visibility).
POST /news/trigger    — run the pipeline now (manual/testing).
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Query, Request
from sse_starlette.sse import EventSourceResponse

from vorentice_agents.api.schemas import (
    AgentRunOut,
    AlertOut,
    NewsItemOut,
    SegmentBriefingOut,
    TriggerResponse,
)
from vorentice_agents.domain.enums import (
    SEGMENT_LABELS,
    SEVERITY_ORDER,
    NewsSegment,
    segment_of,
)
from vorentice_agents.persistence.repository import NewsRepository
from vorentice_agents.persistence.tables import NewsItemRow

logger = logging.getLogger(__name__)

router = APIRouter()

_STREAM_POLL_SECONDS = 5.0


def _to_out(row: NewsItemRow) -> NewsItemOut:
    return NewsItemOut(
        id=row.id or 0,
        url=row.url,
        title=row.title,
        source_name=row.source_name,
        published_at=row.published_at,
        fetched_at=row.fetched_at,
        relevance_score=row.relevance_score,
        severity=row.severity,
        impact_category=row.impact_category,
        region=row.region,
        chokepoints=[c for c in row.chokepoints.split(",") if c],
        summary=row.summary,
        corroboration_count=row.corroboration_count,
        corroborating_sources=[
            s for s in row.corroborating_sources.split(",") if s
        ],
    )


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "agent": "news"}


@router.get("/news/latest", response_model=list[NewsItemOut])
async def latest(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    min_relevance: float = Query(default=0.0, ge=0.0, le=1.0),
    severity: str | None = Query(default=None),
) -> list[NewsItemOut]:
    repository: NewsRepository = request.app.state.repository
    rows = repository.latest_items(
        limit=limit, min_relevance=min_relevance, severity=severity
    )
    return [_to_out(row) for row in rows]


@router.get("/news/runs", response_model=list[AgentRunOut])
async def runs(request: Request) -> list[AgentRunOut]:
    repository: NewsRepository = request.app.state.repository
    return [
        AgentRunOut(
            id=row.id or 0,
            started_at=row.started_at,
            finished_at=row.finished_at,
            ok=row.ok,
            fetched=row.fetched,
            after_dedup=row.after_dedup,
            after_prefilter=row.after_prefilter,
            classified=row.classified,
            stored=row.stored,
            llm_calls=row.llm_calls,
        )
        for row in repository.recent_runs()
    ]


@router.get("/news/briefing", response_model=list[SegmentBriefingOut])
async def briefing(
    request: Request,
    hours: int = Query(default=24, ge=1, le=168),
    min_severity: str = Query(default="high"),
) -> list[SegmentBriefingOut]:
    """The operator briefing: latest developments grouped by monitored
    segment (energy, weather, sanctions, ports, routes, war, security).

    Every significant event in every segment is surfaced with its
    criticality level — 2 war criticals + 3 severe weather events + 2
    port closures = 7 entries across 3 segments, not one headline item.
    """
    repository: NewsRepository = request.app.state.repository
    floor = SEVERITY_ORDER.get(min_severity, SEVERITY_ORDER["high"])

    grouped: dict[NewsSegment, list[NewsItemRow]] = {}
    counts: dict[NewsSegment, dict[str, int]] = {}
    for row in repository.briefing_items(hours=hours):
        segment = segment_of(row.impact_category)
        counts.setdefault(segment, {})[row.severity] = (
            counts.setdefault(segment, {}).get(row.severity, 0) + 1
        )
        if SEVERITY_ORDER.get(row.severity, 0) >= floor:
            grouped.setdefault(segment, []).append(row)

    briefing_out: list[SegmentBriefingOut] = []
    for segment in NewsSegment:
        events = grouped.get(segment, [])
        if not events and segment not in counts:
            continue  # nothing at all in this segment this window
        events.sort(
            key=lambda r: (SEVERITY_ORDER.get(r.severity, 0), r.fetched_at),
            reverse=True,
        )
        briefing_out.append(
            SegmentBriefingOut(
                segment=segment.value,
                label=SEGMENT_LABELS[segment],
                counts=counts.get(segment, {}),
                events=[_to_out(row) for row in events],
            )
        )
    # Hottest segments first: by their single most severe event, then volume.
    briefing_out.sort(
        key=lambda s: (
            max(
                (SEVERITY_ORDER.get(e.severity, 0) for e in s.events),
                default=-1,
            ),
            sum(s.counts.values()),
        ),
        reverse=True,
    )
    return briefing_out


@router.get("/news/sources")
async def sources(request: Request) -> list[dict]:
    """Per-source ingestion health for operators."""
    repository: NewsRepository = request.app.state.repository
    return repository.source_health()


@router.get("/news/alerts", response_model=list[AlertOut])
async def alerts(request: Request) -> list[AlertOut]:
    repository: NewsRepository = request.app.state.repository
    return [
        AlertOut(
            id=alert.id or 0,
            created_at=alert.created_at,
            reason=alert.reason,
            delivered=alert.delivered,
            item=_to_out(item),
        )
        for alert, item in repository.recent_alerts()
    ]


@router.post("/news/trigger", response_model=TriggerResponse)
async def trigger(request: Request) -> TriggerResponse:
    agent = request.app.state.news_agent
    stats = await agent.run()
    return TriggerResponse(status="completed", stats=dict(stats))


@router.get("/news/stream")
async def stream(request: Request) -> EventSourceResponse:
    """SSE stream of newly stored items. The dashboard subscribes once
    and receives each new intelligence item as a `news` event."""
    repository: NewsRepository = request.app.state.repository

    async def event_source():
        # Start from the current head so clients only get NEW items.
        last = repository.latest_items(limit=1)
        last_id = last[0].id or 0 if last else 0

        while True:
            if await request.is_disconnected():
                break
            fresh = repository.items_since(last_id)
            for row in fresh:
                last_id = max(last_id, row.id or 0)
                yield {
                    "event": "news",
                    "id": str(row.id),
                    "data": _to_out(row).model_dump_json(),
                }
            await asyncio.sleep(_STREAM_POLL_SECONDS)

    return EventSourceResponse(event_source())
