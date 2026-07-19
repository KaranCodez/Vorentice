/** Client for the Vorentice Route Agent backend (FastAPI, port 8002). */

const ROUTE_API_BASE =
  process.env.NEXT_PUBLIC_ROUTE_API ?? "http://127.0.0.1:8002/api";

export type NodeRole = "source" | "chokepoint" | "waypoint" | "refinery";
export type NodeState = "blue" | "green" | "red";
export type DisruptStatus = "blocked" | "high_risk" | "elevated";

export interface GraphNode {
  id: string;
  name: string;
  coords: [number, number]; // [lon, lat]
  role: NodeRole;
  region: string;
  country: string;
}

export interface GraphEdge {
  a: string;
  b: string;
  km: number;
}

export interface Topology {
  nodes: GraphNode[];
  edges: GraphEdge[];
  baseline_path: string[];
  baseline: {
    source: string;
    refinery: string;
    distance_km: number;
    transit_days: number;
  };
}

export interface Disruption {
  node_id: string;
  status: DisruptStatus;
  vector: string;
  spark: string;
  header: string;
  source: "live" | "manual";
  criticality: string;
  region: string;
}

export interface Metric {
  label: string;
  value: string;
  unit: string;
  delta: string;
  tone: "critical" | "warn" | "neutral" | "good";
}

export interface AssetExposure {
  asset: string;
  capacity_kbd: number;
  severity: "critical" | "warn";
  detail: string;
}

export interface StrategicOffset {
  action: string;
  detail: string;
  kind: string;
}

export interface DeepDive {
  header: string;
  vector: string;
  spark: string;
  status: DisruptStatus;
  criticality: string;
  region: string;
  alt_source: string | null;
  alt_source_name: string;
  min_draft_m: number;
  min_draft_node: string;
  added_days: number;
  downstream: string[];
}

export interface RouteState {
  mode: "live" | "sandbox";
  generated_at: string;
  feasible: boolean;
  active_path: string[];
  baseline_path: string[];
  disrupted: Disruption[];
  node_states: Record<string, NodeState>;
  broken_edges: { a: string; b: string }[];
  sparks: Record<string, string>;
  deep_dive: Record<string, DeepDive>;
  route: {
    source: string | null;
    source_name: string;
    refinery: string | null;
    refinery_name: string;
    distance_km: number;
    transit_days: number;
  };
  constraints: {
    draft_ok: boolean;
    min_draft_m: number;
    min_draft_node: string;
    dwell_days: number;
    clearance_notes: string[];
    warnings: string[];
    references: {
      node: string;
      name: string;
      max_draft_m: number | null;
      channel_depth_m: number | null;
      typical_dwell_d: number | null;
      treaty: string | null;
      note: string | null;
    }[];
  };
  impact: {
    reroute_required: boolean;
    added_days: number;
    added_km: number;
    landed_cost_uplift_usd_bbl: number;
    retail_pump_pct: number;
  };
  floater: {
    header: string;
    vector: string;
    asset_exposure: AssetExposure[];
    strategic_offset: StrategicOffset[];
    metrics: Metric[];
  };
  event_count?: number;
}

export async function fetchTopology(): Promise<Topology> {
  const res = await fetch(`${ROUTE_API_BASE}/route/topology`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Route Agent topology returned ${res.status}`);
  return res.json();
}

export async function fetchLive(hours = 24): Promise<RouteState> {
  const res = await fetch(`${ROUTE_API_BASE}/route/live?hours=${hours}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `Route Agent live returned ${res.status}`);
  }
  return res.json();
}

export async function simulate(
  disrupted: { node_id: string; status?: DisruptStatus }[]
): Promise<RouteState> {
  const res = await fetch(`${ROUTE_API_BASE}/route/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ disrupted }),
    cache: "no-store",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `Route Agent simulate returned ${res.status}`);
  }
  return res.json();
}

/** Empty (all-nominal) route state so the UI can render before first fetch. */
export function emptyRouteState(baselinePath: string[]): RouteState {
  return {
    mode: "sandbox",
    generated_at: new Date().toISOString(),
    feasible: true,
    active_path: baselinePath,
    baseline_path: baselinePath,
    disrupted: [],
    node_states: {},
    broken_edges: [],
    sparks: {},
    deep_dive: {},
    route: {
      source: baselinePath[0] ?? null,
      source_name: "",
      refinery: baselinePath[baselinePath.length - 1] ?? null,
      refinery_name: "",
      distance_km: 0,
      transit_days: 0,
    },
    constraints: {
      draft_ok: true,
      min_draft_m: 0,
      min_draft_node: "",
      dwell_days: 0,
      clearance_notes: [],
      warnings: [],
      references: [],
    },
    impact: {
      reroute_required: false,
      added_days: 0,
      added_km: 0,
      landed_cost_uplift_usd_bbl: 0,
      retail_pump_pct: 0,
    },
    floater: {
      header: "All corridors nominal",
      vector: "none",
      asset_exposure: [],
      strategic_offset: [],
      metrics: [],
    },
  };
}
