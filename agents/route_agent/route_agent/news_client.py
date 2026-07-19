"""Agent coordination — pull live disruption signals from the News Agent.

The Route Agent's Live Mode "listens" to the News Agent's three-section report
(GET /api/news/report). We consume Section 2 (critical events) because those
carry the structured, chokepoint-tagged, criticality-scored disruptions the
Classification Engine turns into node-level failures.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

NEWS_AGENT_BASE = "http://127.0.0.1:8000/api"


async def fetch_critical_events(hours: int = 24) -> list[dict]:
    """Return the News Agent's critical events (empty list if unreachable)."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(f"{NEWS_AGENT_BASE}/news/report?hours={hours}")
        resp.raise_for_status()
        report = resp.json()
        return report.get("critical_events", []) or []
