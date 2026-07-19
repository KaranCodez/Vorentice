"""Classification Engine — categorise incoming disruptions into threat vectors.

The charter wants events classified WITHOUT hard-coded per-event lists into a
small set of vectors, then mapped onto concrete graph nodes so the Routing
Engine can act. We do this deterministically from the structured signal the News
Agent already produces (critical events tagged with chokepoints, criticality,
trade-impact, region) and from manual sandbox clicks. The mapping — not the
events — is the only static part, which keeps the pipeline un-hardcoded per the
brief.

Threat vectors (charter §2.2):
    maritime_chokepoint    — kinetic/physical blockade of a waterway
    domestic_infrastructure— internal pipeline / processing / inland link failure
    financial_settlement   — sanctions / policy freeze / transaction restriction
    commodity_input        — climate / macro-market intake shock
"""

from __future__ import annotations

from dataclasses import dataclass

from route_agent.graph_data import CHOKEPOINT_IDS, NODES

# Alias fragments → node id. Matched as case-insensitive substrings, longest
# first, against a chokepoint name string coming from the News Agent.
_CHOKEPOINT_ALIASES: list[tuple[str, str]] = [
    ("cape of good hope", "cape"),
    ("good hope", "cape"),
    ("bab-el-mandeb", "bab_el_mandeb"),
    ("bab el-mandeb", "bab_el_mandeb"),
    ("bab el mandeb", "bab_el_mandeb"),
    ("mandeb", "bab_el_mandeb"),
    ("hormuz", "hormuz"),
    ("suez", "suez"),
    ("gibraltar", "gibraltar"),
    ("malacca", "malacca"),
    ("sunda", "sunda"),
    ("panama", "panama"),
    ("singapore", "singapore"),
]

# Kinetic waterway cues checked FIRST — a physical blockade of a strait is a
# maritime_chokepoint event even when the trade-impact text also mentions the
# insurance/premium fallout it triggers.
_MARITIME_KEYWORDS: tuple[str, ...] = (
    "strike", "missile", "drone", "attack", "blockade", "closure", "closed",
    "naval", "mine", "seized", "seizure", "tanker", "kinetic", "war", "houthi",
    "shelling", "assault", "clash", "hijack", "boarded", "warship",
)

_VECTOR_KEYWORDS: dict[str, tuple[str, ...]] = {
    "financial_settlement": (
        "sanction", "sanctioned", "embargo", "insurance", "premium",
        "settlement", "payment", "banking", "policy freeze", "tariff",
        "price cap", "financ", "unviable", "uneconomic",
    ),
    "commodity_input": (
        "weather", "storm", "cyclone", "monsoon", "drought", "climate",
        "sea-state", "swell", "opec", "quota", "output cut", "production cut",
        "harvest", "shortage",
    ),
    "domestic_infrastructure": (
        "pipeline", "refinery fire", "outage", "processing", "inland",
        "rail", "terminal fault", "power", "domestic",
    ),
}


@dataclass
class Disruption:
    node_id: str
    status: str            # "blocked" | "high_risk" | "elevated"
    vector: str            # one of the four threat vectors
    spark: str             # short "why is this broken" for the hover tooltip
    header: str            # dynamic alert header for the floater
    source: str            # "live" | "manual"
    criticality: str = ""  # original news criticality if any
    region: str = ""


def resolve_chokepoint(name: str) -> str | None:
    """Map a free-text chokepoint name to a graph node id."""
    if not name:
        return None
    low = name.lower()
    if low in NODES:  # already an id
        return low
    for frag, nid in _CHOKEPOINT_ALIASES:
        if frag in low:
            return nid
    return None


def _classify_vector(text: str) -> str:
    low = text.lower()
    # Kinetic waterway cues dominate — a strait under attack is a chokepoint
    # event regardless of the financial language around it.
    if any(k in low for k in _MARITIME_KEYWORDS):
        return "maritime_chokepoint"
    for vector, kws in _VECTOR_KEYWORDS.items():
        if any(k in low for k in kws):
            return vector
    # Default: a waterway named + no cue ⇒ kinetic chokepoint.
    return "maritime_chokepoint"


def _status_from(criticality: str, trade_impact: str) -> str:
    c = (criticality or "").lower()
    t = (trade_impact or "").lower()
    econ_fail = any(
        k in t for k in ("unviable", "uneconomic", "premium", "insurance", "prohibitive")
    )
    if "critical" in c or "blocked" in c or "closure" in t or "closed" in t:
        return "blocked"
    if econ_fail:
        return "high_risk"  # "Economically Viable Failure" — passable but punished
    if "high" in c or "severe" in c:
        return "high_risk"
    return "elevated"


def classify_live_events(critical_events: list[dict]) -> list[Disruption]:
    """Turn News-Agent critical events into node-level disruptions.

    Each event may name several chokepoints; every resolvable one becomes a
    disruption. The worst status wins if the same node appears twice.
    """
    by_node: dict[str, Disruption] = {}
    severity_rank = {"elevated": 0, "high_risk": 1, "blocked": 2}

    for ev in critical_events:
        chokepoints = ev.get("chokepoints") or []
        summary = ev.get("event_summary") or ev.get("summary") or ""
        criticality = ev.get("criticality") or ""
        trade_impact = ev.get("trade_impact") or ""
        region = ev.get("region") or "Global"
        category = ev.get("category") or ev.get("segment") or ""

        status = _status_from(criticality, trade_impact)
        vector = _classify_vector(f"{category} {summary} {trade_impact}")

        for cp in chokepoints:
            nid = resolve_chokepoint(cp)
            if not nid:
                continue
            spark = summary.strip()[:180] or f"{criticality} disruption reported."
            header = f"{NODES[nid].name} — {criticality or 'Disruption'}".strip()
            cand = Disruption(
                node_id=nid,
                status=status,
                vector=vector,
                spark=spark,
                header=header,
                source="live",
                criticality=criticality,
                region=region,
            )
            prev = by_node.get(nid)
            if prev is None or severity_rank[status] > severity_rank[prev.status]:
                by_node[nid] = cand

    return list(by_node.values())


def classify_manual(node_id: str, status: str = "blocked") -> Disruption:
    """Classify a manual war-gaming click on a node."""
    node = NODES.get(node_id)
    name = node.name if node else node_id
    vector = "maritime_chokepoint" if node_id in CHOKEPOINT_IDS else "domestic_infrastructure"
    if node and node.role == "source":
        vector = "financial_settlement"
    return Disruption(
        node_id=node_id,
        status=status,
        vector=vector,
        spark=f"Manual war-game: {name} forced to '{status}'.",
        header=f"{name} — Simulated Disruption",
        source="manual",
        region=node.region if node else "",
    )
