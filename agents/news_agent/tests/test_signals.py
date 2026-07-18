"""Signal sources: deterministic classification, no network."""

import asyncio

from vorentice_agents.domain.enums import ImpactCategory, Region, Severity
from vorentice_agents.sources.signals.base import build_signal_item
from vorentice_agents.sources.signals.eia import EiaCrudeStocksSignal, _severity_for_change
from vorentice_agents.sources.signals.fred import _severity_for_move
from vorentice_agents.sources.signals.openmeteo import _severity_for_conditions


# ── Pure severity functions ──────────────────────────────────────────

def test_eia_large_draw_is_high():
    assert _severity_for_change(-11000) == Severity.HIGH  # -11M bbl


def test_eia_small_change_is_low():
    assert _severity_for_change(-1200) == Severity.LOW


def test_eia_large_build_is_not_alarming():
    assert _severity_for_change(+12000) == Severity.LOW


def test_fred_price_shock_severity_scale():
    assert _severity_for_move(-12.5) == Severity.CRITICAL  # double-digit shock
    assert _severity_for_move(6.0) == Severity.HIGH
    assert _severity_for_move(3.0) == Severity.MEDIUM
    assert _severity_for_move(1.0) == Severity.LOW


def test_weather_calm_returns_none():
    assert _severity_for_conditions(0.8, 15) is None


def test_weather_high_waves_escalate():
    assert _severity_for_conditions(4.2, 20) == Severity.HIGH
    assert _severity_for_conditions(6.5, 10) == Severity.CRITICAL


# ── Signal item factory ──────────────────────────────────────────────

def test_signal_item_dedup_key_stable_per_datum():
    a = build_signal_item(
        source="eia", canonical_id="eia://WCESTUS1/2026-07-03",
        headline="h", detail="d", severity=Severity.LOW,
        category=ImpactCategory.SUPPLY_DISRUPTION, region=Region.NORTH_AMERICA,
        relevance=0.6,
    )
    b = build_signal_item(
        source="eia", canonical_id="eia://WCESTUS1/2026-07-03",
        headline="different headline", detail="d2", severity=Severity.HIGH,
        category=ImpactCategory.SUPPLY_DISRUPTION, region=Region.NORTH_AMERICA,
        relevance=0.9,
    )
    # Same datum id -> same dedup key -> won't double-store across runs.
    assert a.article.dedup_key == b.article.dedup_key
    assert a.classified_by == "rule:eia"


# ── EIA adapter against a fake HTTP client ───────────────────────────

class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, payload):
        self._payload = payload

    async def get(self, *args, **kwargs):
        return _FakeResponse(self._payload)


def test_eia_adapter_builds_draw_signal():
    payload = {
        "response": {
            "data": [
                {"period": "2026-07-03", "series": "WCESTUS1", "value": "400000"},
                {"period": "2026-06-26", "series": "WCESTUS1", "value": "411000"},
            ]
        }
    }
    signal = EiaCrudeStocksSignal(api_key="fake")
    items = asyncio.run(signal.fetch(_FakeClient(payload)))  # type: ignore[arg-type]
    assert len(items) == 1
    item = items[0]
    # 400,000 - 411,000 = -11,000 kbbl = -11M bbl draw -> HIGH
    assert item.severity == Severity.HIGH
    assert "drew down" in item.article.title
    assert item.article.dedup_key  # canonical id hashed


def test_eia_disabled_without_key():
    assert EiaCrudeStocksSignal(api_key="").is_enabled() is False
    assert EiaCrudeStocksSignal(api_key="x").is_enabled() is True


# ── OpenSanctions adapter ────────────────────────────────────────────

class _FakeSearchClient:
    """Returns the same payload for every GET (both queries)."""

    def __init__(self, payload):
        self._payload = payload

    async def get(self, *args, **kwargs):
        return _FakeResponse(self._payload)


def test_opensanctions_emits_recent_vessel_as_high():
    from datetime import datetime, timezone
    from vorentice_agents.sources.signals.opensanctions import OpenSanctionsSignal

    today = datetime.now(timezone.utc).isoformat()
    payload = {
        "results": [
            {
                "id": "vessel-1",
                "caption": "MT SHADOW",
                "schema": "Vessel",
                "last_change": today,
                "datasets": ["us_ofac_sdn"],
                "properties": {"country": ["ru"]},
            },
            {
                "id": "old-1",
                "caption": "STALE CO",
                "schema": "Company",
                "last_change": "2020-01-01T00:00:00",
                "datasets": ["x"],
                "properties": {},
            },
        ]
    }
    signal = OpenSanctionsSignal(api_key="fake")
    items = asyncio.run(signal.fetch(_FakeSearchClient(payload)))  # type: ignore[arg-type]
    # The stale (2020) entity is filtered; the fresh vessel remains.
    captions = {i.article.title for i in items}
    assert any("MT SHADOW" in c for c in captions)
    assert not any("STALE CO" in c for c in captions)
    vessel = next(i for i in items if "MT SHADOW" in i.article.title)
    assert vessel.severity == Severity.HIGH
    assert vessel.region == Region.RUSSIA_CIS


def test_opensanctions_disabled_without_key():
    from vorentice_agents.sources.signals.opensanctions import OpenSanctionsSignal

    assert OpenSanctionsSignal(api_key="").is_enabled() is False
