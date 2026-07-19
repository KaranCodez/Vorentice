"""Routing Engine — optimal graph routing for the weighted transport network.

Given a set of disrupted / degraded nodes, compute the cheapest surviving
corridor that terminates at an Indian refinery. We use Dijkstra over an
undirected weighted graph augmented with two virtual nodes:

    __src__ ──premium──▶ every crude source
    every refinery ──0──▶ __sink__

so a single shortest-path search picks BOTH the best origin and the best
destination at once. When the Gulf is severed (Hormuz blocked) the search
naturally degrades to the next-cheapest surviving source (Fujairah bypass,
then Atlantic-basin barrels via the Cape), exactly as the charter requires.

Node status semantics (from the Classification Engine or a manual click):
    "blocked"    → node removed from the graph (pathway completely severed)
    "high_risk"  → node still transitable but incident edges cost RISK_MULT×
    "elevated"   → lighter penalty (ELEVATED_MULT×)
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

from route_agent.graph_data import EDGES, NODES, SOURCE_IDS, REFINERY_IDS

VIRTUAL_SRC = "__src__"
VIRTUAL_SINK = "__sink__"

RISK_MULT = 3.2      # "high_risk" / economically-unviable — passable but punished
ELEVATED_MULT = 1.6  # "elevated" advisory

# Nominal laden VLCC speed for turning distance into transit days.
VLCC_KNOTS = 13.5
KM_PER_NM = 1.852


@dataclass
class RouteResult:
    node_path: list[str]      # ordered real node ids, source → refinery
    source_id: str | None
    refinery_id: str | None
    distance_km: float
    transit_days: float
    feasible: bool


def _transit_days(distance_km: float) -> float:
    nm = distance_km / KM_PER_NM
    hours = nm / VLCC_KNOTS
    return round(hours / 24.0, 2)


def _build_adjacency(
    statuses: dict[str, str],
) -> dict[str, list[tuple[str, float]]]:
    """Weighted adjacency list honoring node statuses.

    A ``blocked`` node is dropped entirely; ``high_risk`` / ``elevated`` nodes
    keep their edges but at a multiplied cost so the router avoids them when a
    cleaner corridor exists yet still uses them as a last resort.
    """
    blocked = {nid for nid, st in statuses.items() if st == "blocked"}

    def penalty(nid: str) -> float:
        st = statuses.get(nid)
        if st == "high_risk":
            return RISK_MULT
        if st == "elevated":
            return ELEVATED_MULT
        return 1.0

    adj: dict[str, list[tuple[str, float]]] = {nid: [] for nid in NODES}
    for e in EDGES:
        if e.a in blocked or e.b in blocked:
            continue
        # An edge inherits the worst penalty of its two endpoints.
        w = e.km * max(penalty(e.a), penalty(e.b))
        adj[e.a].append((e.b, w))
        adj[e.b].append((e.a, w))

    # Virtual super-source → each surviving crude source (premium-weighted).
    adj[VIRTUAL_SRC] = []
    for sid in SOURCE_IDS:
        if sid in blocked:
            continue
        adj[VIRTUAL_SRC].append((sid, NODES[sid].premium_km))
    # Each surviving refinery → virtual super-sink (free).
    for rid in REFINERY_IDS:
        if rid in blocked:
            continue
        adj.setdefault(rid, []).append((VIRTUAL_SINK, 0.0))
    adj[VIRTUAL_SINK] = []
    return adj


def compute_route(statuses: dict[str, str] | None = None) -> RouteResult:
    """Dijkstra shortest path __src__ → __sink__ over the surviving graph."""
    statuses = statuses or {}
    adj = _build_adjacency(statuses)

    dist: dict[str, float] = {VIRTUAL_SRC: 0.0}
    prev: dict[str, str] = {}
    pq: list[tuple[float, str]] = [(0.0, VIRTUAL_SRC)]
    visited: set[str] = set()

    while pq:
        d, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)
        if u == VIRTUAL_SINK:
            break
        for v, w in adj.get(u, ()):  # noqa: B905
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))

    if VIRTUAL_SINK not in dist:
        return RouteResult([], None, None, 0.0, 0.0, feasible=False)

    # Reconstruct and strip the two virtual endpoints.
    chain: list[str] = []
    cur = VIRTUAL_SINK
    while cur in prev:
        chain.append(cur)
        cur = prev[cur]
    chain.append(VIRTUAL_SRC)
    chain.reverse()
    real = [n for n in chain if n not in (VIRTUAL_SRC, VIRTUAL_SINK)]

    # Physical distance = sum of real edge legs (exclude the premium leg).
    phys_km = 0.0
    for a, b in zip(real, real[1:]):  # noqa: B905
        leg = next(
            (e.km for e in EDGES if {e.a, e.b} == {a, b}),
            0.0,
        )
        phys_km += leg
    phys_km = round(phys_km, 1)

    source_id = real[0] if real else None
    refinery_id = real[-1] if real else None
    return RouteResult(
        node_path=real,
        source_id=source_id,
        refinery_id=refinery_id,
        distance_km=phys_km,
        transit_days=_transit_days(phys_km),
        feasible=True,
    )
