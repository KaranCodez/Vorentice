"""Alert gate: critical items fire only when corroborated or official."""

import asyncio

import httpx
import pytest

from vorentice_agents.domain.enums import ImpactCategory, Region, Severity
from vorentice_agents.domain.models import ClassifiedArticle, RawArticle
from vorentice_agents.pipeline.alerts import AlertPolicy
from vorentice_agents.pipeline.classifier import ArticleClassifier
from vorentice_agents.persistence.tables import NewsItemRow
from vorentice_agents.sources.base import NewsSource

from tests.test_graph import fresh_db  # noqa: F401  (reused fixture)


class CriticalClassifier(ArticleClassifier):
    async def classify(self, articles):
        return [
            ClassifiedArticle(
                article=a,
                relevance_score=1.0,
                severity=Severity.CRITICAL,
                impact_category=ImpactCategory.SUPPLY_DISRUPTION,
                region=Region.MIDDLE_EAST,
                summary="Critical event. Details follow.",
                classified_by="fake",
            )
            for a in articles
        ]


class OneShotSource(NewsSource):
    def __init__(self, name: str, articles: list[RawArticle]) -> None:
        self.name = name
        self._articles = articles

    async def fetch(self, client: httpx.AsyncClient) -> list[RawArticle]:
        return self._articles


def _article(url: str, title: str, source: str) -> RawArticle:
    return RawArticle(url=url, title=title, source_name=source)


# ── Pure policy tests ────────────────────────────────────────────────

def _row(**overrides) -> NewsItemRow:
    defaults = dict(
        dedup_key="k", url="u", title="t", source_name="outlet_a",
        relevance_score=1.0, severity="critical",
        impact_category="supply_disruption", region="middle_east",
    )
    defaults.update(overrides)
    return NewsItemRow(**defaults)


def test_single_source_critical_does_not_alert():
    assert not AlertPolicy().should_alert(_row(corroboration_count=1))


def test_corroborated_critical_alerts():
    assert AlertPolicy().should_alert(
        _row(corroboration_count=2, corroborating_sources="outlet_b")
    )


def test_official_source_alerts_without_corroboration():
    assert AlertPolicy().should_alert(_row(source_name="pib_mopng"))


def test_non_critical_never_alerts():
    assert not AlertPolicy().should_alert(
        _row(severity="high", corroboration_count=5)
    )


def test_already_alerted_does_not_refire():
    assert not AlertPolicy().should_alert(
        _row(corroboration_count=3, alert_sent=True)
    )


# ── Event corroboration (chokepoints AND every other segment) ────────

def test_event_corroboration_fires_on_two_sources():
    from vorentice_agents.pipeline.alerts import EventCorroborationPolicy

    items = [
        _row(source_name="oilprice", chokepoints="Strait of Hormuz", relevance_score=0.9),
        _row(source_name="et_energyworld", chokepoints="Strait of Hormuz", relevance_score=0.8),
    ]
    for i, it in enumerate(items):
        it.id = i + 1
    events = EventCorroborationPolicy().find_events(items)
    assert len(events) == 1
    assert events[0].label == "Strait of Hormuz"
    assert events[0].representative_id == 1  # highest relevance
    assert set(events[0].sources) == {"oilprice", "et_energyworld"}


def test_event_corroboration_needs_independent_sources():
    from vorentice_agents.pipeline.alerts import EventCorroborationPolicy

    # Two criticals but SAME source — not corroboration.
    items = [
        _row(source_name="oilprice", chokepoints="Strait of Hormuz"),
        _row(source_name="oilprice", chokepoints="Strait of Hormuz"),
    ]
    for i, it in enumerate(items):
        it.id = i + 1
    assert EventCorroborationPolicy().find_events(items) == []


def test_event_corroboration_without_chokepoint_uses_segment_region():
    """A war escalation with NO chokepoint tag must still corroborate —
    the system watches all segments, not one route."""
    from vorentice_agents.pipeline.alerts import EventCorroborationPolicy

    items = [
        _row(source_name="aljazeera", chokepoints="",
             impact_category="armed_conflict", region="middle_east"),
        _row(source_name="gnews_conflict", chokepoints="",
             impact_category="armed_conflict", region="middle_east"),
    ]
    for i, it in enumerate(items):
        it.id = i + 1
    events = EventCorroborationPolicy().find_events(items)
    assert len(events) == 1
    assert "Wars & Geopolitical Conflicts" in events[0].label
    assert "middle_east" in events[0].label


def test_multiple_simultaneous_events_all_surface():
    """Charter requirement: a war + a port shutdown + a weather crisis
    happening at once produce SEPARATE events, not one."""
    from vorentice_agents.pipeline.alerts import EventCorroborationPolicy

    items = [
        _row(source_name="a", chokepoints="", impact_category="armed_conflict", region="middle_east"),
        _row(source_name="b", chokepoints="", impact_category="armed_conflict", region="middle_east"),
        _row(source_name="c", chokepoints="", impact_category="port_operations", region="asia_pacific"),
        _row(source_name="d", chokepoints="", impact_category="port_operations", region="asia_pacific"),
        _row(source_name="e", chokepoints="", impact_category="weather", region="india"),
        _row(source_name="f", chokepoints="", impact_category="weather", region="india"),
    ]
    for i, it in enumerate(items):
        it.id = i + 1
    events = EventCorroborationPolicy().find_events(items)
    labels = {e.label for e in events}
    assert len(events) == 3
    assert any("Wars & Geopolitical" in l for l in labels)
    assert any("Ports & Shipping" in l for l in labels)
    assert any("Weather" in l for l in labels)


# ── End-to-end: corroboration arriving later still raises the alert ──

def test_late_corroboration_triggers_alert(fresh_db):  # noqa: F811
    from vorentice_agents.agent.graph import build_news_agent
    from vorentice_agents.persistence.repository import NewsRepository

    repository = NewsRepository()
    story_v1 = _article(
        "https://outlet-a.com/hormuz-closed",
        "Iran closes Strait of Hormuz to all tanker traffic",
        "outlet_a",
    )
    story_v2 = _article(
        "https://outlet-b.com/gulf-shutdown",
        "Strait of Hormuz closed to tanker traffic by Iran",
        "outlet_b",
    )

    # Run 1: single-source critical → stored, NO alert.
    asyncio.run(
        build_news_agent(
            sources=[OneShotSource("outlet_a", [story_v1])],
            classifier=CriticalClassifier(),
            repository=repository,
        ).run()
    )
    assert repository.recent_alerts() == []

    # Run 2: second outlet reports the same story → corroboration → alert.
    stats = asyncio.run(
        build_news_agent(
            sources=[OneShotSource("outlet_b", [story_v2])],
            classifier=CriticalClassifier(),
            repository=repository,
        ).run()
    )
    assert stats["alerts_raised"] == 1
    alerts = repository.recent_alerts()
    assert len(alerts) == 1
    alert, item = alerts[0]
    assert item.corroboration_count == 2
    assert "corroborated" in alert.reason


def test_event_alert_fires_for_multi_source_chokepoint(fresh_db):  # noqa: F811
    """Two DIFFERENT outlets file critical Hormuz stories with distinct
    wording — title dedup won't merge them, but event corroboration by
    chokepoint must still page."""
    from vorentice_agents.agent.graph import build_news_agent
    from vorentice_agents.persistence.repository import NewsRepository

    class HormuzChokepointClassifier(ArticleClassifier):
        async def classify(self, articles):
            return [
                ClassifiedArticle(
                    article=a,
                    relevance_score=0.95,
                    severity=Severity.CRITICAL,
                    impact_category=ImpactCategory.ROUTE_CLOSURE,
                    region=Region.MIDDLE_EAST,
                    chokepoints=("Strait of Hormuz",),
                    summary="Critical Hormuz event. Details follow.",
                    classified_by="fake",
                )
                for a in articles
            ]

    repository = NewsRepository()
    a = _article(
        "https://a.com/strikes",
        "Crude oil tanker seized near Hormuz amid US strikes",
        "outlet_a",
    )
    b = _article(
        "https://b.com/standstill",
        "Hormuz shipping halted as Iran conflict escalates, crude flows hit",
        "outlet_b",
    )
    stats = asyncio.run(
        build_news_agent(
            sources=[OneShotSource("outlet_a", [a]), OneShotSource("outlet_b", [b])],
            classifier=HormuzChokepointClassifier(),
            repository=repository,
        ).run()
    )
    assert stats["alerts_raised"] == 1
    alert, _ = repository.recent_alerts()[0]
    assert "Strait of Hormuz event" in alert.reason
    # Both constituent items marked alerted → no re-fire next run.
    assert all(i.alert_sent for i in repository.latest_items())
