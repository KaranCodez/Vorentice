from datetime import datetime, timezone

from vorentice_agents.domain.enums import ImpactCategory, Region, Severity
from vorentice_agents.domain.models import ClassifiedArticle, RawArticle


def test_dedup_key_ignores_tracking_params():
    a = RawArticle(
        url="https://news.example.com/story?utm_source=x&utm_campaign=y",
        title="T", source_name="s",
    )
    b = RawArticle(url="https://news.example.com/story", title="T", source_name="s")
    assert a.dedup_key == b.dedup_key


def test_dedup_key_ignores_case_and_trailing_slash():
    a = RawArticle(url="HTTPS://News.Example.com/Story/", title="T", source_name="s")
    b = RawArticle(url="https://news.example.com/Story", title="T", source_name="s")
    assert a.dedup_key == b.dedup_key


def test_dedup_key_differs_for_different_paths():
    a = RawArticle(url="https://example.com/one", title="T", source_name="s")
    b = RawArticle(url="https://example.com/two", title="T", source_name="s")
    assert a.dedup_key != b.dedup_key


def test_title_whitespace_normalized():
    article = RawArticle(
        url="https://example.com", title="  Oil \n\n price   spikes ", source_name="s"
    )
    assert article.title == "Oil price spikes"


def test_classified_article_is_frozen():
    article = RawArticle(url="https://example.com", title="T", source_name="s")
    classified = ClassifiedArticle(
        article=article,
        relevance_score=0.9,
        severity=Severity.HIGH,
        impact_category=ImpactCategory.SUPPLY_DISRUPTION,
        region=Region.MIDDLE_EAST,
        summary="Two sentences. Exactly two.",
        classified_by="test",
        classified_at=datetime.now(timezone.utc),
    )
    try:
        classified.relevance_score = 0.1  # type: ignore[misc]
        raised = False
    except Exception:
        raised = True
    assert raised


def test_report_fields_default_safe():
    """Heuristic classification must never fabricate impact analysis or
    watchlist reasoning — the defaults keep those fields empty."""
    article = RawArticle(url="https://example.com", title="T", source_name="s")
    classified = ClassifiedArticle(
        article=article,
        relevance_score=0.5,
        severity=Severity.MEDIUM,
        impact_category=ImpactCategory.OTHER,
        region=Region.GLOBAL,
        summary="T",
        classified_by="heuristic",
    )
    assert classified.trade_impact == ""
    assert classified.escalation_potential is False
    assert classified.watchlist_reason == ""
    assert classified.escalation_triggers == ""


def test_report_fields_roundtrip():
    article = RawArticle(url="https://example.com", title="T", source_name="s")
    classified = ClassifiedArticle(
        article=article,
        relevance_score=0.8,
        severity=Severity.MEDIUM,
        impact_category=ImpactCategory.GEOPOLITICAL,
        region=Region.MIDDLE_EAST,
        summary="Tensions rising near a transit corridor.",
        trade_impact="No flows disrupted yet; insurers watching.",
        escalation_potential=True,
        watchlist_reason="Naval build-up near a major tanker route.",
        escalation_triggers="Any vessel interdiction or strait closure.",
        classified_by="test",
    )
    from vorentice_agents.persistence.repository import _to_row

    row = _to_row(classified)
    assert row.trade_impact == "No flows disrupted yet; insurers watching."
    assert row.escalation_potential is True
    assert row.watchlist_reason == "Naval build-up near a major tanker route."
    assert row.escalation_triggers == "Any vessel interdiction or strait closure."
