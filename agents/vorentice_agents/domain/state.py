"""LangGraph state for the News Agent.

The state is a plain TypedDict (LangGraph convention). Each node reads
the fields it needs and returns a partial update; LangGraph merges them.
Keeping the state flat and serializable means checkpointing (SQLite /
Postgres checkpointer) works out of the box when we enable it.
"""

from typing import TypedDict

from vorentice_agents.domain.models import ClassifiedArticle, RawArticle


class RunStats(TypedDict, total=False):
    """Operational accounting for one agent run — persisted to `agent_runs`."""

    started_at: str          # ISO timestamp
    fetched: int             # articles returned by all sources
    after_dedup: int         # new articles not seen before
    after_prefilter: int     # articles that reached the LLM
    classified: int          # successfully classified
    signals: int             # structured signal items produced
    stored: int              # rows written
    source_errors: dict[str, str]  # source name -> error message
    llm_calls: int
    alerts_raised: int


class NewsAgentState(TypedDict, total=False):
    """The single state object threaded through the news graph."""

    raw_articles: list[RawArticle]
    new_articles: list[RawArticle]        # post-dedup
    relevant_articles: list[RawArticle]   # post-prefilter
    classified: list[ClassifiedArticle]   # LLM-classified articles
    signal_items: list[ClassifiedArticle]  # deterministic structured signals
    stats: RunStats
