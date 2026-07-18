"""LangGraph nodes for the News Agent.

Design note — deliberate architecture decision:
the ingestion loop is a *deterministic pipeline* whose stages happen to
be graph nodes; the LLM is an enrichment stage, never the controller.
Determinism keeps 24/7 operation auditable and cheap. Agentic reasoning
(deep-dive corroboration on critical events) is a separate future graph.

Each node is a small class holding its collaborators (constructor
injection) and exposing an async __call__(state) -> partial state —
LangGraph merges the partial updates.
"""

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from vorentice_agents.domain.enums import NewsSegment, segment_of
from vorentice_agents.domain.models import ClassifiedArticle, RawArticle
from vorentice_agents.domain.state import NewsAgentState
from vorentice_agents.pipeline.alerts import AlertPolicy, EventCorroborationPolicy
from vorentice_agents.pipeline.classifier import ArticleClassifier
from vorentice_agents.pipeline.deduplicator import Deduplicator
from vorentice_agents.pipeline.digest import (
    QUIET_SEGMENT_TEXT,
    BriefingComposer,
)
from vorentice_agents.pipeline.prefilter import KeywordPreFilter
from vorentice_agents.persistence.repository import NewsRepository
from vorentice_agents.persistence.tables import SegmentDigestRow
from vorentice_agents.sources.base import NewsSource, SourceError
from vorentice_agents.sources.signals.base import SignalSource

logger = logging.getLogger(__name__)


class FetchNode:
    """Fan out to all sources concurrently; tolerate individual failures.

    Every source gets a hard time budget. A throttled or slow-walled
    provider (GDELT under 429, a hanging feed server) must never hold
    the whole ingestion cycle hostage — the SLA is enforced here, at the
    orchestration boundary, not trusted to adapter internals.
    """

    def __init__(
        self,
        sources: list[NewsSource],
        signal_sources: list[SignalSource] | None = None,
        timeout: float = 20.0,
        source_budget_seconds: float = 90.0,
    ) -> None:
        self._sources = sources
        self._signal_sources = signal_sources or []
        self._timeout = timeout
        self._source_budget = source_budget_seconds

    async def __call__(self, state: NewsAgentState) -> NewsAgentState:
        articles: list[RawArticle] = []
        signals: list[ClassifiedArticle] = []
        errors: dict[str, str] = {}

        # One connection pool; article and signal sources fetch together.
        all_sources = [*self._sources, *self._signal_sources]
        async with httpx.AsyncClient(
            timeout=self._timeout, follow_redirects=True
        ) as client:
            results = await asyncio.gather(
                *(
                    asyncio.wait_for(
                        source.fetch(client), timeout=self._source_budget
                    )
                    for source in all_sources
                ),
                return_exceptions=True,
            )

        for source, result in zip(all_sources, results):
            is_signal = source in self._signal_sources
            if isinstance(result, BaseException):
                message = (
                    f"exceeded {self._source_budget:.0f}s fetch budget"
                    if isinstance(result, (asyncio.TimeoutError, TimeoutError))
                    else str(result)
                )
                errors[source.name] = message
                logger.warning("source %s failed: %s", source.name, message)
            elif is_signal:
                signals.extend(result)
                logger.info("signal %s: %d items", source.name, len(result))
            else:
                articles.extend(result)
                logger.info("source %s: %d articles", source.name, len(result))

        return {
            "raw_articles": articles,
            "signal_items": signals,
            "stats": {
                "started_at": state.get("stats", {}).get(
                    "started_at", datetime.now(timezone.utc).isoformat()
                ),
                "fetched": len(articles),
                "signals": len(signals),
                "source_errors": errors,
            },
        }


class DedupNode:
    def __init__(self, deduplicator: Deduplicator) -> None:
        self._deduplicator = deduplicator

    async def __call__(self, state: NewsAgentState) -> NewsAgentState:
        new_articles = self._deduplicator.filter_new(
            state.get("raw_articles", [])
        )
        stats = dict(state.get("stats", {}))
        stats["after_dedup"] = len(new_articles)
        logger.info("dedup: %d new of %d fetched",
                    len(new_articles), stats.get("fetched", 0))
        return {"new_articles": new_articles, "stats": stats}


class PreFilterNode:
    def __init__(self, prefilter: KeywordPreFilter, llm_budget: int) -> None:
        self._prefilter = prefilter
        self._llm_budget = llm_budget

    async def __call__(self, state: NewsAgentState) -> NewsAgentState:
        relevant = self._prefilter.filter_relevant(
            state.get("new_articles", []), limit=self._llm_budget
        )
        stats = dict(state.get("stats", {}))
        stats["after_prefilter"] = len(relevant)
        logger.info("prefilter: %d relevant (budget %d)",
                    len(relevant), self._llm_budget)
        return {"relevant_articles": relevant, "stats": stats}


class ClassifyNode:
    def __init__(self, classifier: ArticleClassifier, batch_size: int) -> None:
        self._classifier = classifier
        self._batch_size = batch_size

    async def __call__(self, state: NewsAgentState) -> NewsAgentState:
        relevant = state.get("relevant_articles", [])
        classified = await self._classifier.classify(relevant)
        stats = dict(state.get("stats", {}))
        stats["classified"] = len(classified)
        stats["llm_calls"] = -(-len(relevant) // self._batch_size) if relevant else 0
        logger.info("classify: %d of %d", len(classified), len(relevant))
        return {"classified": classified, "stats": stats}


class PersistNode:
    def __init__(self, repository: NewsRepository) -> None:
        self._repository = repository

    async def __call__(self, state: NewsAgentState) -> NewsAgentState:
        # Articles (LLM-classified) and signals (rule-classified) share the
        # same table and the same dedup-by-canonical-key path.
        merged = [*state.get("classified", []), *state.get("signal_items", [])]
        stored = self._repository.store_classified(merged)
        stats = dict(state.get("stats", {}))
        stats["stored"] = stored
        logger.info(
            "persist: %d stored (%d articles + %d signals)",
            stored,
            len(state.get("classified", [])),
            len(state.get("signal_items", [])),
        )
        return {"stats": stats}


class DigestNode:
    """Regenerates the Daily Brief (Section 1 of the report) — one
    narrative digest per monitored category, composed from the window's
    stored items.

    Every generation writes a row for ALL categories: busy ones get the
    composed narrative, quiet ones get an explicit "no significant
    developments" line. That makes each generation a complete newspaper
    edition — the report never has to mix digests from different
    generations, and a category going quiet is itself visible news.

    A composition failure never fails the run: the previous generation
    simply stays current until the next successful cycle.
    """

    def __init__(
        self,
        repository: NewsRepository,
        composer: BriefingComposer,
        window_hours: int = 24,
    ) -> None:
        self._repository = repository
        self._composer = composer
        self._window_hours = window_hours

    async def __call__(self, state: NewsAgentState) -> NewsAgentState:
        stats = dict(state.get("stats", {}))

        # Idle-cycle guard: nothing new stored and a brief already exists
        # -> the existing edition is still accurate; don't spend tokens.
        if not stats.get("stored") and self._repository.latest_digests():
            stats["digests_generated"] = 0
            return {"stats": stats}

        items_by_segment: dict[NewsSegment, list] = {
            segment: [] for segment in NewsSegment
        }
        for row in self._repository.briefing_items(hours=self._window_hours):
            items_by_segment[segment_of(row.impact_category)].append(row)

        try:
            digests = await self._composer.compose(items_by_segment)
        except Exception as error:  # noqa: BLE001 — degradation path
            logger.error("daily-brief composition failed: %s", error)
            stats["digests_generated"] = 0
            return {"stats": stats}

        generation = [
            SegmentDigestRow(
                segment=segment.value,
                digest=digests.get(segment, QUIET_SEGMENT_TEXT),
                item_count=len(items_by_segment[segment]),
                window_hours=self._window_hours,
                composed_by=self._composer.name,
            )
            for segment in NewsSegment
        ]
        self._repository.save_digests(generation)
        stats["digests_generated"] = len(digests)
        logger.info(
            "daily brief: %d of %d categories composed (%d quiet)",
            len(digests),
            len(generation),
            len(generation) - len(digests),
        )
        return {"stats": stats}


class AlertNode:
    """Raises operator alerts. Two complementary policies, on the whole
    recent store (not just this run) so late-arriving corroboration still
    fires:

    1. per-item — trusted signals, official outlets, title-corroborated;
    2. event — >= 2 independent sources filing critical reports on the
       same chokepoint (catches genuine crises that per-item misses).
    """

    def __init__(
        self,
        repository: NewsRepository,
        policy: AlertPolicy,
        event_policy: EventCorroborationPolicy | None = None,
    ) -> None:
        self._repository = repository
        self._policy = policy
        self._event_policy = event_policy or EventCorroborationPolicy()

    async def __call__(self, state: NewsAgentState) -> NewsAgentState:
        raised = 0
        critical_items = self._repository.unalerted_critical_items()

        # 1. Per-item policy.
        for item in critical_items:
            if item.id is not None and self._policy.should_alert(item):
                reason = self._policy.reason(item)
                self._repository.raise_alert(item.id, reason)
                logger.warning("ALERT (item): %s — %s", item.title, reason)
                raised += 1

        # 2. Event corroboration on whatever is still unalerted.
        still_open = self._repository.unalerted_critical_items()
        for event in self._event_policy.find_events(still_open):
            self._repository.raise_event_alert(
                event.representative_id, list(event.item_ids), event.reason
            )
            logger.warning("ALERT (event): %s", event.reason)
            raised += 1

        stats = dict(state.get("stats", {}))
        stats["alerts_raised"] = raised
        return {"stats": stats}
