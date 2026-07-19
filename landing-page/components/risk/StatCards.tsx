"use client";

import { useState } from "react";

/* Renders a <<STATS>> block from the Risk Agent as expandable metric cards.
 *
 * Block format (one stat per line):
 *   Label | Value | Context | Source | Derivation
 *
 * Derivation is optional — shown when the user clicks the card to reveal
 * the calculation logic / domino chain behind the number. */

export interface StatItem {
  label: string;
  value: string;
  context?: string;
  source?: string;
  derivation?: string;
}

export type Segment =
  | { type: "md"; text: string }
  | { type: "stats"; items: StatItem[] };

const OPEN = "<<STATS>>";
const CLOSE = "<<END_STATS>>";

function stripMarkdown(text: string): string {
  return text.replace(/\*\*([^*]+)\*\*/g, "$1").replace(/\*([^*]+)\*/g, "$1");
}

function parseStatLines(inner: string): StatItem[] {
  return inner
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.length > 0 && l.includes("|"))
    .map((l) => {
      const parts = l.split("|").map((p) => stripMarkdown(p.trim()));
      return {
        label: parts[0] ?? "",
        value: parts[1] ?? "",
        context: parts[2] || undefined,
        source: parts[3] || undefined,
        derivation: parts[4] || undefined,
      };
    })
    .filter((s) => s.label && s.value)
    .slice(0, 6);
}

export function splitStatBlocks(content: string): Segment[] {
  const segments: Segment[] = [];
  let rest = content;

  while (true) {
    const start = rest.indexOf(OPEN);
    if (start === -1) break;

    const before = rest.slice(0, start).trimEnd();
    if (before) segments.push({ type: "md", text: before });

    const end = rest.indexOf(CLOSE, start);
    if (end === -1) {
      return segments;
    }

    const inner = rest.slice(start + OPEN.length, end);
    const items = parseStatLines(inner);
    if (items.length) segments.push({ type: "stats", items });

    rest = rest.slice(end + CLOSE.length).replace(/^\s*\n/, "");
  }

  const tail = rest.trim();
  if (tail) segments.push({ type: "md", text: tail });
  return segments;
}

/* ── expandable card ── */

/* The derivation field arrives as a chain of steps separated by ";;" —
 * Step 1: base facts + sources, Step 2: calculation, Step 3: domino logic,
 * Step 4: assumption/limit, Step 5: decision meaning. Rendered as a
 * connected vertical chain when the card is expanded. */

const STEP_LABELS = [
  "Base Facts",
  "Calculation",
  "Domino Effect",
  "Assumption & Limits",
  "Decision Meaning",
];

function derivationSteps(derivation: string): string[] {
  return derivation
    .split(";;")
    .map((s) => s.trim())
    .filter(Boolean);
}

function StatCard({ item, index }: { item: StatItem; index: number }) {
  const [open, setOpen] = useState(false);
  const steps = item.derivation ? derivationSteps(item.derivation) : [];
  const hasDerivation = steps.length > 0;

  return (
    <div
      style={{ animationDelay: `${Math.min(index * 0.07, 0.5)}s` }}
      className={`risk-card flex flex-col rounded-xl border bg-gradient-to-b from-orange-500/[0.08] to-white/[0.02] transition-[transform,border-color,box-shadow] duration-300 hover:-translate-y-0.5 ${
        open
          ? "border-orange-500/40 shadow-[0_0_20px_-4px_rgba(249,115,22,0.3)]"
          : "border-orange-500/20"
      } ${hasDerivation ? "cursor-pointer hover:border-orange-500/45 hover:shadow-[0_0_16px_-6px_rgba(249,115,22,0.35)]" : ""}`}
      onClick={() => hasDerivation && setOpen(!open)}
    >
      <div className="flex flex-col gap-1 px-3 py-2.5">
        <div className="flex items-start justify-between gap-1.5">
          <span className="font-mono text-[8.5px] font-medium uppercase leading-tight tracking-[0.14em] text-white/45">
            {item.label}
          </span>
          <div className="flex items-center gap-1">
            {item.source && (
              <span className="shrink-0 rounded bg-white/[0.07] px-1 py-px font-mono text-[7.5px] uppercase tracking-wider text-orange-300/70">
                {item.source}
              </span>
            )}
            {hasDerivation && (
              <svg
                viewBox="0 0 12 12"
                className={`size-2.5 shrink-0 text-white/30 transition-transform duration-300 ${
                  open ? "rotate-180" : ""
                }`}
                fill="none"
              >
                <path
                  d="M3 5l3 3 3-3"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            )}
          </div>
        </div>
        <span className="font-mono text-[15px] font-bold leading-none text-orange-200">
          {item.value}
        </span>
        {item.context && (
          <span className="text-[10px] leading-tight text-white/40">
            {item.context}
          </span>
        )}
        {hasDerivation && !open && (
          <span className="mt-0.5 font-mono text-[7.5px] uppercase tracking-[0.14em] text-orange-400/45">
            Click for the logic chain
          </span>
        )}
      </div>

      {/* animated derivation panel */}
      <div
        className={`grid transition-all duration-300 ease-out ${
          open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
        }`}
      >
        <div className="overflow-hidden">
          {hasDerivation && (
            <div className="border-t border-orange-500/15 px-3 pb-3 pt-2.5">
              <p className="mb-2 font-mono text-[7.5px] uppercase tracking-[0.16em] text-orange-400/60">
                How this number was built
              </p>
              <div className="flex flex-col">
                {steps.map((step, i) => (
                  <div key={i} className="flex gap-2.5">
                    {/* chain spine */}
                    <div className="flex flex-col items-center">
                      <span className="flex size-4 shrink-0 items-center justify-center rounded-full border border-orange-500/40 bg-orange-500/15 font-mono text-[8px] font-bold text-orange-300">
                        {i + 1}
                      </span>
                      {i < steps.length - 1 && (
                        <span className="w-px flex-1 bg-gradient-to-b from-orange-500/35 to-orange-500/10" />
                      )}
                    </div>
                    <div className="flex-1 pb-2.5">
                      <p className="font-mono text-[7.5px] uppercase tracking-[0.14em] text-white/35">
                        {STEP_LABELS[i] ?? `Step ${i + 1}`}
                      </p>
                      <p className="mt-0.5 text-[11px] leading-relaxed text-white/65">
                        {step}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── the grid ── */

export default function StatCards({ items }: { items: StatItem[] }) {
  if (!items.length) return null;
  return (
    <div className="my-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
      {items.map((s, i) => (
        <StatCard key={i} item={s} index={i} />
      ))}
    </div>
  );
}
