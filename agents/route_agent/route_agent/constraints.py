"""Constraint Engine — RAG verification of a proposed corridor.

Retrieves the physical-clearance and operational-friction facts for every node
on a candidate path (from ``maritime_facts``) and validates the path against the
two checks the charter names:

  * Physical Clearance — a reference laden VLCC draft against each passage's
    controlling depth / max accepted draft. A violation means the corridor
    cannot take the largest hulls (flagged, not silently dropped).
  * Operational Friction — accumulated historical dwell/queue time across the
    corridor, plus any treaty-compliance note worth surfacing.

The output is a compact, serialisable verification the Impact Engine and the UI
floater consume — no LLM call is required for the deterministic checks, keeping
the constraint stage fast and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from route_agent.graph_data import NODES
from route_agent.maritime_facts import VLCC_LADEN_DRAFT_M, facts_for


@dataclass
class ConstraintReport:
    draft_ok: bool
    min_draft_node: str | None          # tightest passage on the corridor
    min_draft_m: float
    dwell_days: float                    # summed operational friction
    clearance_notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    references: list[dict] = field(default_factory=list)  # retrieved KB rows


def verify_path(node_path: list[str]) -> ConstraintReport:
    """Validate a corridor against the maritime facts KB."""
    if not node_path:
        return ConstraintReport(
            draft_ok=False,
            min_draft_node=None,
            min_draft_m=0.0,
            dwell_days=0.0,
            warnings=["No feasible corridor to validate."],
        )

    min_draft = float("inf")
    min_node: str | None = None
    dwell = 0.0
    notes: list[str] = []
    warnings: list[str] = []
    refs: list[dict] = []

    for nid in node_path:
        f = facts_for(nid)
        name = NODES[nid].name if nid in NODES else nid
        dwell += float(f.get("typical_dwell_d", 0.0))

        max_draft = float(f.get("max_draft_m", 30.0))
        if max_draft < min_draft:
            min_draft = max_draft
            min_node = nid

        # Retrieval trace — what the constraint engine "read" for this node.
        refs.append(
            {
                "node": nid,
                "name": name,
                "max_draft_m": f.get("max_draft_m"),
                "channel_depth_m": f.get("channel_depth_m"),
                "typical_dwell_d": f.get("typical_dwell_d"),
                "treaty": f.get("treaty"),
                "note": f.get("note"),
            }
        )

        if max_draft < VLCC_LADEN_DRAFT_M:
            warnings.append(
                f"{name}: max draft {max_draft:.1f} m < laden VLCC "
                f"{VLCC_LADEN_DRAFT_M:.0f} m — requires part-loading, "
                f"lightering, or a Suezmax/Aframax substitution."
            )
        treaty = f.get("treaty")
        if treaty and "contested" in treaty.lower():
            notes.append(f"{name}: transit right {treaty}.")

    draft_ok = min_draft >= VLCC_LADEN_DRAFT_M
    tightest = NODES[min_node].name if min_node in NODES else (min_node or "n/a")
    notes.insert(
        0,
        f"Tightest passage: {tightest} at {min_draft:.1f} m controlling draft.",
    )

    return ConstraintReport(
        draft_ok=draft_ok,
        min_draft_node=min_node,
        min_draft_m=round(min_draft, 1),
        dwell_days=round(dwell, 1),
        clearance_notes=notes,
        warnings=warnings,
        references=refs,
    )
