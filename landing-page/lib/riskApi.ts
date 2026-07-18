/** Client for the Vorentice Risk Agent backend (FastAPI, port 8001). */

const RISK_API_BASE =
  process.env.NEXT_PUBLIC_RISK_API ?? "http://127.0.0.1:8001/api";

export type RiskMode = "critical_events" | "emerging_threats";

export interface InitResponse {
  mode: RiskMode;
  payload: string;
  event_count: number;
  risk_score: number;
  risk_label: string;
  executive_synthesis: string;
  threat_profile_md: string;
  followups: string[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export async function initRiskSession(
  mode: RiskMode,
  hours = 24
): Promise<InitResponse> {
  const res = await fetch(`${RISK_API_BASE}/risk/init`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode, hours }),
    cache: "no-store",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `Risk Agent returned ${res.status}`);
  }
  return res.json();
}

export async function streamRiskChat(
  mode: RiskMode,
  payload: string,
  messages: ChatMessage[],
  message: string,
  onToken: (fullText: string) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${RISK_API_BASE}/risk/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode, payload, messages, message }),
    signal,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Risk Agent returned ${res.status}`);
  }
  const reader = res.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  let acc = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    acc += decoder.decode(value, { stream: true });
    onToken(acc);
  }
}

/** Split a completed assistant message into the visible body and the
 *  follow-up questions the agent appended in a <<FOLLOWUPS>> block. While
 *  the block is still streaming (only the opening tag has arrived) we hide
 *  the partial block from the body so the user never sees raw tags. */
export function parseFollowups(text: string): {
  body: string;
  followups: string[];
} {
  const startIdx = text.indexOf("<<FOLLOWUPS>>");
  if (startIdx === -1) return { body: text, followups: [] };

  const body = text.slice(0, startIdx).trimEnd();
  const endIdx = text.indexOf("<<END>>", startIdx);
  const inner =
    endIdx === -1
      ? text.slice(startIdx + "<<FOLLOWUPS>>".length)
      : text.slice(startIdx + "<<FOLLOWUPS>>".length, endIdx);

  const followups = inner
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.length > 0 && !l.startsWith("<<"))
    .map((l) => l.replace(/^[-*\d.)\s]+/, "").trim())
    .filter(Boolean);

  return { body, followups };
}
