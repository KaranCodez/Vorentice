from vorentice_agents.domain.models import RawArticle
from vorentice_agents.pipeline.prefilter import KeywordPreFilter


def make(title: str, snippet: str = "") -> RawArticle:
    return RawArticle(
        url=f"https://example.com/{abs(hash(title))}",
        title=title,
        snippet=snippet,
        source_name="test",
    )


def test_hormuz_tanker_scores_high():
    article = make("Tanker attacked near Strait of Hormuz, crude oil shipments halted")
    assert KeywordPreFilter().score(article) >= 0.8


def test_celebrity_news_scores_zero():
    article = make("Pop star announces world tour dates for 2027")
    assert KeywordPreFilter().score(article) == 0.0


def test_india_import_relevant():
    article = make("India increases crude oil imports from West Africa amid OPEC cuts")
    assert KeywordPreFilter().score(article) >= 0.5


def test_threshold_filters():
    prefilter = KeywordPreFilter(threshold=0.25)
    articles = [
        make("OPEC announces production cut of 1 million barrels"),
        make("Local bakery wins prize for best croissant"),
    ]
    kept = prefilter.filter_relevant(articles)
    assert len(kept) == 1
    assert "OPEC" in kept[0].title


def test_limit_keeps_best_first():
    prefilter = KeywordPreFilter(threshold=0.1)
    weak = make("Energy sector update for the quarter")
    strong = make("Iran seizes crude oil tanker in Strait of Hormuz")
    kept = prefilter.filter_relevant([weak, strong], limit=1)
    assert kept == [strong]
