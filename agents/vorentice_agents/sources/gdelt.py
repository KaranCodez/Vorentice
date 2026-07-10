"""GDELT DOC 2.0 API adapter.

GDELT monitors global news in 100+ languages, updating every 15 minutes,
free of charge. We run a curated set of standing queries (human-reviewed,
in config — never LLM-generated) and merge the results.

API reference: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from vorentice_agents.domain.models import RawArticle
from vorentice_agents.sources.base import NewsSource, SourceError, USER_AGENT

logger = logging.getLogger(__name__)

_GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# GDELT throttles per-IP hard; unofficial guidance is ~1 request / 5s.
_QUERY_SPACING_SECONDS = 3.0
# Short cooldown + single retry: if the whole IP is throttled a longer
# wait won't clear within one cycle, so we abandon fast and pick GDELT
# back up next run rather than stalling the pipeline.
_RATE_LIMIT_COOLDOWN_SECONDS = 5.0
_MAX_COOLDOWN_SECONDS = 8.0

# Standing queries — the agent's "watch list". Reviewed by humans.
# GDELT syntax: quoted phrases, OR groups in parens, near:N proximity.
DEFAULT_QUERIES: tuple[str, ...] = (
    '"crude oil" (India OR OPEC OR sanctions OR disruption)',
    '("Strait of Hormuz" OR "Suez Canal" OR "Bab el-Mandeb" OR "Strait of Malacca") (oil OR tanker OR shipping)',
    '(tanker OR pipeline) (attack OR seized OR explosion OR blockade)',
    '"oil price" (surge OR spike OR crash OR shock)',
    '(India) ("oil import" OR "petroleum" OR "strategic reserve" OR refinery)',
)


class GdeltDocSource(NewsSource):
    """Fetches articles from the GDELT DOC 2.0 full-text search API."""

    name = "gdelt"

    def __init__(
        self,
        queries: tuple[str, ...] = DEFAULT_QUERIES,
        timespan: str = "1h",
        max_records_per_query: int = 75,
    ) -> None:
        self._queries = queries
        self._timespan = timespan
        self._max_records = max_records_per_query

    async def fetch(self, client: httpx.AsyncClient) -> list[RawArticle]:
        articles: dict[str, RawArticle] = {}
        errors: list[str] = []

        for position, query in enumerate(self._queries):
            if position > 0:
                # Space queries out — GDELT 429s aggressive callers.
                await asyncio.sleep(_QUERY_SPACING_SECONDS)
            try:
                for item in await self._run_query(client, query):
                    article = self._to_article(item)
                    if article is not None:
                        # Same URL may match several standing queries.
                        articles.setdefault(article.dedup_key, article)
            except httpx.HTTPStatusError as exc:
                errors.append(f"query {query!r}: HTTP {exc.response.status_code}")
                if exc.response.status_code == 429:
                    # Whole IP is throttled — abandon remaining queries
                    # this run rather than digging the hole deeper.
                    logger.warning(
                        "gdelt rate-limited; skipping %d remaining queries",
                        len(self._queries) - position - 1,
                    )
                    break
            except httpx.TransportError as exc:
                # Connection-level failure is IP-wide, not query-specific —
                # stop hammering and pick GDELT up next cycle.
                errors.append(f"query {query!r}: {exc}")
                logger.warning(
                    "gdelt transport error; skipping %d remaining queries",
                    len(self._queries) - position - 1,
                )
                break
            except httpx.HTTPError as exc:
                errors.append(f"query {query!r}: {exc}")

        # Partial success is fine; total failure is not.
        if errors and not articles:
            raise SourceError(self.name, "; ".join(errors))
        return list(articles.values())

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, max=4),
        reraise=True,
    )
    async def _run_query(
        self, client: httpx.AsyncClient, query: str
    ) -> list[dict[str, Any]]:
        response = await self._get(client, query)
        if response.status_code == 429:
            # One measured second chance after a cooldown; if still
            # throttled, raise and let fetch() abandon the cycle.
            retry_after = float(
                response.headers.get("Retry-After", _RATE_LIMIT_COOLDOWN_SECONDS)
            )
            cooldown = min(retry_after, _MAX_COOLDOWN_SECONDS)
            logger.info("gdelt 429 — cooling down %.0fs before one retry", cooldown)
            await asyncio.sleep(cooldown)
            response = await self._get(client, query)
        response.raise_for_status()
        # GDELT occasionally returns an empty body or HTML error page
        # with status 200 — treat unparseable JSON as "no results".
        try:
            payload = response.json()
        except ValueError:
            return []
        return payload.get("articles", [])

    async def _get(
        self, client: httpx.AsyncClient, query: str
    ) -> httpx.Response:
        return await client.get(
            _GDELT_DOC_URL,
            params={
                "query": query,
                "mode": "artlist",
                "format": "json",
                "timespan": self._timespan,
                "maxrecords": str(self._max_records),
                "sort": "datedesc",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=12.0,  # fail a hung GDELT call fast, don't eat the SLA
        )

    def _to_article(self, item: dict[str, Any]) -> RawArticle | None:
        url = item.get("url", "").strip()
        title = item.get("title", "").strip()
        if not url or not title:
            return None
        return RawArticle(
            url=url,
            title=title,
            source_name=f"gdelt:{item.get('domain', 'unknown')}",
            published_at=_parse_gdelt_date(item.get("seendate")),
            language=item.get("language", "en").lower()[:2] or "en",
        )


def _parse_gdelt_date(value: str | None) -> datetime | None:
    """GDELT dates look like '20260709T143000Z'."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None
