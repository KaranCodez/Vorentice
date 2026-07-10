"""Classification stage — the only place the LLM is invoked.

`ArticleClassifier` is the contract; two implementations:

- `AzureLlmClassifier`  — Azure OpenAI structured output, batched.
- `HeuristicClassifier` — keyword-based fallback used in dry-run mode
  (no keys required) and as the degradation path if Azure is down:
  ingestion never stops, items are marked for later re-classification.
"""

import asyncio
import logging
from abc import ABC, abstractmethod

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from vorentice_agents.domain.enums import (
    CHOKEPOINTS,
    ImpactCategory,
    Region,
    Severity,
)
from vorentice_agents.domain.models import ClassifiedArticle, RawArticle
from vorentice_agents.settings import AzureOpenAISettings

logger = logging.getLogger(__name__)


class ArticleClassifier(ABC):
    """Contract for the enrichment stage."""

    @abstractmethod
    async def classify(
        self, articles: list[RawArticle]
    ) -> list[ClassifiedArticle]:
        raise NotImplementedError


# ── LLM output schema ────────────────────────────────────────────────
# The model fills this per article; index ties results back to inputs
# so a partially-hallucinated batch cannot mis-attribute classifications.

class _ArticleVerdict(BaseModel):
    index: int = Field(description="0-based index of the article in the input list")
    relevance_score: float = Field(
        ge=0.0, le=1.0,
        description="Relevance to India's crude-oil supply security",
    )
    severity: Severity
    impact_category: ImpactCategory
    region: Region
    chokepoints: list[str] = Field(
        default_factory=list,
        description=f"Maritime chokepoints explicitly implicated; choose only from {list(CHOKEPOINTS)}",
    )
    summary: str = Field(
        description="Two factual sentences grounded ONLY in the given headline/snippet"
    )


class _BatchVerdict(BaseModel):
    verdicts: list[_ArticleVerdict]


_SYSTEM_PROMPT = """You are an intelligence analyst for India's national crude-oil \
supply security monitoring system.

For each numbered news article, assess:
- relevance_score: how much this affects India's crude oil supply chain \
(imports, prices, shipping routes, refining). 0.0 = unrelated, 1.0 = direct major impact.
- severity: operational urgency, judged by THREAT to physical supply.
- impact_category, region: pick the single best fit.
- chokepoints: list any named maritime chokepoints genuinely implicated.
- summary: exactly two factual sentences. NEVER add facts not present in the \
headline/snippet. If information is thin, say what is known and note it is a headline-only report.

SEVERITY RUBRIC — apply strictly:
- "critical": an ACTIVE or IMMINENT disruption to physical crude supply within \
days — chokepoint closure, attack on tankers/pipelines/terminals on India-bound \
routes, major producer outage, a sudden double-digit price shock, or war/strikes \
directly hitting oil infrastructure.
- "high": a serious escalation or threat that raises supply risk but is not yet \
disrupting flows (rising tensions near a chokepoint, new sanctions on a major \
supplier, a large single-session price move).
- "medium": material but routine market/policy news (OPEC commentary, ordinary \
price moves, refinery maintenance, trade-flow shifts).
- "low": background, explainer, historical, forecast, or POSITIVE news. \
Rising production, higher inventories, improved/ample supply, easing tensions, \
new capacity, and analytical retrospectives are NOT critical or high — they \
REDUCE risk. Score them low.

Good news is never critical. Reserve "critical" for genuine supply threats. \
Ground every judgment in the text provided. Do not speculate.

EXAMPLES (headline -> severity):
- "U.S. jet fuel production rises after prices doubled earlier this year" -> low \
(production RISING eases supply; a past price move is not a current threat).
- "Shipping through the Strait of Hormuz grinds to a near standstill after strikes" \
-> critical (active disruption to a chokepoint on India-bound routes).
- "OPEC signals it may consider output changes next quarter" -> medium (routine \
commentary, no immediate effect).
- "UAE oil output hits all-time high" -> low (more supply reduces risk)."""


class AzureLlmClassifier(ArticleClassifier):
    """Batched structured-output classification via Azure OpenAI."""

    def __init__(
        self,
        settings: AzureOpenAISettings,
        batch_size: int = 8,
        max_concurrency: int = 3,
    ) -> None:
        # Import here so dry-run mode works without Azure packages configured.
        from langchain_openai import AzureChatOpenAI

        self._deployment = settings.deployment
        self._batch_size = batch_size
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._llm = AzureChatOpenAI(
            azure_endpoint=settings.endpoint,
            api_key=settings.api_key,
            api_version=settings.api_version,
            azure_deployment=settings.deployment,
            temperature=0.0,
            timeout=60,
            max_retries=2,
        ).with_structured_output(_BatchVerdict)

    async def classify(
        self, articles: list[RawArticle]
    ) -> list[ClassifiedArticle]:
        if not articles:
            return []
        batches = [
            articles[i : i + self._batch_size]
            for i in range(0, len(articles), self._batch_size)
        ]
        results = await asyncio.gather(
            *(self._classify_batch(batch) for batch in batches),
            return_exceptions=True,
        )
        classified: list[ClassifiedArticle] = []
        for batch, result in zip(batches, results):
            if isinstance(result, BaseException):
                logger.error(
                    "LLM batch failed (%d articles): %s", len(batch), result
                )
                continue  # skipped articles stay unclassified; next run may retry
            classified.extend(result)
        return classified

    async def _classify_batch(
        self, batch: list[RawArticle]
    ) -> list[ClassifiedArticle]:
        prompt = "\n\n".join(
            f"[{i}] SOURCE: {a.source_name}\nHEADLINE: {a.title}\nSNIPPET: {a.snippet or '(none)'}"
            for i, a in enumerate(batch)
        )
        async with self._semaphore:
            verdict: _BatchVerdict = await self._llm.ainvoke(
                [SystemMessage(_SYSTEM_PROMPT), HumanMessage(prompt)]
            )

        classified = []
        for item in verdict.verdicts:
            if not 0 <= item.index < len(batch):
                logger.warning("LLM returned out-of-range index %d", item.index)
                continue
            classified.append(
                ClassifiedArticle(
                    article=batch[item.index],
                    relevance_score=item.relevance_score,
                    severity=item.severity,
                    impact_category=item.impact_category,
                    region=item.region,
                    chokepoints=tuple(
                        c for c in item.chokepoints if c in CHOKEPOINTS
                    ),
                    summary=item.summary,
                    classified_by=self._deployment,
                )
            )
        return classified


class HeuristicClassifier(ArticleClassifier):
    """Keyword-only fallback. Deliberately conservative: it never assigns
    severity above MEDIUM, because escalation decisions belong to the LLM
    (and eventually corroboration logic), not a regex."""

    def __init__(self) -> None:
        from vorentice_agents.pipeline.prefilter import KeywordPreFilter

        self._scorer = KeywordPreFilter(threshold=0.0)

    async def classify(
        self, articles: list[RawArticle]
    ) -> list[ClassifiedArticle]:
        classified = []
        for article in articles:
            score = self._scorer.score(article)
            classified.append(
                ClassifiedArticle(
                    article=article,
                    relevance_score=round(score, 2),
                    severity=Severity.MEDIUM if score >= 0.7 else Severity.LOW,
                    impact_category=ImpactCategory.OTHER,
                    region=Region.GLOBAL,
                    chokepoints=(),
                    summary=article.title,
                    classified_by="heuristic",
                )
            )
        return classified
