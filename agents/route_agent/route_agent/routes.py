"""Route Agent HTTP routes.

GET  /health           — liveness probe
GET  /route/topology   — the full network graph + baseline corridor (render once)
GET  /route/live       — Live Mode: pull News-Agent disruptions, reroute, impact
POST /route/simulate   — Sandbox Mode: reroute against manually-toggled nodes
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from route_agent.classification import (
    Disruption,
    classify_live_events,
    classify_manual,
)
from route_agent.engine import build_topology, run_pipeline
from route_agent.graph_data import NODES
from route_agent.market import fetch_brent_usd
from route_agent.news_client import fetch_critical_events

logger = logging.getLogger(__name__)
router = APIRouter()

_VALID_STATUS = {"blocked", "high_risk", "elevated"}


class ManualNode(BaseModel):
    node_id: str
    status: str = "blocked"


class SimulateRequest(BaseModel):
    disrupted: list[ManualNode] = []


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "agent": "route", "nodes": len(NODES)}


@router.get("/route/topology")
async def topology() -> dict:
    return build_topology()


@router.get("/route/live")
async def live(request: Request, hours: int = 24) -> dict:
    """Live Simulation Pipeline — ingest News-Agent critical events, classify
    them into node disruptions, and auto-reroute the corridor to India."""
    try:
        events = await fetch_critical_events(hours=hours)
    except Exception as exc:
        logger.warning("News Agent unreachable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="News Agent not reachable (expected on port 8000).",
        )

    disruptions = classify_live_events(events)
    brent = await fetch_brent_usd(request.app.state.fred_api_key)
    payload = run_pipeline(disruptions, mode="live", brent_usd=brent)
    payload["event_count"] = len(events)
    return payload


@router.post("/route/simulate")
async def simulate(request: Request, body: SimulateRequest) -> dict:
    """Manual Simulation Sandbox — reroute against user-toggled node states."""
    disruptions: list[Disruption] = []
    for item in body.disrupted:
        if item.node_id not in NODES:
            raise HTTPException(status_code=400, detail=f"Unknown node '{item.node_id}'.")
        status = item.status if item.status in _VALID_STATUS else "blocked"
        disruptions.append(classify_manual(item.node_id, status))

    brent = await fetch_brent_usd(request.app.state.fred_api_key)
    return run_pipeline(disruptions, mode="sandbox", brent_usd=brent)
