"""Route Agent engine tests — topology, routing, constraints, impact, and the
end-to-end pipeline across the charter's key disruption scenarios."""

from route_agent.classification import (
    classify_live_events,
    classify_manual,
    resolve_chokepoint,
)
from route_agent.constraints import verify_path
from route_agent.engine import build_topology, run_pipeline
from route_agent.graph_data import NODES, haversine_km
from route_agent.pathfinding import compute_route


# ── Graph / geometry ────────────────────────────────────────────
def test_haversine_known_distance():
    # London ↔ Paris ≈ 344 km
    d = haversine_km(-0.13, 51.51, 2.35, 48.85)
    assert 330 < d < 360


def test_topology_shape_and_baseline():
    topo = build_topology()
    assert len(topo["nodes"]) == len(NODES)
    assert topo["edges"]
    # India's baseline artery runs Ras Tanura → Hormuz → … → Jamnagar.
    assert topo["baseline_path"][0] == "ras_tanura"
    assert "hormuz" in topo["baseline_path"]
    assert topo["baseline_path"][-1] == "jamnagar"


# ── Routing ─────────────────────────────────────────────────────
def test_baseline_uses_hormuz():
    r = compute_route({})
    assert r.feasible
    assert "hormuz" in r.node_path
    assert r.distance_km > 0


def test_hormuz_block_reroutes_to_fujairah_bypass():
    r = compute_route({"hormuz": "blocked"})
    assert r.feasible
    assert "hormuz" not in r.node_path
    assert r.source_id == "fujairah"  # the Gulf-of-Oman bypass


def test_gulf_severed_switches_source_and_adds_days():
    baseline = compute_route({})
    r = compute_route({"hormuz": "blocked", "fujairah": "blocked"})
    assert r.feasible
    # Gulf fully cut → must pull barrels from outside the Gulf.
    assert NODES[r.source_id].region not in ("persian_gulf", "gulf_of_oman")
    assert r.transit_days > baseline.transit_days


def test_infeasible_when_all_sources_blocked():
    statuses = {nid: "blocked" for nid, n in NODES.items() if n.role == "source"}
    r = compute_route(statuses)
    assert not r.feasible


# ── Constraints (RAG) ───────────────────────────────────────────
def test_constraint_flags_suez_draft():
    report = verify_path(["novorossiysk", "suez", "arabian_sea", "jamnagar"])
    assert not report.draft_ok          # Suez 20.1 m < 22 m laden VLCC
    assert report.min_draft_node == "suez"
    assert any("Suez" in w for w in report.warnings)
    assert report.references             # retrieval trace populated


# ── Classification ──────────────────────────────────────────────
def test_resolve_chokepoint_aliases():
    assert resolve_chokepoint("Strait of Hormuz") == "hormuz"
    assert resolve_chokepoint("Bab el-Mandeb") == "bab_el_mandeb"
    assert resolve_chokepoint("Cape of Good Hope") == "cape"
    assert resolve_chokepoint("nowhere") is None


def test_kinetic_event_classifies_as_maritime():
    events = [
        {
            "chokepoints": ["Strait of Hormuz"],
            "event_summary": "Missile strike closes the strait",
            "criticality": "Critical",
            "trade_impact": "insurance premiums spike",
            "category": "Armed conflict",
        }
    ]
    disruptions = classify_live_events(events)
    assert len(disruptions) == 1
    d = disruptions[0]
    assert d.node_id == "hormuz"
    assert d.status == "blocked"
    assert d.vector == "maritime_chokepoint"  # kinetic dominates the finance cue


def test_classify_manual_status():
    d = classify_manual("suez", "blocked")
    assert d.node_id == "suez"
    assert d.status == "blocked"
    assert d.source == "manual"


# ── End-to-end pipeline ─────────────────────────────────────────
def test_pipeline_hormuz_plus_fujairah_payload():
    disruptions = [
        classify_manual("hormuz", "blocked"),
        classify_manual("fujairah", "blocked"),
    ]
    payload = run_pipeline(disruptions, mode="sandbox")
    assert payload["feasible"]
    # two disrupted nodes render red
    reds = [nid for nid, st in payload["node_states"].items() if st == "red"]
    assert set(reds) == {"hormuz", "fujairah"}
    # the surviving corridor is green and reaches an Indian refinery
    assert payload["active_path"][-1] in ("jamnagar", "vadinar", "mumbai", "mangalore", "cochin", "chennai", "paradip")
    # broken green legs adjacent to Hormuz turn red
    assert payload["broken_edges"]
    # impact + floater populated (un-hardcoded arrays)
    assert payload["impact"]["added_days"] > 0
    assert payload["floater"]["asset_exposure"]
    assert payload["floater"]["strategic_offset"]
    assert payload["floater"]["metrics"]
    # deep-dive keyed per disrupted node
    assert set(payload["deep_dive"]) == {"hormuz", "fujairah"}


def test_pipeline_nominal_when_no_disruptions():
    payload = run_pipeline([], mode="live")
    assert payload["feasible"]
    assert not payload["disrupted"]
    assert not payload["broken_edges"]
    assert payload["floater"]["vector"] == "none"
    assert "hormuz" in payload["active_path"]  # baseline artery intact
