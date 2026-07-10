/** Client for the Vorentice agent backend (FastAPI, port 8000). */

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
  relevance_score: number;
  severity: Severity;
  impact_category: string;
  region: string;
  chokepoints: string[];
  summary: string;
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

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`agents API ${res.status}`);
  return res.json();
}

export const fetchLatest = (limit = 40) =>
  getJSON<NewsItem[]>(`/news/latest?limit=${limit}`);
export const fetchRuns = () => getJSON<AgentRun[]>(`/news/runs`);
export const fetchAlerts = () => getJSON<Alert[]>(`/news/alerts`);

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
