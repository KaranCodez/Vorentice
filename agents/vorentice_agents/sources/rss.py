"""Generic RSS/Atom feed adapter.

One class serves every RSS-shaped provider (OilPrice, EIA, PIB, OGJ…);
the registry instantiates it once per configured feed. feedparser is
run in a worker thread because it is synchronous and can be slow on
large feeds.
"""

import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import httpx

from vorentice_agents.domain.models import RawArticle
from vorentice_agents.sources.base import NewsSource, SourceError, USER_AGENT


class RssSource(NewsSource):
    """Fetches and normalizes a single RSS/Atom feed."""

    def __init__(self, name: str, feed_url: str, max_entries: int = 50) -> None:
        self.name = name
        self._feed_url = feed_url
        self._max_entries = max_entries

    async def fetch(self, client: httpx.AsyncClient) -> list[RawArticle]:
        try:
            response = await client.get(
                self._feed_url,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise SourceError(self.name, str(exc)) from exc

        # feedparser is sync — keep the event loop responsive.
        parsed = await asyncio.to_thread(feedparser.parse, response.content)
        if parsed.bozo and not parsed.entries:
            raise SourceError(self.name, f"unparseable feed: {parsed.bozo_exception}")

        articles = []
        for entry in parsed.entries[: self._max_entries]:
            url = getattr(entry, "link", "").strip()
            title = getattr(entry, "title", "").strip()
            if not url or not title:
                continue
            articles.append(
                RawArticle(
                    url=url,
                    title=title,
                    source_name=self.name,
                    published_at=_entry_datetime(entry),
                    snippet=getattr(entry, "summary", "")[:500],
                )
            )
        return articles


def _entry_datetime(entry: feedparser.FeedParserDict) -> datetime | None:
    """Extract a timezone-aware datetime from whichever field the feed uses."""
    for attr in ("published", "updated", "created"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                parsed = parsedate_to_datetime(raw)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed
            except (TypeError, ValueError):
                continue
    # Fall back to feedparser's pre-parsed struct_time.
    for attr in ("published_parsed", "updated_parsed"):
        struct = getattr(entry, attr, None)
        if struct:
            return datetime(*struct[:6], tzinfo=timezone.utc)
    return None
