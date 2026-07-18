"""Generic RSS/Atom feed adapter.

One class serves every RSS-shaped provider (OilPrice, EIA, PIB, OGJ…);
the registry instantiates it once per configured feed. feedparser is
run in a worker thread because it is synchronous and can be slow on
large feeds.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser
import httpx

from vorentice_agents.domain.models import RawArticle
from vorentice_agents.sources.base import NewsSource, SourceError, USER_AGENT


class RssSource(NewsSource):
    """Fetches and normalizes a single RSS/Atom feed.

    `publisher_per_entry` is for aggregator feeds (Google News): each
    entry names its true publisher in the <source> tag, so articles get
    source_name "feed:Publisher". Without this, every aggregated outlet
    would collapse into one source and corroboration independence checks
    would wrongly treat BBC and Reuters as the same voice.
    """

    def __init__(
        self,
        name: str,
        feed_url: str,
        max_entries: int = 50,
        publisher_per_entry: bool = False,
        max_age_days: int = 7,
    ) -> None:
        self.name = name
        self._feed_url = feed_url
        self._max_entries = max_entries
        self._publisher_per_entry = publisher_per_entry
        self._max_age_days = max_age_days

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

        # Freshness gate — search-based aggregator feeds (Google News)
        # can return YEARS-old articles; an intelligence feed must never
        # present the 2021 Suez blockage as breaking news. Entries with
        # no parseable date are kept (regular feeds are current by nature).
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._max_age_days)

        articles = []
        for entry in parsed.entries[: self._max_entries]:
            url = getattr(entry, "link", "").strip()
            title = getattr(entry, "title", "").strip()
            if not url or not title:
                continue

            published_at = _entry_datetime(entry)
            if published_at is not None and published_at < cutoff:
                continue  # stale — historical result, not news

            source_name = self.name
            if self._publisher_per_entry:
                publisher = _entry_publisher(entry)
                if publisher:
                    source_name = f"{self.name}:{publisher}"
                    # Aggregators suffix headlines with " - Publisher";
                    # strip it so titles dedup/compare cleanly.
                    suffix = f" - {publisher}"
                    if title.endswith(suffix):
                        title = title[: -len(suffix)].rstrip()

            articles.append(
                RawArticle(
                    url=url,
                    title=title,
                    source_name=source_name,
                    published_at=published_at,
                    snippet=getattr(entry, "summary", "")[:500],
                )
            )
        return articles


def _entry_publisher(entry: feedparser.FeedParserDict) -> str:
    """True publisher of an aggregated entry (Google News <source> tag)."""
    source = getattr(entry, "source", None)
    if source is None:
        return ""
    title = source.get("title", "") if hasattr(source, "get") else ""
    return " ".join(str(title).split())[:80]


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
