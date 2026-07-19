"""Minimal live-market fetch — Brent spot for the Impact Engine's cost framing.

Kept deliberately tiny (one FRED series) so the Route Agent has no hard runtime
dependency on the Risk Agent. Returns None on any failure; the Impact Engine
falls back to a sane default basket price.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_FRED_URL = "https://api.stlouisfed.org/fred/series/observations"


async def fetch_brent_usd(fred_api_key: str) -> float | None:
    if not fred_api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(
                _FRED_URL,
                params={
                    "series_id": "DCOILBRENTEU",
                    "api_key": fred_api_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": "5",
                },
            )
            resp.raise_for_status()
            for obs in resp.json().get("observations", []):
                v = obs.get("value")
                if v not in (".", None, ""):
                    return float(v)
    except Exception as exc:  # pragma: no cover - network best-effort
        logger.debug("Brent fetch failed: %s", exc)
    return None
