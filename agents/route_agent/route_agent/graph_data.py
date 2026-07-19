"""Authoritative network topology for the Route Agent.

The Route Agent models the global crude-supply network as an *extensible*
weighted graph — NOT static ship-tracking data. This module is the single
source of truth for both the pathfinding engine (backend) and the visualizer
(frontend fetches it via GET /api/route/topology), so node ids and coordinates
never drift between the two.

Design notes
------------
* Nodes carry a ``role`` — ``source`` (crude origin), ``chokepoint``,
  ``waypoint`` (open-ocean navigation), or ``refinery`` (an Indian import
  terminal / destination).
* Edges are undirected shipping lanes. We only author the *adjacency*; the
  weight of every edge is the great-circle (haversine) distance in km, computed
  once at import. That keeps the data honest — a lane is only "shorter" if it is
  geographically shorter.
* ``source`` nodes carry a ``premium_km`` — a synthetic distance penalty that
  encodes commercial preference (Gulf crude is closest/cheapest for India, so a
  low premium; Atlantic-basin barrels cost more to land). The router adds this
  to the path cost so the baseline optimum is the Gulf → Hormuz artery and a
  reroute degrades gracefully to the next-cheapest source when the Gulf is cut.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# ──────────────────────────────────────────────────────────────────
# Node / edge datamodel
# ──────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Node:
    id: str
    name: str
    lon: float
    lat: float
    role: str  # "source" | "chokepoint" | "waypoint" | "refinery"
    region: str
    country: str = ""
    premium_km: float = 0.0  # source-only commercial preference penalty


@dataclass(frozen=True)
class Edge:
    a: str
    b: str
    km: float = field(default=0.0)  # filled at import via haversine


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance between two lon/lat points, in kilometres."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    h = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    )
    return round(2 * r * math.asin(math.sqrt(h)), 1)


# ──────────────────────────────────────────────────────────────────
# Nodes
# ──────────────────────────────────────────────────────────────────
_NODES: list[Node] = [
    # ── Crude sources ────────────────────────────────────────────
    Node("ras_tanura", "Ras Tanura", 50.15, 26.64, "source", "persian_gulf", "Saudi Arabia", premium_km=0),
    Node("basra", "Basra Oil Terminal", 48.80, 29.70, "source", "persian_gulf", "Iraq", premium_km=150),
    Node("kharg", "Kharg Island", 50.32, 29.23, "source", "persian_gulf", "Iran", premium_km=400),
    Node("mina_al_ahmadi", "Mina al-Ahmadi", 48.15, 29.07, "source", "persian_gulf", "Kuwait", premium_km=180),
    # Fujairah bypasses Hormuz on the Gulf of Oman, but its pipeline capacity is
    # a fraction of Hormuz throughput — a fallback, not the baseline artery. The
    # high premium keeps the primary corridor on Ras Tanura → Hormuz.
    Node("fujairah", "Fujairah", 56.35, 25.12, "source", "gulf_of_oman", "UAE", premium_km=1500),
    Node("novorossiysk", "Novorossiysk", 37.80, 44.72, "source", "black_sea", "Russia", premium_km=1400),
    Node("primorsk", "Primorsk", 28.60, 60.35, "source", "baltic", "Russia", premium_km=2600),
    Node("bonny", "Bonny Terminal", 7.17, 4.45, "source", "west_africa", "Nigeria", premium_km=900),
    Node("luanda", "Luanda", 13.23, -8.78, "source", "west_africa", "Angola", premium_km=1000),
    Node("houston", "Houston / US Gulf", -94.90, 29.30, "source", "us_gulf", "United States", premium_km=2200),
    Node("jose", "Jose Terminal", -64.80, 10.08, "source", "americas", "Venezuela", premium_km=2400),
    # ── Chokepoints ──────────────────────────────────────────────
    Node("hormuz", "Strait of Hormuz", 56.50, 26.40, "chokepoint", "persian_gulf"),
    Node("bab_el_mandeb", "Bab el-Mandeb", 43.40, 12.60, "chokepoint", "red_sea"),
    Node("suez", "Suez Canal", 32.50, 30.20, "chokepoint", "mediterranean"),
    Node("gibraltar", "Strait of Gibraltar", -5.60, 35.90, "chokepoint", "atlantic"),
    Node("malacca", "Malacca Strait", 100.50, 3.20, "chokepoint", "se_asia"),
    Node("sunda", "Sunda Strait", 105.90, -5.90, "chokepoint", "se_asia"),
    Node("cape", "Cape of Good Hope", 18.90, -34.80, "chokepoint", "south_atlantic"),
    Node("panama", "Panama Canal", -79.60, 9.10, "chokepoint", "americas"),
    Node("singapore", "Singapore", 103.80, 1.35, "chokepoint", "se_asia"),
    # ── Open-ocean waypoints ─────────────────────────────────────
    Node("gulf_of_oman", "Gulf of Oman", 58.50, 24.50, "waypoint", "arabian_sea"),
    Node("arabian_sea", "Arabian Sea", 63.00, 20.00, "waypoint", "arabian_sea"),
    Node("gulf_of_aden", "Gulf of Aden", 48.00, 12.50, "waypoint", "red_sea"),
    Node("red_sea_s", "Southern Red Sea", 40.00, 18.00, "waypoint", "red_sea"),
    Node("red_sea_n", "Northern Red Sea", 34.00, 27.50, "waypoint", "red_sea"),
    Node("e_mediterranean", "Eastern Mediterranean", 30.00, 33.50, "waypoint", "mediterranean"),
    Node("w_mediterranean", "Western Mediterranean", 10.00, 38.00, "waypoint", "mediterranean"),
    Node("n_atlantic", "North Atlantic", -30.00, 35.00, "waypoint", "atlantic"),
    Node("s_atlantic", "South Atlantic", -5.00, -25.00, "waypoint", "atlantic"),
    Node("mozambique_ch", "Mozambique Channel", 40.00, -22.00, "waypoint", "indian_ocean"),
    Node("s_indian_ocean", "Southern Indian Ocean", 55.00, -25.00, "waypoint", "indian_ocean"),
    Node("bay_of_bengal", "Bay of Bengal", 88.00, 12.00, "waypoint", "bay_of_bengal"),
    Node("andaman_sea", "Andaman Sea", 95.00, 8.00, "waypoint", "bay_of_bengal"),
    # Southern approach round Sri Lanka — the open-sea lane that lets Gulf/Cape
    # crude reach the east coast (Chennai/Paradip) WITHOUT transiting the
    # west-coast refinery chain. Without it, blocking the west coast wrongly
    # severs all Indian supply.
    Node("sri_lanka_s", "South of Sri Lanka", 80.50, 4.50, "waypoint", "bay_of_bengal"),
    Node("baltic_sea", "Baltic Sea", 18.00, 56.00, "waypoint", "baltic"),
    Node("black_sea", "Black Sea", 34.00, 43.00, "waypoint", "black_sea"),
    Node("gulf_of_mexico", "Gulf of Mexico", -90.00, 25.00, "waypoint", "americas"),
    Node("caribbean", "Caribbean Sea", -72.00, 14.00, "waypoint", "americas"),
    # ── Indian refineries (destinations) ─────────────────────────
    Node("vadinar", "Vadinar", 69.70, 22.30, "refinery", "india_west", "India"),
    Node("jamnagar", "Jamnagar", 70.05, 22.47, "refinery", "india_west", "India"),
    Node("mumbai", "Mumbai", 72.80, 18.90, "refinery", "india_west", "India"),
    Node("mangalore", "Mangalore", 74.85, 12.90, "refinery", "india_west", "India"),
    Node("cochin", "Kochi", 76.20, 9.97, "refinery", "india_south", "India"),
    Node("chennai", "Chennai", 80.30, 13.10, "refinery", "india_east", "India"),
    Node("paradip", "Paradip", 86.60, 20.30, "refinery", "india_east", "India"),
]

NODES: dict[str, Node] = {n.id: n for n in _NODES}


# ──────────────────────────────────────────────────────────────────
# Edges (undirected shipping lanes) — adjacency only; km filled below
# ──────────────────────────────────────────────────────────────────
_ADJ: list[tuple[str, str]] = [
    # Persian Gulf → Hormuz (Hormuz is the sole Gulf exit)
    ("ras_tanura", "hormuz"),
    ("basra", "hormuz"),
    ("kharg", "hormuz"),
    ("mina_al_ahmadi", "hormuz"),
    ("hormuz", "gulf_of_oman"),
    # Fujairah bypass — sits outside Hormuz on the Gulf of Oman
    ("fujairah", "gulf_of_oman"),
    ("gulf_of_oman", "arabian_sea"),
    # Arabian Sea → Indian west coast (Jamnagar is the primary landing; Vadinar,
    # its Gulf-of-Kutch neighbour, hangs off it via a short coastal hop)
    ("arabian_sea", "jamnagar"),
    ("jamnagar", "vadinar"),
    ("arabian_sea", "mumbai"),
    ("arabian_sea", "mangalore"),
    ("mumbai", "mangalore"),
    ("mangalore", "cochin"),
    ("cochin", "chennai"),
    ("chennai", "paradip"),
    ("cochin", "bay_of_bengal"),
    ("bay_of_bengal", "chennai"),
    ("bay_of_bengal", "paradip"),
    # Open-sea round-Sri-Lanka lane → independent access to the east coast.
    # Gulf barrels: arabian_sea → sri_lanka_s → bay_of_bengal → Chennai/Paradip.
    ("arabian_sea", "sri_lanka_s"),
    ("sri_lanka_s", "bay_of_bengal"),
    # Cape/southern-ocean crude can also swing east below Sri Lanka.
    ("s_indian_ocean", "sri_lanka_s"),
    # Red Sea → Suez → Mediterranean → Atlantic
    ("arabian_sea", "gulf_of_aden"),
    ("gulf_of_aden", "bab_el_mandeb"),
    ("bab_el_mandeb", "red_sea_s"),
    ("red_sea_s", "red_sea_n"),
    ("red_sea_n", "suez"),
    ("suez", "e_mediterranean"),
    ("e_mediterranean", "w_mediterranean"),
    ("w_mediterranean", "gibraltar"),
    ("gibraltar", "n_atlantic"),
    # Cape of Good Hope failover
    ("arabian_sea", "s_indian_ocean"),
    ("s_indian_ocean", "mozambique_ch"),
    ("mozambique_ch", "cape"),
    ("s_indian_ocean", "cape"),
    ("cape", "s_atlantic"),
    ("s_atlantic", "n_atlantic"),
    # West Africa sources
    ("bonny", "s_atlantic"),
    ("bonny", "n_atlantic"),
    ("luanda", "s_atlantic"),
    ("luanda", "cape"),
    # Atlantic / Americas
    ("n_atlantic", "caribbean"),
    ("caribbean", "jose"),
    ("caribbean", "panama"),
    ("caribbean", "gulf_of_mexico"),
    ("gulf_of_mexico", "houston"),
    # Russia
    ("novorossiysk", "black_sea"),
    ("black_sea", "e_mediterranean"),
    ("primorsk", "baltic_sea"),
    ("baltic_sea", "n_atlantic"),
    # South-East Asia (latent eastern grid)
    ("bay_of_bengal", "andaman_sea"),
    ("andaman_sea", "malacca"),
    ("malacca", "singapore"),
    ("andaman_sea", "sunda"),
    ("sunda", "singapore"),
]

EDGES: list[Edge] = [
    Edge(a, b, haversine_km(NODES[a].lon, NODES[a].lat, NODES[b].lon, NODES[b].lat))
    for a, b in _ADJ
]


# ──────────────────────────────────────────────────────────────────
# Derived helpers
# ──────────────────────────────────────────────────────────────────
SOURCE_IDS = [n.id for n in _NODES if n.role == "source"]
REFINERY_IDS = [n.id for n in _NODES if n.role == "refinery"]
CHOKEPOINT_IDS = [n.id for n in _NODES if n.role == "chokepoint"]

# The default primary artery for India (used to frame "baseline" deltas).
PRIMARY_SOURCE = "ras_tanura"
PRIMARY_REFINERY = "jamnagar"


def node_public(n: Node) -> dict:
    """Serialisable node for the topology endpoint / frontend."""
    return {
        "id": n.id,
        "name": n.name,
        "coords": [n.lon, n.lat],
        "role": n.role,
        "region": n.region,
        "country": n.country,
    }


def edge_public(e: Edge) -> dict:
    return {"a": e.a, "b": e.b, "km": e.km}
