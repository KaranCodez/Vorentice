"""Impact Engine — domestic downstream deltas of a route reconfiguration.

Compares the surviving corridor against the clean baseline corridor and
quantifies what it does to Indian assets:

  * transit delta   — extra sea-days and distance the reroute imposes
  * asset exposure  — Indian refineries facing supply degradation / starvation
  * strategic offset— alternative sources & domestic workarounds
  * economic friction — freight/demurrage uplift → an approximate landed-cost
    and retail-pump proxy, using live Brent when the caller supplies it

Everything is returned as open, loopable arrays so the charter's "un-hardcoded"
UI floater can render whatever the engine emits without static fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from route_agent.constraints import ConstraintReport
from route_agent.graph_data import NODES, PRIMARY_REFINERY
from route_agent.pathfinding import RouteResult

# Approximate nameplate crude capacity (kbd) for exposure weighting.
REFINERY_CAPACITY_KBD: dict[str, int] = {
    "jamnagar": 1240,
    "vadinar": 405,
    "mumbai": 240,
    "mangalore": 300,
    "cochin": 310,
    "chennai": 210,
    "paradip": 300,
}

# India lands the large majority of its crude through the Gulf via Hormuz.
# A Gulf-severing disruption exposes the west-coast complexes first.
WEST_COAST = {"jamnagar", "vadinar", "mumbai", "mangalore"}

# Rough VLCC voyage economics for friction framing.
_VLCC_CARGO_BBL = 2_000_000
_DAILY_CHARTER_USD = 55_000        # laden day rate incl. bunkers (order-of-mag)


@dataclass
class Metric:
    label: str
    value: str
    unit: str = ""
    delta: str = ""            # signed change vs baseline, e.g. "+9.4 days"
    tone: str = "neutral"      # "critical" | "warn" | "neutral" | "good"


@dataclass
class ImpactReport:
    reroute_required: bool
    added_days: float
    added_km: float
    baseline_source: str | None
    new_source: str | None
    baseline_refinery: str | None
    new_refinery: str | None
    landed_cost_uplift_usd_bbl: float
    retail_pump_pct: float
    asset_exposure: list[dict] = field(default_factory=list)
    strategic_offset: list[dict] = field(default_factory=list)
    metrics: list[dict] = field(default_factory=list)


def _name(nid: str | None) -> str:
    return NODES[nid].name if nid in NODES else (nid or "—")


def compute_impact(
    baseline: RouteResult,
    reroute: RouteResult,
    constraints: ConstraintReport,
    statuses: dict[str, str],
    brent_usd: float | None = None,
) -> ImpactReport:
    """Derive downstream Indian asset & economic deltas for the reroute."""
    added_km = round(max(0.0, reroute.distance_km - baseline.distance_km), 1)
    added_days = round(max(0.0, reroute.transit_days - baseline.transit_days), 2)
    source_switched = (
        reroute.feasible
        and baseline.feasible
        and reroute.source_id != baseline.source_id
    )
    reroute_required = source_switched or added_days > 0.01 or not reroute.feasible

    # ── Economic friction ────────────────────────────────────────
    # Extra charter days spread across the cargo → $/bbl freight uplift.
    freight_uplift = (
        round((added_days * _DAILY_CHARTER_USD) / _VLCC_CARGO_BBL, 2)
        if added_days > 0
        else 0.0
    )
    # Draft-limited corridors force smaller hulls / lightering — a surcharge.
    draft_surcharge = 0.0 if constraints.draft_ok else 0.9
    landed_uplift = round(freight_uplift + draft_surcharge, 2)
    # Landed-cost delta as a share of crude → crude is ~⅓ of pump price in India
    # (rest is duties/taxes), so pump sensitivity ≈ uplift/basket × 0.33.
    basket = (brent_usd - 3.0) if brent_usd else 78.0
    retail_pump_pct = (
        round((landed_uplift / basket) * 0.33 * 100, 2) if basket > 0 else 0.0
    )

    # ── Asset exposure (Indian facilities under degradation) ─────
    exposure: list[dict] = []
    gulf_cut = any(
        statuses.get(n) == "blocked" for n in ("hormuz",)
    ) or (source_switched and NODES.get(baseline.source_id or "", None) is not None
          and NODES[baseline.source_id].region in ("persian_gulf", "gulf_of_oman")
          and reroute.source_id is not None
          and NODES[reroute.source_id].region not in ("persian_gulf", "gulf_of_oman"))

    at_risk = WEST_COAST if gulf_cut else set()
    # The refinery that actually lost its baseline corridor is always exposed.
    if source_switched and baseline.refinery_id:
        at_risk = at_risk | {baseline.refinery_id}
    for rid in sorted(at_risk, key=lambda r: -REFINERY_CAPACITY_KBD.get(r, 0)):
        cap = REFINERY_CAPACITY_KBD.get(rid, 0)
        if not reroute.feasible:
            sev, drop = "critical", "supply severed — no feasible corridor"
        elif added_days >= 7:
            sev, drop = "critical", f"+{added_days:.0f}d transit — inventory draw risk"
        elif added_days >= 3:
            sev, drop = "warn", f"+{added_days:.1f}d transit — schedule slip"
        else:
            sev, drop = "warn", "reroute pressure on feed reliability"
        exposure.append(
            {
                "asset": _name(rid),
                "capacity_kbd": cap,
                "severity": sev,
                "detail": drop,
            }
        )

    # ── Strategic offset (remedies) ──────────────────────────────
    offsets: list[dict] = []
    if source_switched:
        offsets.append(
            {
                "action": f"Substitute supply: {_name(reroute.source_id)}",
                "detail": f"Redirect intake from {_name(baseline.source_id)} to "
                f"{_name(reroute.source_id)} via the surviving corridor.",
                "kind": "alt_source",
            }
        )
    if not constraints.draft_ok:
        offsets.append(
            {
                "action": "Lighter / part-load VLCCs",
                "detail": f"Tightest passage {_name(constraints.min_draft_node)} "
                f"caps draft at {constraints.min_draft_m:.1f} m; split cargoes or "
                f"deploy Suezmax hulls.",
                "kind": "ops",
            }
        )
    if added_days >= 5:
        offsets.append(
            {
                "action": "Draw down Strategic Petroleum Reserve",
                "detail": f"Bridge the {added_days:.0f}-day transit gap from SPR "
                f"caverns (Mangalore/Padur/Vizag) to hold refinery run-rates.",
                "kind": "reserve",
            }
        )
    if gulf_cut:
        offsets.append(
            {
                "action": "Activate Fujairah / Atlantic-basin diversification",
                "detail": "Lean on the Gulf-of-Oman bypass and West-African / US "
                "barrels while the Hormuz corridor is degraded.",
                "kind": "diversify",
            }
        )
    if not offsets:
        offsets.append(
            {
                "action": "Hold current sourcing",
                "detail": "Primary corridor intact — no substitution required.",
                "kind": "steady",
            }
        )

    # ── Dynamic metrics array ────────────────────────────────────
    metrics: list[Metric] = [
        Metric(
            "Transit penalty",
            f"{reroute.transit_days:.1f}" if reroute.feasible else "—",
            "days",
            delta=f"+{added_days:.1f} days" if added_days > 0 else "no change",
            tone="critical" if added_days >= 7 else "warn" if added_days > 0 else "good",
        ),
        Metric(
            "Corridor distance",
            f"{reroute.distance_km:,.0f}" if reroute.feasible else "—",
            "km",
            delta=f"+{added_km:,.0f} km" if added_km > 0 else "no change",
            tone="warn" if added_km > 0 else "good",
        ),
        Metric(
            "Landed-cost friction",
            f"${landed_uplift:.2f}",
            "/bbl",
            delta="freight + draft surcharge" if landed_uplift else "nil",
            tone="warn" if landed_uplift >= 0.5 else "neutral",
        ),
        Metric(
            "Retail pump proxy",
            f"+{retail_pump_pct:.2f}",
            "%",
            delta="est. downstream pass-through",
            tone="warn" if retail_pump_pct >= 1.0 else "neutral",
        ),
        Metric(
            "Supply source",
            _name(reroute.source_id),
            "",
            delta=f"was {_name(baseline.source_id)}" if source_switched else "unchanged",
            tone="critical" if source_switched else "good",
        ),
    ]

    return ImpactReport(
        reroute_required=reroute_required,
        added_days=added_days,
        added_km=added_km,
        baseline_source=baseline.source_id,
        new_source=reroute.source_id,
        baseline_refinery=baseline.refinery_id or PRIMARY_REFINERY,
        new_refinery=reroute.refinery_id,
        landed_cost_uplift_usd_bbl=landed_uplift,
        retail_pump_pct=retail_pump_pct,
        asset_exposure=exposure,
        strategic_offset=offsets,
        metrics=[m.__dict__ for m in metrics],
    )
