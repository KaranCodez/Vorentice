"""End-to-end graph test with fake sources and classifier — no network,
no LLM, no shared DB (each test gets a fresh SQLite file)."""

import asyncio

import httpx
import pytest

from vorentice_agents.domain.enums import ImpactCategory, Region, Severity
from vorentice_agents.domain.models import ClassifiedArticle, RawArticle
from vorentice_agents.pipeline.classifier import ArticleClassifier
from vorentice_agents.sources.base import NewsSource, SourceError


class FakeSource(NewsSource):
    name = "fake"

    def __init__(self, articles: list[RawArticle]) -> None:
        self._articles = articles

    async def fetch(self, client: httpx.AsyncClient) -> list[RawArticle]:
        return self._articles


class FailingSource(NewsSource):
    name = "failing"

    async def fetch(self, client: httpx.AsyncClient) -> list[RawArticle]:
        raise SourceError(self.name, "simulated outage")


class HangingSource(NewsSource):
    name = "hanging"

    async def fetch(self, client: httpx.AsyncClient) -> list[RawArticle]:
        await asyncio.sleep(3600)
        return []


class FakeClassifier(ArticleClassifier):
    async def classify(self, articles):
        return [
            ClassifiedArticle(
                article=a,
                relevance_score=0.9,
                severity=Severity.HIGH,
                impact_category=ImpactCategory.SUPPLY_DISRUPTION,
                region=Region.MIDDLE_EAST,
                summary="Fake summary. Second sentence.",
                classified_by="fake",
            )
            for a in articles
        ]


@pytest.fixture()
def fresh_db(tmp_path, monkeypatch):
    """Point the app at a throwaway SQLite DB and reset cached singletons."""
    from vorentice_agents import settings as settings_module
    from vorentice_agents.persistence import database

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    settings_module.get_settings.cache_clear()
    database.get_engine.cache_clear()
    database.create_db_and_tables()
    yield
    settings_module.get_settings.cache_clear()
    database.get_engine.cache_clear()


_STORY_TITLES = {
    "a": "Crude oil tanker seized near Strait of Hormuz by Iranian forces",
    "b": "OPEC agrees surprise production cut of two million barrels",
    "x": "India expands strategic petroleum reserve amid supply concerns",
    "y": "Explosion halts crude loading at major Saudi export terminal",
    "z": "Sanctions tighten on Russian crude shipments to Asian buyers",
    "q": "Suez Canal transit fees rise as tanker traffic rebounds",
}


def _relevant(key: str) -> RawArticle:
    return RawArticle(
        url=f"https://example.com/oil-{key}",
        title=_STORY_TITLES[key],
        source_name="fake",
    )


def _irrelevant() -> RawArticle:
    return RawArticle(
        url="https://example.com/sports",
        title="Local football team wins championship",
        source_name="fake",
    )


def test_full_pipeline_stores_relevant_articles(fresh_db):
    from vorentice_agents.agent.graph import build_news_agent
    from vorentice_agents.persistence.repository import NewsRepository

    repository = NewsRepository()
    agent = build_news_agent(
        sources=[FakeSource([_relevant("a"), _relevant("b"), _irrelevant()])],
        classifier=FakeClassifier(),
        repository=repository,
    )
    stats = asyncio.run(agent.run())

    assert stats["fetched"] == 3
    assert stats["after_prefilter"] == 2   # irrelevant filtered out
    assert stats["stored"] == 2
    items = repository.latest_items()
    assert len(items) == 2
    assert all(item.severity == "high" for item in items)


def test_second_run_dedups_everything(fresh_db):
    from vorentice_agents.agent.graph import build_news_agent
    from vorentice_agents.persistence.repository import NewsRepository

    repository = NewsRepository()
    make_agent = lambda: build_news_agent(  # noqa: E731
        sources=[FakeSource([_relevant("x")])],
        classifier=FakeClassifier(),
        repository=repository,
    )
    first = asyncio.run(make_agent().run())
    second = asyncio.run(make_agent().run())

    assert first["stored"] == 1
    assert second["after_dedup"] == 0
    assert second.get("stored", 0) == 0


def test_source_failure_does_not_kill_run(fresh_db):
    from vorentice_agents.agent.graph import build_news_agent
    from vorentice_agents.persistence.repository import NewsRepository

    repository = NewsRepository()
    agent = build_news_agent(
        sources=[FailingSource(), FakeSource([_relevant("y")])],
        classifier=FakeClassifier(),
        repository=repository,
    )
    stats = asyncio.run(agent.run())

    assert stats["stored"] == 1
    assert "failing" in stats["source_errors"]


def test_near_duplicate_becomes_corroboration(fresh_db):
    """Same story from a second outlet must fold into the stored item
    as corroboration instead of creating a duplicate row."""
    from vorentice_agents.agent.graph import build_news_agent
    from vorentice_agents.persistence.repository import NewsRepository

    repository = NewsRepository()
    original = RawArticle(
        url="https://outlet-one.com/hormuz",
        title="Iran seizes crude oil tanker in Strait of Hormuz",
        source_name="outlet_one",
    )
    rewrite = RawArticle(
        url="https://outlet-two.com/gulf-incident",
        title="Crude oil tanker seized by Iran in the Strait of Hormuz",
        source_name="outlet_two",
    )
    asyncio.run(
        build_news_agent(
            sources=[FakeSource([original])],
            classifier=FakeClassifier(),
            repository=repository,
        ).run()
    )
    second = asyncio.run(
        build_news_agent(
            sources=[FakeSource([rewrite])],
            classifier=FakeClassifier(),
            repository=repository,
        ).run()
    )

    assert second.get("stored", 0) == 0
    items = repository.latest_items()
    assert len(items) == 1
    assert items[0].corroboration_count == 2
    assert "outlet_two" in items[0].corroborating_sources


def test_hanging_source_is_cut_off_by_budget(fresh_db, monkeypatch):
    """A source that never returns must not stall the pipeline."""
    monkeypatch.setenv("NEWS_SOURCE_FETCH_BUDGET_SECONDS", "1")
    from vorentice_agents import settings as settings_module

    settings_module.get_settings.cache_clear()
    from vorentice_agents.agent.graph import build_news_agent
    from vorentice_agents.persistence.repository import NewsRepository

    repository = NewsRepository()
    agent = build_news_agent(
        sources=[HangingSource(), FakeSource([_relevant("q")])],
        classifier=FakeClassifier(),
        repository=repository,
    )
    stats = asyncio.run(agent.run())

    assert stats["stored"] == 1
    assert "budget" in stats["source_errors"]["hanging"]


def test_run_is_recorded(fresh_db):
    from vorentice_agents.agent.graph import build_news_agent
    from vorentice_agents.persistence.repository import NewsRepository

    repository = NewsRepository()
    agent = build_news_agent(
        sources=[FakeSource([_relevant("z")])],
        classifier=FakeClassifier(),
        repository=repository,
    )
    asyncio.run(agent.run())
    runs = repository.recent_runs()
    assert len(runs) == 1
    assert runs[0].ok is True
    assert runs[0].stored == 1
