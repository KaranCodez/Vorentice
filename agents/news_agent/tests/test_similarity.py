from vorentice_agents.pipeline.similarity import TitleSimilarity


SIM = TitleSimilarity()


def same(a: str, b: str) -> bool:
    return SIM.same_story(SIM.tokens(a), SIM.tokens(b))


def test_wire_story_rewrites_match():
    assert same(
        "Iran seizes oil tanker in Strait of Hormuz",
        "Oil tanker seized by Iran in the Strait of Hormuz",
    )


def test_different_stories_do_not_match():
    assert not same(
        "Iran seizes oil tanker in Strait of Hormuz",
        "OPEC agrees to cut production by one million barrels",
    )


def test_same_topic_different_event_does_not_match():
    assert not same(
        "Oil prices surge after OPEC production cut announcement",
        "Oil prices fall as US inventories rise unexpectedly",
    )


def test_empty_title_never_matches():
    assert not same("", "Iran seizes oil tanker")
