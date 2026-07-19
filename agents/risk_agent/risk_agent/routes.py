"""Risk Agent HTTP routes.

GET  /health          — liveness probe
POST /risk/init       — coordinate with News Agent, ingest section, run the
                        agent to produce the opening threat briefing
POST /risk/chat       — streaming interactive risk QA
"""

import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from risk_agent.chat_engine import (
    fetch_news_report,
    extract_critical_events,
    extract_watchlist,
)
from risk_agent.stat_context import fetch_stat_bundle, stat_bundle_to_context

logger = logging.getLogger(__name__)
router = APIRouter()


class InitRequest(BaseModel):
    mode: str  # "critical_events" | "emerging_threats"
    hours: int = 24


class InitResponse(BaseModel):
    mode: str
    payload: str
    event_count: int
    risk_score: int
    risk_label: str
    executive_synthesis: str
    threat_profile_md: str
    followups: list[str]


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    mode: str
    payload: str
    messages: list[ChatMessage] = []
    message: str


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "agent": "risk"}


@router.post("/risk/init", response_model=InitResponse)
async def init_session(request: Request, body: InitRequest) -> InitResponse:
    """Coordinate with the News Agent, ingest the requested section, and run
    the Risk Agent to produce a real aggregated threat briefing."""
    engine = request.app.state.chat_engine
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="Risk Agent LLM is not configured. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY.",
        )

    try:
        report = await fetch_news_report(hours=body.hours)
    except Exception as exc:
        logger.warning("News Agent unreachable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="News Agent is not reachable. Make sure it is running on port 8000.",
        )

    if body.mode == "critical_events":
        payload = extract_critical_events(report)
        count = len(report.get("critical_events", []))
    elif body.mode == "emerging_threats":
        payload = extract_watchlist(report)
        count = len(report.get("watchlist", []))
    else:
        raise HTTPException(
            status_code=400,
            detail="mode must be 'critical_events' or 'emerging_threats'",
        )

    # Append live statistical context so the LLM reasons from real numbers.
    try:
        stat_bundle = await fetch_stat_bundle(
            fred_api_key=request.app.state.fred_api_key,
            eia_api_key=request.app.state.eia_api_key,
        )
        payload = payload + "\n\n" + stat_bundle_to_context(stat_bundle)
        logger.info(
            "Stat bundle appended: brent=%s wti=%s inr=%s",
            stat_bundle.brent_usd,
            stat_bundle.wti_usd,
            stat_bundle.inr_per_usd,
        )
    except Exception as exc:
        logger.warning("Stat bundle fetch failed (continuing without): %s", exc)

    try:
        briefing = await engine.generate_briefing(payload, body.mode)
    except Exception as exc:
        logger.exception("briefing generation failed")
        raise HTTPException(status_code=502, detail=f"Agent briefing failed: {exc}")

    return InitResponse(
        mode=body.mode,
        payload=payload,
        event_count=count,
        risk_score=briefing["risk_score"],
        risk_label=briefing["risk_label"],
        executive_synthesis=briefing["executive_synthesis"],
        threat_profile_md=briefing["threat_profile_md"],
        followups=briefing["followups"],
    )


@router.post("/risk/chat")
async def chat(request: Request, body: ChatRequest):
    """Stream a risk analysis response from Azure OpenAI."""
    engine = request.app.state.chat_engine
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="Risk Agent LLM is not configured.",
        )

    async def stream_tokens():
        try:
            async for token in engine.chat(
                payload=body.payload,
                messages=[m.model_dump() for m in body.messages],
                user_message=body.message,
            ):
                yield token
        except Exception as exc:
            logger.exception("Risk chat stream error")
            yield f"\n\n[Error: {exc}]"

    return StreamingResponse(stream_tokens(), media_type="text/plain; charset=utf-8")
