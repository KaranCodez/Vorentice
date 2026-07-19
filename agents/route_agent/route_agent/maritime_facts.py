"""Curated maritime & trade-logistics knowledge base for the Constraint Engine.

This is the retrieval corpus behind the charter's "RAG Verification" stage.
Rather than a full vector store, it is a structured, auditable facts table keyed
by graph node id. Each entry carries the physical clearance metrics and
operational-friction indexes the charter asks us to validate a proposed path
against:

    channel_depth_m   — controlling depth of the strait/canal/approach (m)
    max_draft_m       — deepest vessel draft the passage reliably accepts (m)
    typical_dwell_d   — historical port/canal dwell or transit-queue time (days)
    treaty            — governing legal/treaty regime (compliance note)
    note              — one-line operational colour

Figures are open-source public-domain approximations for decision-support
framing, not navigational authority. A reference VLCC laden draft is ~22 m.
"""

from __future__ import annotations

# A fully-laden VLCC (2M bbl) sits at roughly this draft.
VLCC_LADEN_DRAFT_M = 22.0

FACTS: dict[str, dict] = {
    # ── Chokepoints ──────────────────────────────────────────────
    "hormuz": {
        "channel_depth_m": 60,
        "max_draft_m": 30,
        "typical_dwell_d": 0.5,
        "treaty": "UNCLOS transit passage (contested by Iran)",
        "note": "Two 2-nm traffic lanes; ~21 Mbbl/d — the world's #1 oil chokepoint.",
    },
    "bab_el_mandeb": {
        "channel_depth_m": 30,
        "max_draft_m": 25,
        "typical_dwell_d": 0.4,
        "treaty": "UNCLOS transit passage",
        "note": "Red Sea southern gate; exposed to Houthi missile/USV threat.",
    },
    "suez": {
        "channel_depth_m": 24,
        "max_draft_m": 20.1,
        "typical_dwell_d": 1.2,
        "treaty": "Constantinople Convention 1888 (free passage)",
        "note": "SUMED pipeline offloads deep VLCCs that exceed canal draft.",
    },
    "gibraltar": {
        "channel_depth_m": 300,
        "max_draft_m": 30,
        "typical_dwell_d": 0.2,
        "treaty": "UNCLOS transit passage",
        "note": "Deep, unrestricted; Atlantic–Mediterranean gateway.",
    },
    "malacca": {
        "channel_depth_m": 25,
        "max_draft_m": 20,
        "typical_dwell_d": 0.6,
        "treaty": "UNCLOS straits regime (littoral states)",
        "note": "Malaccamax draft cap ~20 m; piracy advisory zones persist.",
    },
    "sunda": {
        "channel_depth_m": 20,
        "max_draft_m": 16,
        "typical_dwell_d": 0.7,
        "treaty": "Indonesian archipelagic sea-lane",
        "note": "Shallow, strong currents; Malacca alternate for smaller hulls.",
    },
    "cape": {
        "channel_depth_m": 1000,
        "max_draft_m": 30,
        "typical_dwell_d": 0.0,
        "treaty": "High seas — no transit restriction",
        "note": "Open-ocean rounding; adds ~9–10 days vs Suez but never blocks.",
    },
    "panama": {
        "channel_depth_m": 18.3,
        "max_draft_m": 15.2,
        "typical_dwell_d": 1.5,
        "treaty": "Neutrality Treaty 1977",
        "note": "Neopanamax draft ~15 m — VLCCs cannot transit; drought queues.",
    },
    "singapore": {
        "channel_depth_m": 25,
        "max_draft_m": 20,
        "typical_dwell_d": 0.8,
        "treaty": "Port of Singapore / UNCLOS",
        "note": "World's largest bunkering hub; deep and well-served.",
    },
    # ── Indian refinery approaches (destinations) ────────────────
    "vadinar": {
        "channel_depth_m": 30,
        "max_draft_m": 27,
        "typical_dwell_d": 1.5,
        "treaty": "Indian port state control",
        "note": "SPM buoys handle VLCCs; Nayara/Kandla gateway.",
    },
    "jamnagar": {
        "channel_depth_m": 32,
        "max_draft_m": 28,
        "typical_dwell_d": 1.3,
        "treaty": "Indian port state control",
        "note": "World's largest refinery complex; deep SPM crude intake.",
    },
    "mumbai": {
        "channel_depth_m": 15,
        "max_draft_m": 12,
        "typical_dwell_d": 2.0,
        "treaty": "Indian port state control",
        "note": "Draft-limited; large crude via offshore SPM to BPCL/HPCL.",
    },
    "mangalore": {
        "channel_depth_m": 18,
        "max_draft_m": 16,
        "typical_dwell_d": 1.8,
        "treaty": "Indian port state control",
        "note": "MRPL / SPR cavern feed; SPM for VLCC discharge.",
    },
    "cochin": {
        "channel_depth_m": 16,
        "max_draft_m": 14.5,
        "typical_dwell_d": 1.9,
        "treaty": "Indian port state control",
        "note": "BPCL Kochi; deep-draft SPM commissioned offshore.",
    },
    "chennai": {
        "channel_depth_m": 19.2,
        "max_draft_m": 17,
        "typical_dwell_d": 2.2,
        "treaty": "Indian port state control",
        "note": "East-coast CPCL feed; Bay of Bengal approach.",
    },
    "paradip": {
        "channel_depth_m": 20,
        "max_draft_m": 18,
        "typical_dwell_d": 2.0,
        "treaty": "Indian port state control",
        "note": "IOCL Paradip; deepest east-coast crude terminal + SPR.",
    },
    # ── Sources (load-port clearance) ────────────────────────────
    "ras_tanura": {
        "channel_depth_m": 27,
        "max_draft_m": 24,
        "typical_dwell_d": 1.0,
        "treaty": "Saudi port authority",
        "note": "Saudi Aramco's primary sea island; VLCC loading berths.",
    },
    "fujairah": {
        "channel_depth_m": 30,
        "max_draft_m": 26,
        "typical_dwell_d": 1.0,
        "treaty": "UAE port authority",
        "note": "Outside Hormuz on the Gulf of Oman — the strategic bypass.",
    },
}

# Fallback used for open-ocean waypoints and any un-catalogued node.
_OPEN_WATER = {
    "channel_depth_m": 2000,
    "max_draft_m": 30,
    "typical_dwell_d": 0.0,
    "treaty": "High seas",
    "note": "Open-ocean navigation leg.",
}


def facts_for(node_id: str) -> dict:
    """Retrieve the KB record for a node (open-water default if absent)."""
    return FACTS.get(node_id, _OPEN_WATER)
