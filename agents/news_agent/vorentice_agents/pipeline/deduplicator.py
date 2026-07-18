"""Deduplication stage — three identity checks, cheapest first.

1. within-batch exact: same canonical-URL hash twice in one run;
2. against the store, exact: hash already in `news_items`;
3. near-duplicate: same story text from a different outlet (token-set
   Jaccard on headlines vs. the last 72h). Near-dups are not discarded
   silently — each one is recorded as *corroboration* on the stored
   item, which is what the future critical-alert gate feeds on.

Embedding similarity (pgvector) will replace layer 3's comparator
behind this same class when we move to Postgres; callers won't change.
"""

import logging

from vorentice_agents.domain.models import RawArticle
from vorentice_agents.persistence.repository import NewsRepository
from vorentice_agents.pipeline.similarity import TitleSimilarity

logger = logging.getLogger(__name__)


class Deduplicator:
    """Filters articles the system has already seen, in any form."""

    def __init__(
        self,
        repository: NewsRepository,
        similarity: TitleSimilarity | None = None,
        near_dup_window_hours: int = 72,
    ) -> None:
        self._repository = repository
        self._similarity = similarity or TitleSimilarity()
        self._window_hours = near_dup_window_hours

    def filter_new(self, articles: list[RawArticle]) -> list[RawArticle]:
        candidates = self._drop_exact_duplicates(articles)
        if not candidates:
            return []
        return self._collapse_near_duplicates(candidates)

    def _drop_exact_duplicates(
        self, articles: list[RawArticle]
    ) -> list[RawArticle]:
        seen_in_batch: set[str] = set()
        candidates: list[RawArticle] = []
        for article in articles:
            key = article.dedup_key
            if key in seen_in_batch:
                continue
            seen_in_batch.add(key)
            candidates.append(article)

        if not candidates:
            return []
        known = self._repository.existing_dedup_keys(
            [a.dedup_key for a in candidates]
        )
        return [a for a in candidates if a.dedup_key not in known]

    def _collapse_near_duplicates(
        self, candidates: list[RawArticle]
    ) -> list[RawArticle]:
        stored = [
            (item_id, self._similarity.tokens(title))
            for item_id, title in self._repository.recent_titles(
                self._window_hours
            )
        ]

        kept: list[RawArticle] = []
        kept_tokens: list[frozenset[str]] = []
        corroborated = 0

        for article in candidates:
            tokens = self._similarity.tokens(article.title)

            matched_id = next(
                (
                    item_id
                    for item_id, stored_tokens in stored
                    if self._similarity.same_story(tokens, stored_tokens)
                ),
                None,
            )
            if matched_id is not None:
                self._repository.add_corroboration(
                    matched_id, article.source_name
                )
                corroborated += 1
                continue

            if any(
                self._similarity.same_story(tokens, existing)
                for existing in kept_tokens
            ):
                continue  # same story twice within this batch

            kept.append(article)
            kept_tokens.append(tokens)

        if corroborated:
            logger.info(
                "near-dup: %d sightings folded into stored items as corroboration",
                corroborated,
            )
        return kept
