"""Serper web search wrapper for the Risk Agent.

Called as an on-demand tool during the chat loop when the user asks about
something not covered by the pre-fetched news payload or live market data
(e.g. a specific refinery delay, a recent OPEC+ decision, a government
press release).
"""

import logging

import httpx

logger = logging.getLogger(__name__)

_SERPER_URL = "https://google.serper.dev/search"
_MAX_RESULTS = 5

# Tool definition passed to the OpenAI API.
WEB_SEARCH_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web for current information not already in the pre-fetched "
            "news payload or live market data. Use this when the user asks about: "
            "a specific refinery's operational status, a recent policy or government "
            "announcement, the reason behind a particular delay or disruption, "
            "recent OPEC+ decisions, SPR fill levels, or any data point that needs "
            "more detail than what the context provides. "
            "Do NOT call this for questions already answerable from the ingested context."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "A focused, specific search query. Include dates or locations "
                        "when relevant. Example: 'India Mangaluru SPR refill delay 2026'"
                    ),
                }
            },
            "required": ["query"],
        },
    },
}


async def serper_search(query: str, api_key: str) -> str:
    """Execute a Serper search and return a clean text block for LLM context."""
    if not api_key:
        return "Web search unavailable: SERPER_API_KEY not configured."

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _SERPER_URL,
                headers={
                    "X-API-KEY": api_key,
                    "Content-Type": "application/json",
                },
                json={"q": query, "num": _MAX_RESULTS},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Serper search failed for %r: %s", query, exc)
        return f"Web search failed: {exc}"

    lines = [f"[WEB SEARCH RESULTS for: {query}]", ""]

    # Answer box — direct answer when Google surfaces one
    answer_box = data.get("answerBox", {})
    for key in ("answer", "snippet"):
        if val := answer_box.get(key):
            lines += [f"Quick answer: {val}", ""]
            break

    # Organic results
    for i, item in enumerate(data.get("organic", [])[:_MAX_RESULTS], 1):
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        source = item.get("displayLink", "")
        date = item.get("date", "")
        date_str = f" ({date})" if date else ""
        lines.append(f"{i}. {title}{date_str} [{source}]")
        if snippet:
            lines.append(f"   {snippet}")
        lines.append("")

    if len(lines) <= 2:
        return f"[WEB SEARCH RESULTS for: {query}]\nNo results found."

    return "\n".join(lines).rstrip()
