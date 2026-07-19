"""The dynamic six-stage pipeline that binds the Route Agent together.

    Disruption ─▶ Classify ─▶ Route ─▶ Constraint(RAG) ─▶ Impact ─▶ (payload)

`build_topology` serves the static-ish graph to the frontend once; `run_pipeline`
takes a set of classified disruptions (live or manual), recomputes the optimal
corridor, validates it, quantifies the domestic impact, and assembles a single
open payload the UI renderer paints into empty containers.
"""

from __future__ import annotations

from datetime import datetime, timezone

from route_agent.classification import Disruption
from route_agent.constraints import verify_path
from route_agent.graph_data import (
    EDGES,
    NODES,
    edge_public,
    node_public,
)
from route_agent.impact import compute_impact
from route_agent.pathfinding import compute_route


# ──────────────────────────────────────────────────────────────────
# Topology (served once to the frontend)
# ──────────────────────────────────────────────────────────────────
def build_topology() -> dict:
    """Nodes, edges, and the clean baseline active corridor to India."""
    baseline = compute_route({})
    return {
        "nodes": [node_public(n) for n in NODES.values()],
        "edges": [edge_public(e) for e in EDGES],
        "baseline_path": baseline.node_path,
        "baseline": {
            "source": baseline.source_id,
            "refinery": baseline.refinery_id,
            "distance_km": baseline.distance_km,
            "transit_days": baseline.transit_days,
        },
    }


def _path_edges(path: list[str]) -> set[frozenset[str]]:
    return {frozenset((a, b)) for a, b in zip(path, path[1:])}  # noqa: B905


# ──────────────────────────────────────────────────────────────────
# Pipeline
# ──────────────────────────────────────────────────────────────────
def run_pipeline(
    disruptions: list[Disruption],
    mode: str,
    brent_usd: float | None = None,
) -> dict:
    """Run classify→route→constraint→impact and assemble the render payload."""
    statuses = {d.node_id: d.status for d in disruptions}

    # Stage 3 — Routing (baseline vs surviving corridor)
    baseline = compute_route({})
    reroute = compute_route(statuses)

    # Stage 4 — Constraint (RAG verification of the surviving corridor)
    constraints = verify_path(reroute.node_path)

    # Stage 5 — Impact (domestic downstream deltas)
    impact = compute_impact(baseline, reroute, constraints, statuses, brent_usd)

    # Stage 6 — Render state assembly
    active = set(reroute.node_path)
    disrupted_ids = set(statuses)

    node_states: dict[str, str] = {}
    for nid in NODES:
        if nid in disrupted_ids:
            node_states[nid] = "red"
        elif nid in active:
            node_states[nid] = "green"
        else:
            node_states[nid] = "blue"

    # Broken edges = baseline legs, adjacent to a disruption, dropped by reroute.
    base_edges = _path_edges(baseline.node_path)
    new_edges = _path_edges(reroute.node_path)
    broken_edges: list[dict] = []
    for e in base_edges - new_edges:
        a, b = tuple(e)
        if a in disrupted_ids or b in disrupted_ids or not reroute.feasible:
            broken_edges.append({"a": a, "b": b})

    # Per-node spark + deep-dive (on-map interaction protocol)
    sparks = {d.node_id: d.spark for d in disruptions}
    deep_dive = {
        d.node_id: {
            "header": d.header,
            "vector": d.vector,
            "spark": d.spark,
            "status": d.status,
            "criticality": d.criticality,
            "region": d.region,
            "alt_source": impact.new_source,
            "alt_source_name": _name(impact.new_source),
            "min_draft_m": constraints.min_draft_m,
            "min_draft_node": _name(constraints.min_draft_node),
            "added_days": impact.added_days,
            "downstream": [x["asset"] for x in impact.asset_exposure],
        }
        for d in disruptions
    }

    # Dynamic alert header (Classification Engine → floater)
    if disruptions:
        worst = max(
            disruptions,
            key=lambda d: {"elevated": 0, "high_risk": 1, "blocked": 2}[d.status],
        )
        header = worst.header
        vector = worst.vector
    else:
        header = "All corridors nominal"
        vector = "none"

    return {
        "mode": mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "feasible": reroute.feasible,
        "active_path": reroute.node_path,
        "baseline_path": baseline.node_path,
        "disrupted": [d.__dict__ for d in disruptions],
        "node_states": node_states,
        "broken_edges": broken_edges,
        "sparks": sparks,
        "deep_dive": deep_dive,
        "route": {
            "source": reroute.source_id,
            "source_name": _name(reroute.source_id),
            "refinery": reroute.refinery_id,
            "refinery_name": _name(reroute.refinery_id),
            "distance_km": reroute.distance_km,
            "transit_days": reroute.transit_days,
        },
        "constraints": {
            "draft_ok": constraints.draft_ok,
            "min_draft_m": constraints.min_draft_m,
            "min_draft_node": _name(constraints.min_draft_node),
            "dwell_days": constraints.dwell_days,
            "clearance_notes": constraints.clearance_notes,
            "warnings": constraints.warnings,
            "references": constraints.references,
        },
        "impact": {
            "reroute_required": impact.reroute_required,
            "added_days": impact.added_days,
            "added_km": impact.added_km,
            "landed_cost_uplift_usd_bbl": impact.landed_cost_uplift_usd_bbl,
            "retail_pump_pct": impact.retail_pump_pct,
        },
        "floater": {
            "header": header,
            "vector": vector,
            "asset_exposure": impact.asset_exposure,
            "strategic_offset": impact.strategic_offset,
            "metrics": impact.metrics,
        },
    }


def _name(nid: str | None) -> str:
    return NODES[nid].name if nid in NODES else (nid or "—")
