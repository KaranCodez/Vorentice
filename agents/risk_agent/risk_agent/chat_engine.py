"""Azure OpenAI chat engine for the Risk Agent.

Two responsibilities:
  * fetch structured intelligence from the News Agent (agent coordination)
  * run the Risk Agent LLM — both the one-shot ingestion briefing and the
    streaming interactive QA loop.
"""

import json
import logging
from typing import AsyncIterator

import httpx
from openai import AsyncAzureOpenAI

from risk_agent.system_prompt import (
    RISK_AGENT_SYSTEM_PROMPT,
    FORMATTING_RULES,
    FOLLOWUP_RULES,
    CHAT_TURN_RULES,
)

logger = logging.getLogger(__name__)

NEWS_AGENT_BASE = "http://127.0.0.1:8000/api"


# ──────────────────────────────────────────────────────────────────
# Agent coordination — pull live intelligence from the News Agent
# ──────────────────────────────────────────────────────────────────
async def fetch_news_report(hours: int = 24) -> dict:
    """Fetch the full three-section intelligence report from the News Agent."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{NEWS_AGENT_BASE}/news/report?hours={hours}")
        resp.raise_for_status()
        return resp.json()


def extract_critical_events(report: dict) -> str:
    """Extract Section 2 — Critical Events — as a clean ingestion stream."""
    events = report.get("critical_events", [])
    if not events:
        return "No critical events recorded in the current window."

    lines = ["[SECTION 2: HIGH-IMPACT & CRITICAL DEVELOPMENTS]\n"]
    for ev in events:
        lines.append(f"- Segment: {ev.get('category', 'Unknown')}")
        lines.append(f"  Headline/Event: {ev.get('event_summary', '')}")
        lines.append(f"  Trade Impact: {ev.get('trade_impact', 'Not assessed')}")
        lines.append(f"  Region: {ev.get('region', 'Global')}")
        chokepoints = ev.get("chokepoints", [])
        if chokepoints:
            lines.append(f"  Chokepoints Affected: {', '.join(chokepoints)}")
        lines.append(f"  Criticality: {ev.get('criticality', 'High')}")
        lines.append("  Status: Active/Escalating")
        lines.append("")
    return "\n".join(lines)


def extract_watchlist(report: dict) -> str:
    """Extract Section 3 — Emerging Threats — as a clean ingestion stream."""
    watchlist = report.get("watchlist", [])
    if not watchlist:
        return "No emerging threats in the current watchlist window."

    lines = ["[SECTION 3: HORIZON WATCH (Emerging & Latent Developments)]\n"]
    for item in watchlist:
        lines.append(f"- Segment: {item.get('category', 'Unknown')}")
        lines.append(f"  Emerging Issue: {item.get('summary', '')}")
        lines.append(
            f"  Current Indicator: {item.get('watchlist_reason', 'Under monitoring')}"
        )
        triggers = item.get("escalation_triggers", "")
        if triggers:
            lines.append(f"  Escalation Triggers: {triggers}")
        lines.append(f"  Region: {item.get('region', 'Global')}")
        lines.append("")
    return "\n".join(lines)


def _mode_label(mode: str) -> str:
    return (
        "Critical Events (Section 2)"
        if mode == "critical_events"
        else "Emerging Threats Watchlist (Section 3)"
    )


class RiskChatEngine:
    """Stateless engine — callers manage conversation history."""

    def __init__(self, endpoint: str, api_key: str, deployment: str, api_version: str):
        self._client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )
        self._deployment = deployment

    def _system(self, payload: str) -> str:
        return (
            f"{RISK_AGENT_SYSTEM_PROMPT}\n\n"
            f"{FORMATTING_RULES}\n\n"
            f"[INGESTED_NEWS_PAYLOAD]\n{payload}"
        )

    # ── One-shot ingestion briefing (real analysis, not a template) ──
    async def generate_briefing(self, payload: str, mode: str) -> dict:
        """Run the agent over the ingested payload to produce the opening
        Aggregated Threat Profile, Global Risk Score, Executive Synthesis
        and suggested opening questions. Returns a structured dict."""
        instruction = (
            f"You have just ingested the {_mode_label(mode)} section from the News "
            "Agent (see INGESTED_NEWS_PAYLOAD). Produce your ingestion acknowledgment.\n\n"
            "Respond with a STRICT JSON object (no prose outside JSON) with keys:\n"
            '  "risk_score": integer 1-100 (aggregated global risk),\n'
            '  "risk_label": one of "Low","Moderate","Elevated","High","Severe",\n'
            '  "executive_synthesis": a 2-3 sentence plain-English summary string,\n'
            '  "threat_profile_md": a Markdown string with the AGGREGATED THREAT '
            "PROFILE — synthesize the individual events into ONE cohesive global "
            "narrative (how do the weather events, wars, port closures, sanctions "
            "interact?). Use ## sub-headers, bullet points and a short Markdown table "
            "of the top clustered risks (columns: Cluster | Trigger | India Exposure). "
            "Do NOT restate the raw feed line by line.\n"
            '  "followups": array of 4 short question strings the user is most likely '
            "to ask next, phrased from the user's point of view.\n\n"
            "Keep the plain-English colleague tone. No academic jargon."
        )
        messages = [
            {"role": "system", "content": self._system(payload)},
            {"role": "user", "content": instruction},
        ]
        resp = await self._client.chat.completions.create(
            model=self._deployment,
            messages=messages,
            response_format={"type": "json_object"},
            max_completion_tokens=2000,
        )
        raw = resp.choices[0].message.content or "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("briefing JSON parse failed; raw=%s", raw[:200])
            data = {}

        return {
            "risk_score": int(data.get("risk_score", 50) or 50),
            "risk_label": data.get("risk_label", "Elevated"),
            "executive_synthesis": data.get("executive_synthesis", ""),
            "threat_profile_md": data.get("threat_profile_md", ""),
            "followups": [str(f) for f in data.get("followups", [])][:4],
        }

    # ── Streaming interactive QA ──
    async def chat(
        self,
        payload: str,
        messages: list[dict],
        user_message: str,
    ) -> AsyncIterator[str]:
        """Stream a response. Ends with a <<FOLLOWUPS>> block the client parses."""
        system_content = (
            f"{self._system(payload)}\n\n{CHAT_TURN_RULES}\n\n{FOLLOWUP_RULES}"
        )

        openai_messages = [{"role": "system", "content": system_content}]
        for msg in messages:
            openai_messages.append({"role": msg["role"], "content": msg["content"]})
        openai_messages.append({"role": "user", "content": user_message})

        stream = await self._client.chat.completions.create(
            model=self._deployment,
            messages=openai_messages,
            stream=True,
            max_completion_tokens=2500,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content
