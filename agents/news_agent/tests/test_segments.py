"""Segment taxonomy: every category maps, labels exist, unknowns are safe."""

from vorentice_agents.domain.enums import (
    CATEGORY_TO_SEGMENT,
    SEGMENT_LABELS,
    ImpactCategory,
    NewsSegment,
    segment_of,
)


def test_every_impact_category_maps_to_a_segment():
    for category in ImpactCategory:
        assert category.value in CATEGORY_TO_SEGMENT, f"unmapped: {category}"


def test_every_segment_has_a_label():
    for segment in NewsSegment:
        assert segment in SEGMENT_LABELS


def test_user_facing_groupings():
    assert segment_of("armed_conflict") == NewsSegment.WAR_GEOPOLITICS
    assert segment_of("military_security") == NewsSegment.MILITARY_SECURITY
    assert segment_of("port_operations") == NewsSegment.PORTS_SHIPPING
    assert segment_of("route_closure") == NewsSegment.ROUTES_CHOKEPOINTS
    assert segment_of("price_movement") == NewsSegment.ENERGY_MARKETS
    assert segment_of("weather") == NewsSegment.WEATHER
    assert segment_of("sanctions") == NewsSegment.SANCTIONS_TRADE


def test_unknown_category_falls_back_to_other():
    # Legacy rows / future categories must never break the briefing.
    assert segment_of("something_new") == NewsSegment.OTHER
