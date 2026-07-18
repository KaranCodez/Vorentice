/** Client for the Vorentice agent backend (FastAPI, port 8000).
 *
 * Charter rule mirrored from the API: no numeric risk/relevance scores
 * anywhere — urgency is always a qualitative descriptor. */

const API_BASE =
  process.env.NEXT_PUBLIC_AGENTS_API ?? "http://127.0.0.1:8000/api";

export type Severity = "low" | "medium" | "high" | "critical";

export interface NewsItem {
  id: number;
  url: string;
  title: string;
  source_name: string;
  published_at: string | null;
  fetched_at: string;
  severity: Severity;
  /** Qualitative urgency descriptor: Critical / High / Moderate / Low / Emerging. */
  criticality: string;
  impact_category: string;
  region: string;
  chokepoints: string[];
  summary: string;
  /** How this affects global trade & logistics right now (may be empty). */
  trade_impact: string;
  escalation_potential: boolean;
  watchlist_reason: string;
  escalation_triggers: string;
  corroboration_count: number;
  corroborating_sources: string[];
}

export interface AgentRun {
  id: number;
  started_at: string;
  finished_at: string | null;
  ok: boolean;
  fetched: number;
  stored: number;
}

export interface Alert {
  id: number;
  created_at: string;
  reason: string;
  delivered: boolean;
  item: NewsItem;
}

export interface SegmentBriefing {
  segment: string;
  label: string;
  counts: Partial<Record<Severity, number>>;
  events: NewsItem[];
}

/** Section 1 — Daily Brief: one category's narrative roundup plus every
 *  underlying headline. All 8 categories always present. */
export interface CategoryBrief {
  segment: string;
  label: string;
  digest: string;
  item_count: number;
  digest_generated_at: string | null;
  counts: Partial<Record<Severity, number>>;
  headlines: NewsItem[];
}

/** Section 2 — Critical Events Tracker entry. */
export interface CriticalEvent {
  category: string;
  segment: string;
  event_summary: string;
  criticality: string;
  trade_impact: string;
  region: string;
  chokepoints: string[];
  sources: string[];
  url: string;
  reported_at: string | null;
}

/** Section 3 — Emerging Threats (Watchlist) entry. */
export interface WatchlistEntry {
  category: string;
  segment: string;
  summary: string;
  criticality: string;
  watchlist_reason: string;
  escalation_triggers: string;
  region: string;
  url: string;
  reported_at: string | null;
}

/** The agent's primary product: the three-section intelligence report. */
export interface IntelligenceReport {
  generated_at: string;
  window_hours: number;
  daily_brief: CategoryBrief[];
  critical_events: CriticalEvent[];
  watchlist: WatchlistEntry[];
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`agents API ${res.status}`);
  return res.json();
}

export const fetchLatest = (limit = 40) =>
  getJSON<NewsItem[]>(`/news/latest?limit=${limit}`);
export const fetchRuns = () => getJSON<AgentRun[]>(`/news/runs`);
export const fetchAlerts = () => getJSON<Alert[]>(`/news/alerts`);
export const fetchBriefing = (hours = 24) =>
  getJSON<SegmentBriefing[]>(`/news/briefing?hours=${hours}`);
export const fetchReport = (hours = 24) =>
  getJSON<IntelligenceReport>(`/news/report?hours=${hours}`);

/** Subscribe to the SSE stream; returns an unsubscribe function. */
export function subscribeToNews(
  onItem: (item: NewsItem) => void,
  onStateChange?: (connected: boolean) => void,
): () => void {
  const source = new EventSource(`${API_BASE}/news/stream`);
  source.addEventListener("news", (event) => {
    onItem(JSON.parse((event as MessageEvent).data));
  });
  source.onopen = () => onStateChange?.(true);
  source.onerror = () => onStateChange?.(false);
  return () => source.close();
}

/** True when this item is a deterministic signal (EIA/FRED/weather), not
 *  an LLM-classified article. Signals carry a synthetic `scheme://` URL. */
export function isSignal(item: NewsItem): boolean {
  return /^(eia|fred|openmeteo|noaa|ecmwf):\/\//.test(item.url);
}
