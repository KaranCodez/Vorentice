"""RSS freshness gate: aggregator search feeds must not resurface
years-old stories (e.g. the 2021 Suez blockage) as breaking news."""

import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

from vorentice_agents.sources.rss import RssSource


def _feed_xml(entries: str) -> bytes:
    return f"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>t</title>{entries}</channel></rss>""".encode()


def _entry(title: str, url: str, published: datetime, publisher: str = "") -> str:
    src = f'<source url="https://x.com">{publisher}</source>' if publisher else ""
    return (
        f"<item><title>{title}</title><link>{url}</link>"
        f"<pubDate>{format_datetime(published)}</pubDate>{src}</item>"
    )


class _FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


class _FakeClient:
    def __init__(self, content: bytes) -> None:
        self._content = content

    async def get(self, *args, **kwargs):
        return _FakeResponse(self._content)


def test_stale_entries_are_dropped():
    now = datetime.now(timezone.utc)
    xml = _feed_xml(
        _entry("Fresh port story", "https://n.com/fresh", now - timedelta(hours=2))
        + _entry("Suez blocked (2021)", "https://n.com/old", now - timedelta(days=1900))
    )
    source = RssSource(name="test", feed_url="https://x.com/feed")
    articles = asyncio.run(source.fetch(_FakeClient(xml)))  # type: ignore[arg-type]
    titles = [a.title for a in articles]
    assert "Fresh port story" in titles
    assert all("2021" not in t for t in titles)


def test_publisher_attribution_for_aggregators():
    now = datetime.now(timezone.utc)
    xml = _feed_xml(
        _entry("Canal update - BBC", "https://n.com/a", now, publisher="BBC")
    )
    source = RssSource(
        name="gnews_ports", feed_url="https://x.com/feed", publisher_per_entry=True
    )
    articles = asyncio.run(source.fetch(_FakeClient(xml)))  # type: ignore[arg-type]
    assert articles[0].source_name == "gnews_ports:BBC"
    assert articles[0].title == "Canal update"  # " - BBC" suffix stripped
