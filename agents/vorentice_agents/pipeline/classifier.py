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
        description=(
            "Relevance to global supply chains, trade and logistics "
            "(internal filter only — never shown to users)"
        ),
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
    trade_impact: str = Field(
        default="",
        description=(
            "One or two sentences: how this affects global trade and "
            "logistics RIGHT NOW (flows, routes, costs, delays). Empty "
            "string if there is no current trade effect."
        ),
    )
    escalation_potential: bool = Field(
        default=False,
        description=(
            "True if this is NOT critical right now but could plausibly "
            "escalate into a major supply-chain disruption later"
        ),
    )
    watchlist_reason: str = Field(
        default="",
        description=(
            "If escalation_potential: one sentence on WHY this belongs "
            "on the watchlist. Empty otherwise."
        ),
    )
    escalation_triggers: str = Field(
        default="",
        description=(
            "If escalation_potential: the concrete trigger(s) that would "
            "turn this into a critical disruption. Empty otherwise."
        ),
    )


class _BatchVerdict(BaseModel):
    verdicts: list[_ArticleVerdict]


_SYSTEM_PROMPT = """You are an intelligence analyst for a global supply-chain and \
geopolitical monitoring system. Its users read NO other newspaper: your analysis is \
their complete picture of world events affecting trade, so it must be comprehensive, \
global and multi-category. The system watches ALL domains that can affect supply \
chains and trade — wars, oil and energy markets, weather, ports, sanctions, route \
blockages, military incidents, logistics — worldwide. Do NOT anchor on any single \
route, region, country or scenario (the Strait of Hormuz is one chokepoint among \
many, not the default): an event in ANY category and ANY region deserves full, \
independent assessment.

For each numbered news article, assess:
- relevance_score: how much this affects global supply chains, trade flows and \
logistics (commodities, shipping routes, ports, transport, production). \
0.0 = unrelated, 1.0 = direct major impact. This is an internal filter only — \
users never see numbers, so never mention scores in any text field.
- severity: operational urgency, judged by THREAT to supply chains and logistics.
- impact_category: the single best fit from this taxonomy:
  * supply_disruption — physical crude/product supply interrupted or at risk
  * price_movement — significant market price action
  * opec_decision — OPEC/OPEC+ production policy
  * sanctions — sanctions, embargoes, export bans, trade restrictions
  * port_operations — port closures, congestion, labor strikes, terminal outages
  * route_closure — chokepoint/canal/route blockage or rerouting
  * geopolitical — political threats, diplomatic crises, rising tensions
  * armed_conflict — wars, invasions, declared hostilities, major escalations
  * military_security — missile/drone attacks, strikes on infrastructure, \
piracy, vessel seizures, terrorism
  * weather — storms, cyclones, floods affecting energy or shipping
  * policy / other — anything else
- region: single best fit.
- chokepoints: named maritime chokepoints genuinely implicated (often none).
- summary: exactly two factual sentences. NEVER add facts not present in the \
headline/snippet. If information is thin, say what is known and note it is a headline-only report.
- trade_impact: 1–2 sentences on how this affects global trade and logistics \
RIGHT NOW — rerouted flows, delayed shipments, price pass-through, capacity lost, \
insurance/freight costs. Ground it in the text; if there is no current trade \
effect, return an empty string. Qualitative words only, never numeric scores.
- escalation_potential / watchlist_reason / escalation_triggers: the watchlist \
call. Flag escalation_potential=true for events that are NOT critical today but \
could become major disruptions — e.g. rising tensions near a trade route, a \
forming storm system, threatened strike action, sanctions under discussion, \
military posturing near a chokepoint. Give the WHY (watchlist_reason) and the \
concrete tripwires that would make it critical (escalation_triggers, e.g. \
"strike vote passes and walkout begins", "storm intensifies to category 4 on a \
port-bound track", "naval incident closes the strait to tankers"). For events \
already critical/high or with no plausible escalation path, leave all three \
at their defaults.

SEVERITY RUBRIC — apply strictly, in ANY category:
- "critical": an ACTIVE or IMMINENT disruption — chokepoint/canal closure, \
attack on tankers/pipelines/ports/terminals, war eruption or major escalation in \
a producing or transit region, major producer outage, sudden double-digit price \
shock, severe storm shutting a major port or shipping lane.
- "high": a serious escalation or threat not yet disrupting flows — rising \
tensions near a transit route, new sanctions on a major supplier, missile/drone \
activity near shipping lanes, a large single-session price move, a cyclone \
forecast to hit a port region.
- "medium": material but routine — OPEC commentary, ordinary price moves, \
refinery maintenance, trade-flow shifts, minor port delays.
- "low": background, explainer, historical, forecast commentary, or POSITIVE \
news. Rising production, higher inventories, easing tensions, ceasefires \
holding, new capacity — these REDUCE risk. Score them low.

Good news is never critical. Ground every judgment in the text provided. Do not speculate.

EXAMPLES (headline -> category, severity):
- "Missile strikes hit oil terminal at Ras Tanura" -> military_security, critical.
- "Shipping through the Strait of Hormuz grinds to a near standstill after strikes" \
-> route_closure, critical.
- "War escalates as strikes hit second-largest city" -> armed_conflict, \
critical if in a producing/transit region, else high.
- "Cyclone forces closure of Mumbai and Kandla ports" -> weather, critical.
- "Dockworkers strike shuts Europe's largest port" -> port_operations, high.
- "New sanctions target tankers carrying Iranian crude" -> sanctions, high.
- "U.S. jet fuel production rises after prices doubled earlier this year" -> \
price_movement, low (production RISING eases supply; past price move is not a threat).
- "OPEC signals it may consider output changes next quarter" -> opec_decision, medium.
- "UAE oil output hits all-time high" -> supply_disruption, low (more supply reduces risk)."""


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
                    trade_impact=item.trade_impact.strip(),
                    escalation_potential=item.escalation_potential,
                    watchlist_reason=item.watchlist_reason.strip(),
                    escalation_triggers=item.escalation_triggers.strip(),
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
