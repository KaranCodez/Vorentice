"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  ChatMessage,
  InitResponse,
  RiskMode,
  initRiskSession,
  streamRiskChat,
  parseFollowups,
} from "@/lib/riskApi";
import Markdown from "@/components/risk/Markdown";
import StatCards, { splitStatBlocks } from "@/components/risk/StatCards";

/* ─────────── types ─────────── */

interface Message {
  id: string;
  role: "user" | "assistant" | "error";
  content: string;
  followups?: string[];
  streaming?: boolean;
}

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

/* ─────────── risk gauge ─────────── */

function scoreColor(score: number): string {
  if (score >= 80) return "#ef4444";
  if (score >= 60) return "#f97316";
  if (score >= 40) return "#eab308";
  return "#14b8a6";
}

function RiskGauge({ score, label }: { score: number; label: string }) {
  const color = scoreColor(score);
  const r = 34;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="relative size-[88px]">
        <svg viewBox="0 0 80 80" className="size-full -rotate-90">
          <circle cx="40" cy="40" r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="6" />
          <circle
            cx="40"
            cy="40"
            r={r}
            fill="none"
            stroke={color}
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={`${dash} ${circ}`}
            style={{ transition: "stroke-dasharray 1s ease-out", filter: `drop-shadow(0 0 5px ${color}88)` }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold leading-none text-white">{score}</span>
          <span className="font-mono text-[8px] uppercase tracking-widest text-white/40">/ 100</span>
        </div>
      </div>
      <span
        className="rounded-full px-2.5 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-widest"
        style={{ background: `${color}22`, color, border: `1px solid ${color}55` }}
      >
        {label}
      </span>
    </div>
  );
}

/* ─────────── briefing card ─────────── */

function BriefingCard({ session, mode }: { session: InitResponse; mode: RiskMode }) {
  const modeLabel =
    mode === "critical_events"
      ? "Critical Events · Section 2"
      : "Emerging Threats · Section 3";
  return (
    <div className="overflow-hidden rounded-2xl border border-orange-500/20 bg-gradient-to-b from-orange-500/[0.07] to-transparent">
      {/* header row */}
      <div className="flex flex-col gap-4 border-b border-white/[0.07] p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-1">
          <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-orange-400">
            Ingestion Acknowledged · {modeLabel}
          </span>
          <span className="text-sm font-semibold text-white">
            Aggregated Global Threat Profile
          </span>
          <span className="font-mono text-[10px] text-white/40">
            {session.event_count} live {session.event_count === 1 ? "entry" : "entries"} mapped from the News Agent
          </span>
        </div>
        <RiskGauge score={session.risk_score} label={session.risk_label} />
      </div>

      {/* executive synthesis */}
      {session.executive_synthesis && (
        <div className="border-b border-white/[0.06] p-5">
          <p className="mb-1.5 font-mono text-[9px] uppercase tracking-widest text-white/40">
            Executive Synthesis
          </p>
          <p className="text-[13.5px] leading-relaxed text-white/85">
            {session.executive_synthesis}
          </p>
        </div>
      )}

      {/* threat profile markdown */}
      {session.threat_profile_md && (
        <div className="p-5">
          <Markdown text={session.threat_profile_md} />
        </div>
      )}
    </div>
  );
}

/* ─────────── mode select ─────────── */

const MODES: { id: RiskMode; label: string; desc: string; icon: string }[] = [
  {
    id: "critical_events",
    label: "Analyze Critical Events",
    desc: "Deep analysis of high-impact, active disruptions — the News Agent's Section 2.",
    icon: "⚡",
  },
  {
    id: "emerging_threats",
    label: "Analyze Emerging Threats",
    desc: "Latent risk modeling from the News Agent's Section 3 watchlist.",
    icon: "🔭",
  },
];

function ModeSelect({ onSelect }: { onSelect: (mode: RiskMode) => void }) {
  return (
    <div className="mx-auto flex max-w-2xl flex-1 flex-col items-center justify-center gap-8 px-4 py-12 text-center">
      <div>
        <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.22em] text-orange-400">
          Risk Intelligence Agent
        </p>
        <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
          Select Analysis Mode
        </h1>
        <p className="mx-auto mt-2 max-w-md text-sm text-white/40">
          The Risk Agent coordinates with the News Agent, pulls the live section,
          computes a global risk posture, and opens an unlimited What-If session.
        </p>
      </div>

      <div className="flex w-full flex-col gap-4 sm:flex-row">
        {MODES.map((m) => (
          <button
            key={m.id}
            onClick={() => onSelect(m.id)}
            className="group flex flex-1 flex-col gap-3 rounded-2xl border border-white/10 bg-white/[0.03] p-6 text-left transition-all hover:border-orange-500/40 hover:bg-white/[0.06] hover:shadow-[0_0_28px_-8px_rgba(249,115,22,0.35)]"
          >
            <span className="text-2xl">{m.icon}</span>
            <span className="font-semibold text-white transition-colors group-hover:text-orange-300">
              {m.label}
            </span>
            <span className="text-xs leading-relaxed text-white/40">{m.desc}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

/* ─────────── loading ─────────── */

function LoadingScreen({ mode }: { mode: RiskMode }) {
  const label = mode === "critical_events" ? "Critical Events" : "Emerging Threats";
  const steps = [
    "Invoking News Agent…",
    `Extracting ${label} payload…`,
    "Running cross-segment synthesis…",
    "Scoring global risk posture…",
  ];
  const [step, setStep] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setStep((s) => (s + 1) % steps.length), 1400);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-5 py-20 text-center">
      <div className="relative size-12">
        <span className="absolute inset-0 animate-ping rounded-full border-2 border-orange-500/30" />
        <span className="absolute inset-0 rounded-full border-2 border-orange-500/60" />
        <span className="absolute inset-[30%] rounded-full bg-orange-500/70" />
      </div>
      <p className="font-mono text-xs uppercase tracking-widest text-orange-400">
        {steps[step]}
      </p>
    </div>
  );
}

/* ─────────── follow-up chips ─────────── */

function Followups({
  items,
  onPick,
}: {
  items: string[];
  onPick: (q: string) => void;
}) {
  if (!items.length) return null;
  return (
    <div className="flex flex-wrap gap-2 pt-1">
      {items.map((q, i) => (
        <button
          key={i}
          onClick={() => onPick(q)}
          className="group flex items-center gap-1.5 rounded-full border border-orange-500/30 bg-orange-500/[0.06] px-3 py-1.5 text-left text-[12px] text-white/80 transition-all hover:border-orange-500/60 hover:bg-orange-500/15 hover:text-white"
        >
          <svg viewBox="0 0 16 16" fill="none" className="size-3 shrink-0 text-orange-400" aria-hidden>
            <path d="M8 3v6a2 2 0 0 1-2 2H3M6 9l-3 2 3 2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          {q}
        </button>
      ))}
    </div>
  );
}

/* ─────────── bubbles ─────────── */

function Dots() {
  return (
    <span className="inline-flex gap-1 pl-0.5 align-middle">
      {[0, 1, 2].map((i) => (
        <span key={i} className="size-1.5 animate-bounce rounded-full bg-orange-400/70" style={{ animationDelay: `${i * 0.15}s` }} />
      ))}
    </span>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-orange-600/85 px-4 py-2.5 text-[13.5px] leading-relaxed text-white">
        {text}
      </div>
    </div>
  );
}

function AssistantBubble({ msg }: { msg: Message }) {
  const segments = msg.content ? splitStatBlocks(msg.content) : [];
  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[92%] rounded-2xl rounded-bl-sm border border-white/10 bg-white/[0.03] px-4 py-3.5">
        {segments.map((seg, i) =>
          seg.type === "stats" ? (
            <StatCards key={i} items={seg.items} />
          ) : (
            <Markdown key={i} text={seg.text} />
          )
        )}
        {msg.streaming && !msg.content && <Dots />}
        {msg.streaming && msg.content && (
          <span className="ml-0.5 inline-block h-3.5 w-0.5 animate-pulse bg-orange-400 align-middle" />
        )}
      </div>
    </div>
  );
}

/* ─────────── page ─────────── */

export default function RiskAgentPage() {
  const [phase, setPhase] = useState<"select" | "loading" | "chat">("select");
  const [mode, setMode] = useState<RiskMode | null>(null);
  const [session, setSession] = useState<InitResponse | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [initFollowups, setInitFollowups] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [initError, setInitError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const chatHistory = useRef<ChatMessage[]>([]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleModeSelect = useCallback(async (m: RiskMode) => {
    setMode(m);
    setPhase("loading");
    setInitError(null);
    try {
      const result = await initRiskSession(m);
      setSession(result);
      setInitFollowups(result.followups ?? []);
      setMessages([]);
      chatHistory.current = [];
      setPhase("chat");
    } catch (err: unknown) {
      setInitError(err instanceof Error ? err.message : String(err));
      setPhase("chat");
    }
  }, []);

  const sendTracked = useCallback(
    async (text: string) => {
      const userText = text.trim();
      if (!userText || busy || !session) return;
      setInput("");
      setInitFollowups([]);
      const assistantId = uid();
      setMessages((prev) => [
        ...prev,
        { id: uid(), role: "user", content: userText },
        { id: assistantId, role: "assistant", content: "", streaming: true },
      ]);
      setBusy(true);
      abortRef.current = new AbortController();
      let raw = "";
      try {
        await streamRiskChat(
          session.mode,
          session.payload,
          chatHistory.current,
          userText,
          (fullText) => {
            raw = fullText;
            const { body } = parseFollowups(fullText);
            setMessages((prev) =>
              prev.map((mm) =>
                mm.id === assistantId ? { ...mm, content: body, streaming: true } : mm
              )
            );
          },
          abortRef.current.signal
        );
        const { body, followups } = parseFollowups(raw);
        chatHistory.current = [
          ...chatHistory.current,
          { role: "user", content: userText },
          { role: "assistant", content: body },
        ];
        setMessages((prev) =>
          prev.map((mm) =>
            mm.id === assistantId
              ? { ...mm, content: body, followups, streaming: false }
              : mm
          )
        );
      } catch (err: unknown) {
        if ((err as { name?: string })?.name === "AbortError") return;
        const emsg = err instanceof Error ? err.message : String(err);
        setMessages((prev) =>
          prev.map((mm) =>
            mm.id === assistantId
              ? { ...mm, role: "error", content: `**Error:** ${emsg}`, streaming: false }
              : mm
          )
        );
      } finally {
        setBusy(false);
      }
    },
    [busy, session]
  );

  const reset = () => {
    abortRef.current?.abort();
    setPhase("select");
    setMode(null);
    setSession(null);
    setMessages([]);
    setInitFollowups([]);
    setInitError(null);
    chatHistory.current = [];
  };

  const modeLabel = mode === "critical_events" ? "Critical Events" : "Emerging Threats";

  // Which followups to show under the last message?
  const lastMsg = messages[messages.length - 1];
  const showInitChips =
    phase === "chat" &&
    !busy &&
    messages.length === 0 &&
    initFollowups.length > 0 &&
    !initError;
  const lastMsgFollowups =
    !busy && lastMsg?.role === "assistant" ? lastMsg.followups ?? [] : [];

  return (
    <div className="flex min-h-dvh flex-col bg-[#080f0e] text-[#e8f2ef]">
      {/* header */}
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-white/[0.07] bg-[#080f0e]/90 px-4 py-3 backdrop-blur-md sm:px-8">
        <div className="flex items-center gap-3">
          <span className="flex size-7 items-center justify-center rounded-md bg-orange-500/15 text-orange-400">
            <ShieldIcon />
          </span>
          <div>
            <p className="text-[11px] font-semibold leading-none text-white/80">
              Risk Intelligence Agent
            </p>
            {mode && (
              <p className="mt-0.5 font-mono text-[9px] uppercase tracking-widest text-orange-400/70">
                {modeLabel} · Active
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-4">
          {phase === "chat" && (
            <button
              onClick={reset}
              className="font-mono text-[9px] uppercase tracking-[0.18em] text-white/30 transition-colors hover:text-orange-400"
            >
              ← Switch Mode
            </button>
          )}
          <Link
            href="/"
            className="font-mono text-[9px] uppercase tracking-[0.18em] text-white/30 transition-colors hover:text-teal-300"
          >
            ← Surface
          </Link>
        </div>
      </header>

      {/* body */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {phase === "select" && <ModeSelect onSelect={handleModeSelect} />}
        {phase === "loading" && mode && <LoadingScreen mode={mode} />}

        {phase === "chat" && (
          <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col overflow-hidden px-4 sm:px-6">
            <div className="flex flex-1 flex-col gap-4 overflow-y-auto py-6 pr-1">
              {initError && (
                <div className="rounded-xl border border-red-500/30 bg-red-500/[0.07] p-4 text-sm text-red-200">
                  <p className="mb-1 font-semibold">Failed to initialize session</p>
                  <p className="text-red-200/80">{initError}</p>
                  <p className="mt-2 text-xs text-red-200/60">
                    Ensure the News Agent (port 8000) and Risk Agent (port 8001) are both running.
                  </p>
                </div>
              )}

              {session && mode && <BriefingCard session={session} mode={mode} />}

              {showInitChips && (
                <div>
                  <p className="mb-2 font-mono text-[9px] uppercase tracking-widest text-white/35">
                    Suggested openings
                  </p>
                  <Followups items={initFollowups} onPick={sendTracked} />
                </div>
              )}

              {messages.map((msg) =>
                msg.role === "user" ? (
                  <UserBubble key={msg.id} text={msg.content} />
                ) : msg.role === "error" ? (
                  <div
                    key={msg.id}
                    className="rounded-xl border border-red-500/30 bg-red-500/[0.07] px-4 py-3 text-sm text-red-200"
                  >
                    <Markdown text={msg.content} />
                  </div>
                ) : (
                  <AssistantBubble key={msg.id} msg={msg} />
                )
              )}

              {lastMsgFollowups.length > 0 && (
                <Followups items={lastMsgFollowups} onPick={sendTracked} />
              )}

              <div ref={bottomRef} />
            </div>

            {/* input */}
            <div className="border-t border-white/[0.07] py-3">
              <div className="flex items-end gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 transition-colors focus-within:border-orange-500/40">
                <textarea
                  className="max-h-36 min-h-[2.5rem] flex-1 resize-none bg-transparent text-sm leading-relaxed text-white/90 outline-none placeholder:text-white/25"
                  placeholder='Ask a "What-If" scenario or request a risk analysis…'
                  value={input}
                  rows={1}
                  disabled={!!initError}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      sendTracked(input);
                    }
                  }}
                />
                <button
                  onClick={() => sendTracked(input)}
                  disabled={!input.trim() || busy || !!initError}
                  className="shrink-0 rounded-lg bg-orange-600 px-3.5 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-orange-500 disabled:opacity-30"
                >
                  {busy ? "…" : "Send"}
                </button>
              </div>
              <p className="mt-1.5 text-center font-mono text-[8px] uppercase tracking-widest text-white/20">
                Enter to send · Shift+Enter for newline
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ShieldIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" className="size-4" aria-hidden>
      <path d="M8 2L3 4v4c0 3 2.3 5.3 5 6 2.7-.7 5-3 5-6V4L8 2z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
      <path d="M5.5 8l1.8 1.8L10.5 6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
