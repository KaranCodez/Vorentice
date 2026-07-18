"""Tests for the three-section report machinery: qualitative
criticality descriptors, the Daily Brief composer, and the DigestNode's
complete-edition guarantee (all 8 categories, every generation)."""

import asyncio

from vorentice_agents.agent.nodes import DigestNode
from vorentice_agents.domain.enums import NewsSegment, criticality_label
from vorentice_agents.persistence.tables import NewsItemRow, SegmentDigestRow
from vorentice_agents.pipeline.digest import (
    QUIET_SEGMENT_TEXT,
    HeuristicComposer,
)


# ── criticality descriptors (charter: no numeric scores, ever) ──────


def test_critical_severity_reads_critical():
    assert criticality_label("critical") == "Critical"


def test_medium_with_escalation_reads_emerging():
    assert criticality_label("medium", escalation_potential=True) == "Emerging"


def test_low_with_escalation_reads_emerging():
    assert criticality_label("low", escalation_potential=True) == "Emerging"


def test_high_with_escalation_stays_high():
    # Already-high events belong in the Critical Events Tracker, not the
    # watchlist — the Emerging descriptor is reserved for below-High.
    assert criticality_label("high", escalation_potential=True) == "High"


def test_plain_severities_title_cased():
    assert criticality_label("medium") == "Moderate"
    assert criticality_label("low") == "Low"


# ── Daily Brief composer fallback ───────────────────────────────────


def _row(title: str, summary: str = "", severity: str = "medium") -> NewsItemRow:
    return NewsItemRow(
        dedup_key=title,
        url=f"https://example.com/{abs(hash(title))}",
        title=title,
        source_name="test",
        relevance_score=0.5,
        severity=severity,
        impact_category="port_operations",
        region="global",
        summary=summary,
    )


def test_heuristic_composer_stitches_summaries():
    items = {
        NewsSegment.PORTS_SHIPPING: [
            _row("Port strike", "Dockworkers walked out at Rotterdam."),
            _row("Congestion", "Vessel queue doubled at Singapore"),
        ],
        NewsSegment.WEATHER: [],
    }
    digests = asyncio.run(HeuristicComposer().compose(items))
    assert NewsSegment.WEATHER not in digests  # quiet stays uncomposed
    text = digests[NewsSegment.PORTS_SHIPPING]
    assert "Dockworkers walked out at Rotterdam." in text
    assert "Vessel queue doubled at Singapore." in text  # period added


# ── DigestNode: every generation is a complete 8-category edition ──


class _FakeRepository:
    def __init__(self, items: list[NewsItemRow], existing_digests: bool = False):
        self._items = items
        self._existing = existing_digests
        self.saved: list[SegmentDigestRow] = []

    def briefing_items(self, hours: int = 24):
        return self._items

    def latest_digests(self):
        if not self._existing:
            return {}
        return {"weather": SegmentDigestRow(segment="weather", digest="old")}

    def save_digests(self, digests):
        self.saved = list(digests)


def test_digest_node_writes_all_categories():
    repository = _FakeRepository(
        [_row("Port strike", "Dockworkers walked out at Rotterdam.")]
    )
    node = DigestNode(repository, HeuristicComposer())
    state = asyncio.run(node({"stats": {"stored": 1}}))

    assert len(repository.saved) == len(NewsSegment)  # complete edition
    by_segment = {row.segment: row for row in repository.saved}
    assert "Rotterdam" in by_segment["ports_shipping"].digest
    # Quiet categories are explicit, never missing.
    assert by_segment["weather"].digest == QUIET_SEGMENT_TEXT
    assert by_segment["weather"].item_count == 0
    assert state["stats"]["digests_generated"] == 1


def test_digest_node_skips_idle_cycles():
    repository = _FakeRepository([_row("x")], existing_digests=True)
    node = DigestNode(repository, HeuristicComposer())
    state = asyncio.run(node({"stats": {"stored": 0}}))

    assert repository.saved == []  # previous edition stays current
    assert state["stats"]["digests_generated"] == 0


def test_digest_node_composer_failure_never_fails_run():
    class _ExplodingComposer(HeuristicComposer):
        async def compose(self, items_by_segment):
            raise RuntimeError("llm down")

    repository = _FakeRepository([_row("x")])
    node = DigestNode(repository, _ExplodingComposer())
    state = asyncio.run(node({"stats": {"stored": 1}}))

    assert repository.saved == []
    assert state["stats"]["digests_generated"] == 0
