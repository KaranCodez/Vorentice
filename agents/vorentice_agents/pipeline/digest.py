"""Daily Brief composition — Section 1 of the intelligence report.

The charter makes the agent a complete newspaper replacement: for each
of the 8 monitored categories the user gets a clear, detailed roundup of
the latest developments, not just the critical spikes. This stage turns
the window's stored items into one narrative digest per category.

`BriefingComposer` is the contract; two implementations mirror the
classifier's degradation path:

- `AzureLlmComposer`  — one structured-output call composes every
  category's narrative from the stored item summaries.
- `HeuristicComposer` — keyless fallback: a readable stitched roundup
  of the item summaries, so the Daily Brief never goes dark when the
  LLM is unavailable.
"""

import logging
from abc import ABC, abstractmethod

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from vorentice_agents.domain.enums import SEGMENT_LABELS, NewsSegment
from vorentice_agents.persistence.tables import NewsItemRow
from vorentice_agents.settings import AzureOpenAISettings

logger = logging.getLogger(__name__)

#: Cap per category so a news storm cannot blow the composer's context.
#: Items are passed newest-first, so the cap sheds the oldest ones.
MAX_ITEMS_PER_SEGMENT = 25

QUIET_SEGMENT_TEXT = (
    "No significant developments reported in this category during the "
    "current monitoring window."
)


def stitch_summaries(rows: list[NewsItemRow]) -> str:
    """Plain stitched roundup of item summaries — grounded, no LLM.
    Used by the heuristic composer and as the API's fallback when items
    exist but no digest generation has run yet (fresh/migrated DB)."""
    parts = []
    for row in rows[:MAX_ITEMS_PER_SEGMENT]:
        text = row.summary if row.summary else row.title
        if not text.rstrip().endswith((".", "!", "?")):
            text = f"{text}."
        parts.append(text)
    return " ".join(parts)


class BriefingComposer(ABC):
    """Contract for the Daily Brief stage."""

    #: recorded in `segment_digests.composed_by`
    name: str = "composer"

    @abstractmethod
    async def compose(
        self, items_by_segment: dict[NewsSegment, list[NewsItemRow]]
    ) -> dict[NewsSegment, str]:
        """Return one narrative digest per segment WITH items. Quiet
        segments are the caller's concern (deterministic text, no LLM)."""
        raise NotImplementedError


class _SegmentDigest(BaseModel):
    segment: str = Field(description="segment id exactly as given in the input")
    digest: str = Field(
        description=(
            "The category's Daily Brief: a clear, detailed narrative "
            "roundup of ALL notable developments in the provided items"
        )
    )


class _DailyBrief(BaseModel):
    digests: list[_SegmentDigest]


_COMPOSER_PROMPT = """You are the editor of a global supply-chain intelligence \
briefing. Your readers read NO other newspaper — for each news category below, \
your roundup is their complete picture of what happened. Write the Daily Brief.

For EVERY category in the input, write one narrative roundup (roughly 3–7 \
sentences, more if the category is busy) that covers ALL notable developments \
in that category's items — do not silently drop stories; group related items \
into one thread where they cover the same event.

Rules:
- Ground every statement ONLY in the provided item summaries. Never invent \
facts, numbers, or outcomes.
- Plain, factual, newspaper-brief prose. No bullet lists, no headlines.
- Never mention scores, ratings, or the monitoring system itself.
- Use qualitative language for urgency (critical, severe, elevated, emerging).
- Global perspective — do not anchor the narrative on any single route, \
region or country beyond what the items themselves report.
- Return one digest per input category, with the segment id copied exactly."""


class AzureLlmComposer(BriefingComposer):
    """Composes all category digests in a single structured-output call."""

    def __init__(self, settings: AzureOpenAISettings) -> None:
        from langchain_openai import AzureChatOpenAI

        self.name = settings.deployment
        self._llm = AzureChatOpenAI(
            azure_endpoint=settings.endpoint,
            api_key=settings.api_key,
            api_version=settings.api_version,
            azure_deployment=settings.deployment,
            temperature=0.0,
            timeout=90,
            max_retries=2,
        ).with_structured_output(_DailyBrief)

    async def compose(
        self, items_by_segment: dict[NewsSegment, list[NewsItemRow]]
    ) -> dict[NewsSegment, str]:
        populated = {
            segment: items[:MAX_ITEMS_PER_SEGMENT]
            for segment, items in items_by_segment.items()
            if items
        }
        if not populated:
            return {}

        sections = []
        for segment, items in populated.items():
            lines = "\n".join(
                f"- [{row.severity}] {row.title} — {row.summary}"
                for row in items
            )
            sections.append(
                f"CATEGORY {segment.value} ({SEGMENT_LABELS[segment]}):\n{lines}"
            )
        prompt = "\n\n".join(sections)

        brief: _DailyBrief = await self._llm.ainvoke(
            [SystemMessage(_COMPOSER_PROMPT), HumanMessage(prompt)]
        )

        valid_ids = {segment.value for segment in populated}
        digests: dict[NewsSegment, str] = {}
        for entry in brief.digests:
            if entry.segment not in valid_ids:
                logger.warning("composer returned unknown segment %r", entry.segment)
                continue
            if entry.digest.strip():
                digests[NewsSegment(entry.segment)] = entry.digest.strip()
        return digests


class HeuristicComposer(BriefingComposer):
    """Stitches item summaries into a plain roundup. Not editorial prose,
    but the Daily Brief stays populated with real, grounded content."""

    name = "heuristic"

    async def compose(
        self, items_by_segment: dict[NewsSegment, list[NewsItemRow]]
    ) -> dict[NewsSegment, str]:
        return {
            segment: stitch_summaries(items)
            for segment, items in items_by_segment.items()
            if items
        }
