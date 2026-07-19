"""LangGraph ReAct agent factory for the Risk Agent.

`build_react_agent` returns a compiled LangGraph graph that handles
multi-step tool orchestration. Unlike the Phase 2 single-shot loop,
the graph can call tools as many times as needed before producing a
final answer — the LLM decides autonomously when it has enough context.

Tools registered here:
  web_search  — Serper API (enabled when SERPER_API_KEY is set)
"""

from langchain_core.tools import tool as lc_tool
from langchain_openai import AzureChatOpenAI
from langgraph.prebuilt import create_react_agent

from risk_agent.web_search import serper_search


def build_react_agent(
    endpoint: str,
    api_key: str,
    deployment: str,
    api_version: str,
    serper_api_key: str = "",
):
    """Build and return a compiled LangGraph ReAct graph.

    The graph is stateless — callers pass full conversation history on
    every invocation. No checkpointer is used so there is no in-process
    state to manage.
    """
    llm = AzureChatOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        azure_deployment=deployment,
        api_version=api_version,
        streaming=True,
        temperature=0,
    )

    tools = []

    if serper_api_key:
        _key = serper_api_key  # captured in closure; avoids late-binding

        @lc_tool
        async def web_search(query: str) -> str:
            """Search the web for current information not in the pre-fetched news
            payload or live market data. Use when the user asks about: a specific
            refinery's operational status, a recent government or policy announcement,
            SPR fill levels, OPEC+ decisions with exact numbers, or any data point
            that needs more detail than the ingested context provides.
            Do NOT call for questions already answerable from the context.
            Use a focused, specific query — include dates and locations when relevant."""
            return await serper_search(query, _key)

        tools.append(web_search)

    return create_react_agent(llm, tools=tools)
