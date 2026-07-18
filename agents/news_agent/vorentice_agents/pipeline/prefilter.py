"""Pre-LLM relevance filter.

A deterministic keyword scorer that runs before any token is spent.
It exists purely to cut LLM cost/latency (~70% of wire volume is noise
for our mandate); precision work happens in the LLM stage. Tune by
editing the vocabularies — no ML, no surprises, fully auditable.
"""

import re

from vorentice_agents.domain.models import RawArticle

# Weighted vocabularies. Score = sum of matched weights, capped at 1.0.
# Weights reflect how strongly a term signals crude-supply relevance
# on its own.
_CORE_TERMS: dict[str, float] = {
    r"\bcrude\b": 0.5,
    r"\boil\b": 0.3,
    r"\bopec\+?\b": 0.6,
    r"\btanker": 0.5,
    r"\bpetroleum\b": 0.5,
    r"\brefiner": 0.4,          # refinery / refiner / refining
    r"\bpipelines?\b": 0.4,
    r"\bbarrel": 0.4,
    r"\bbrent\b|\bwti\b": 0.6,
    r"\benergy\b": 0.15,
    r"\blng\b|\bnatural gas\b": 0.2,
}

# Maritime logistics — ports, shipping, canals. These matter even when
# the article never says "oil": a closed port or blocked canal reroutes
# crude and products all the same.
_MARITIME_TERMS: dict[str, float] = {
    r"\bports?\b|\bharbou?r\b|\bterminals?\b": 0.35,
    r"\bshipping\b|\bmaritime\b|\bvessels?\b|\bfreight\b|\bcargo\b": 0.3,
    r"\bcanal\b|\bstraits?\b": 0.4,
    r"\bcongestion\b|\bberth": 0.3,
    r"\brun aground\b|\bgrounding\b|\bcapsiz": 0.4,
    r"\bvlcc\b|\bsupertanker": 0.5,
    r"\bconvoy\b|\btransit(s|ing)?\b": 0.2,
}

# Conflict & security — wars and attacks in producer/transit regions are
# supply events even before markets react.
_SECURITY_TERMS: dict[str, float] = {
    r"\bmissiles?\b|\bdrones?\b|\buav\b|\brockets?\b": 0.45,
    r"\bpirac|\bpirates?\b|\bhijack": 0.5,
    r"\bnavy\b|\bnaval\b|\bwarships?\b|\bfrigate": 0.35,
    r"\binvasion\b|\boffensive\b|\bairstrikes?\b|\bshelling\b": 0.45,
    r"\bceasefire\b|\btruce\b": 0.3,
    r"\bterror": 0.3,
    r"\bhouthis?\b|\bhezbollah\b": 0.5,
    r"\bmilitar(y|ised|ized)\b": 0.2,
}

_GEO_TERMS: dict[str, float] = {
    r"\bhormuz\b": 0.7,
    r"\bmalacca\b": 0.6,
    r"\bsuez\b": 0.6,
    r"\bbab[- ]el[- ]mandeb\b|\bred sea\b": 0.5,
    r"\bblack sea\b|\bbosporus\b": 0.4,
    r"\bpanama\b": 0.35,
    r"\bindia\b|\bindian\b": 0.4,
    r"\bpersian gulf\b|\bmiddle east\b": 0.4,
    r"\bsaudi\b|\biraq\b|\biran\b|\buae\b|\bkuwait\b|\bqatar\b": 0.35,
    r"\brussia\b|\burals\b": 0.3,
    r"\bukrain|\bisrael\b|\bgaza\b|\byemen\b": 0.3,
    r"\bnigeria\b|\bangola\b|\bvenezuela\b": 0.3,
}

_EVENT_TERMS: dict[str, float] = {
    r"\battacks?\b|\bstrikes?\b|\bexplosions?\b|\bseiz": 0.5,
    r"\bsanction": 0.5,
    r"\bblockades?\b|\bclosures?\b|\bdisrupt|\bhalt": 0.5,
    r"\bembargo": 0.5,
    r"\bproduction cut\b|\boutput cut\b|\bquotas?\b": 0.5,
    r"\bprice (surge|spike|shock|crash|rall)|\bprices? (surge|spike|jump|plunge|soar)": 0.5,
    r"\bwars?\b|\bconflicts?\b|\bescalat|\bclash": 0.3,
    r"\bcyclones?\b|\bhurricanes?\b|\bstorms?\b": 0.25,
}

_ALL_VOCABULARIES = (
    _CORE_TERMS,
    _MARITIME_TERMS,
    _SECURITY_TERMS,
    _GEO_TERMS,
    _EVENT_TERMS,
)


class KeywordPreFilter:
    """Scores articles 0–1 on crude-supply relevance using keyword heuristics."""

    def __init__(self, threshold: float = 0.25) -> None:
        self._threshold = threshold
        self._compiled: list[tuple[re.Pattern[str], float]] = [
            (re.compile(pattern, re.IGNORECASE), weight)
            for vocabulary in _ALL_VOCABULARIES
            for pattern, weight in vocabulary.items()
        ]

    def score(self, article: RawArticle) -> float:
        text = f"{article.title} {article.snippet}"
        total = sum(
            weight for pattern, weight in self._compiled if pattern.search(text)
        )
        return min(total, 1.0)

    def filter_relevant(
        self, articles: list[RawArticle], limit: int | None = None
    ) -> list[RawArticle]:
        """Keep articles above threshold, best-first, optionally capped.

        The cap is the cost guard: when a news storm produces more
        candidates than the per-run LLM budget, we degrade gracefully by
        classifying the highest-scoring ones first.
        """
        scored = [
            (score, article)
            for article in articles
            if (score := self.score(article)) >= self._threshold
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        if limit is not None:
            scored = scored[:limit]
        return [article for _, article in scored]
