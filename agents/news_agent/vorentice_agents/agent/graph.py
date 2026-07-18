"""News Agent graph assembly and façade.

Topology:

    fetch ─► dedup ─► prefilter ─┬─► classify ─► persist ─► digest ─► alerts ─► END
                                 └────────────► persist   (nothing relevant)

`build_news_agent()` is the composition root: it wires settings,
sources, pipeline stages and storage together. Everything else in the
codebase receives its dependencies — nothing else calls constructors
across layers.
"""

import logging
from datetime import datetime, timezone

from langgraph.graph import END, START, StateGraph

from vorentice_agents.agent.nodes import (
    AlertNode,
    ClassifyNode,
    DedupNode,
    DigestNode,
    FetchNode,
    PersistNode,
    PreFilterNode,
)
from vorentice_agents.pipeline.alerts import AlertPolicy
from vorentice_agents.domain.state import NewsAgentState, RunStats
from vorentice_agents.pipeline.classifier import (
    ArticleClassifier,
    AzureLlmClassifier,
    HeuristicClassifier,
)
from vorentice_agents.pipeline.digest import (
    AzureLlmComposer,
    BriefingComposer,
    HeuristicComposer,
)
from vorentice_agents.pipeline.deduplicator import Deduplicator
from vorentice_agents.pipeline.prefilter import KeywordPreFilter
from vorentice_agents.persistence.repository import NewsRepository
from vorentice_agents.settings import AppSettings, get_settings
from vorentice_agents.sources.base import NewsSource
from vorentice_agents.sources.registry import (
    build_article_sources,
    build_signal_sources,
)
from vorentice_agents.sources.signals.base import SignalSource

logger = logging.getLogger(__name__)


def _has_relevant_articles(state: NewsAgentState) -> str:
    # With no articles to classify we still go through persist — signal
    # items fetched this run need storing, and the alert gate must run
    # (corroboration added this run can make an OLD item alert-eligible).
    return "classify" if state.get("relevant_articles") else "persist"


class NewsAgent:
    """Façade over the compiled graph — what schedulers and APIs call."""

    def __init__(self, graph, repository: NewsRepository) -> None:
        self._graph = graph
        self._repository = repository

    async def run(self) -> RunStats:
        """Execute one full ingestion cycle and record it."""
        initial: NewsAgentState = {
            "stats": {"started_at": datetime.now(timezone.utc).isoformat()}
        }
        ok = True
        try:
            final_state: NewsAgentState = await self._graph.ainvoke(initial)
            stats: RunStats = final_state.get("stats", {})
        except Exception:
            logger.exception("news agent run failed")
            ok = False
            stats = initial["stats"]
        self._repository.record_run(stats, ok=ok)
        return stats


def build_news_agent(
    settings: AppSettings | None = None,
    *,
    sources: list[NewsSource] | None = None,
    signal_sources: list[SignalSource] | None = None,
    classifier: ArticleClassifier | None = None,
    composer: BriefingComposer | None = None,
    repository: NewsRepository | None = None,
) -> NewsAgent:
    """Composition root. Keyword overrides exist for tests."""
    settings = settings or get_settings()
    repository = repository or NewsRepository()
    explicit_sources = sources is not None
    if sources is None:
        sources = build_article_sources(settings.news, settings.sources)
    if signal_sources is None:
        # When a caller wires sources by hand (tests), don't silently pull
        # live signal feeds — they must opt in explicitly.
        signal_sources = (
            [] if explicit_sources else build_signal_sources(settings.sources)
        )
    classifier = classifier or _select_classifier(settings)
    composer = composer or _select_composer(settings)

    graph = StateGraph(NewsAgentState)
    graph.add_node(
        "fetch",
        FetchNode(
            sources,
            signal_sources=signal_sources,
            timeout=settings.news.http_timeout_seconds,
            source_budget_seconds=settings.news.source_fetch_budget_seconds,
        ),
    )
    graph.add_node("dedup", DedupNode(Deduplicator(repository)))
    graph.add_node(
        "prefilter",
        PreFilterNode(
            KeywordPreFilter(settings.news.prefilter_threshold),
            llm_budget=settings.news.max_llm_articles,
        ),
    )
    graph.add_node("classify", ClassifyNode(classifier, settings.news.llm_batch_size))
    graph.add_node("persist", PersistNode(repository))
    graph.add_node(
        "digest",
        DigestNode(
            repository,
            composer,
            window_hours=settings.news.digest_window_hours,
        ),
    )
    graph.add_node("alerts", AlertNode(repository, AlertPolicy()))

    graph.add_edge(START, "fetch")
    graph.add_edge("fetch", "dedup")
    graph.add_edge("dedup", "prefilter")
    graph.add_conditional_edges(
        "prefilter", _has_relevant_articles, ["classify", "persist"]
    )
    graph.add_edge("classify", "persist")
    graph.add_edge("persist", "digest")
    graph.add_edge("digest", "alerts")
    graph.add_edge("alerts", END)

    return NewsAgent(graph.compile(), repository)


def _select_classifier(settings: AppSettings) -> ArticleClassifier:
    if settings.news.dry_run:
        logger.warning("NEWS_DRY_RUN=true — using heuristic classifier (no LLM)")
        return HeuristicClassifier()
    if not settings.azure_openai.is_configured:
        logger.warning(
            "Azure OpenAI not configured — falling back to heuristic classifier. "
            "Set AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY for real classification."
        )
        return HeuristicClassifier()
    return AzureLlmClassifier(
        settings.azure_openai, batch_size=settings.news.llm_batch_size
    )


def _select_composer(settings: AppSettings) -> BriefingComposer:
    """Daily Brief composer follows the classifier's degradation path."""
    if settings.news.dry_run or not settings.azure_openai.is_configured:
        return HeuristicComposer()
    return AzureLlmComposer(settings.azure_openai)
