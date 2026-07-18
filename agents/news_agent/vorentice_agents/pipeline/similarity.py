"""Lightweight title similarity for near-duplicate story detection.

Token-set Jaccard over normalized headlines. Deliberately dependency-free
and deterministic: this layer catches the common case (same wire story,
different outlets) cheaply. Embedding-based similarity (pgvector) slots
in behind the same interface when we move to Postgres.
"""

import re

# Words that carry no story identity; kept short on purpose — over-long
# stopword lists start erasing meaning from short headlines.
_STOPWORDS = frozenset(
    "a an and as at by for from in of on or the to with over after amid".split()
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class TitleSimilarity:
    """Compares headlines for same-story identity."""

    def __init__(self, threshold: float = 0.6) -> None:
        self._threshold = threshold

    def tokens(self, title: str) -> frozenset[str]:
        return frozenset(
            token
            for token in _TOKEN_RE.findall(title.lower())
            if token not in _STOPWORDS and len(token) > 1
        )

    def same_story(self, tokens_a: frozenset[str], tokens_b: frozenset[str]) -> bool:
        if not tokens_a or not tokens_b:
            return False
        intersection = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)
        return intersection / union >= self._threshold
