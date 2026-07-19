"use client";

import type { RouteState } from "@/lib/routeApi";

const TONE: Record<string, string> = {
  critical: "var(--ra-bad)",
  warn: "var(--ra-warn)",
  good: "var(--ra-good)",
  neutral: "var(--ra-dim)",
};

const VECTOR_LABEL: Record<string, string> = {
  maritime_chokepoint: "Maritime Chokepoint Disruption",
  domestic_infrastructure: "Domestic Infrastructure Breakdown",
  financial_settlement: "Financial Settlement Frustration",
  commodity_input: "Commodity Input Shock",
  none: "Network Nominal",
};

/** The charter's "un-hardcoded" intelligence panel — loops over
 *  backend-generated arrays; it stores no static text fields of its own.
 *  Rendered inside the page's scrollable side panel. */
export default function ImpactFloater({ state }: { state: RouteState }) {
  const { floater, route, constraints, impact, feasible } = state;
  const active = state.disrupted.length > 0;

  return (
    <div className="flex flex-col gap-3.5 p-4">
      {/* Dynamic alert header */}
      <div className="flex items-start gap-2.5">
        <span className="relative mt-1.5 flex size-2.5 shrink-0">
          <span
            className="absolute inline-flex h-full w-full rounded-full opacity-80"
            style={{ background: active ? TONE.critical : TONE.good }}
          />
          {active && (
            <span
              className="absolute inline-flex h-full w-full animate-ping rounded-full"
              style={{ background: TONE.critical }}
            />
          )}
        </span>
        <div className="min-w-0">
          <div className="font-mono text-[9.5px] uppercase tracking-[0.2em] text-[var(--ra-faint)]">
            {VECTOR_LABEL[floater.vector] ?? "Disruption"}
          </div>
          <h3 className="mt-0.5 text-[16px] font-semibold leading-tight text-[var(--ra-text)]">
            {floater.header}
          </h3>
        </div>
      </div>

      {/* Route line */}
      <div className="rounded-xl border border-[var(--ra-border)] bg-[var(--ra-inset)] px-3.5 py-2.5">
        <div className="font-mono text-[9.5px] uppercase tracking-widest text-[var(--ra-faint)]">
          Corridor to India
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[13.5px]">
          <span className="font-semibold text-[var(--ra-good)]">
            {route.source_name || "—"}
          </span>
          <svg viewBox="0 0 16 16" className="size-3.5 text-[var(--ra-faint)]" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M2.5 8h11M9.5 4l4 4-4 4" />
          </svg>
          <span className="font-semibold text-[var(--ra-text)]">
            {route.refinery_name || "—"}
          </span>
        </div>
        {!feasible && (
          <div className="mt-1.5 text-[12px] font-semibold text-[var(--ra-bad)]">
            No feasible corridor — supply severed.
          </div>
        )}
      </div>

      {/* Dynamic metrics */}
      {floater.metrics.length > 0 && (
        <div className="grid grid-cols-2 gap-2">
          {floater.metrics.map((m) => (
            <div
              key={m.label}
              className="rounded-xl border border-[var(--ra-border)] bg-[var(--ra-inset)] px-3 py-2.5"
            >
              <div className="font-mono text-[9px] uppercase tracking-wider text-[var(--ra-faint)]">
                {m.label}
              </div>
              <div className="mt-1 flex items-baseline gap-1">
                <span
                  className="text-[17px] font-semibold tabular-nums leading-none"
                  style={{ color: TONE[m.tone] ?? TONE.neutral }}
                >
                  {m.value}
                </span>
                {m.unit && (
                  <span className="text-[10.5px] text-[var(--ra-faint)]">{m.unit}</span>
                )}
              </div>
              {m.delta && (
                <div className="mt-1 text-[10px] leading-snug text-[var(--ra-faint)]">
                  {m.delta}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Asset exposure list (open-ended loop) */}
      {floater.asset_exposure.length > 0 && (
        <Section title="Asset Exposure">
          {floater.asset_exposure.map((a) => (
            <li key={a.asset} className="flex items-start gap-2.5 py-1.5">
              <span
                className="mt-1.5 size-1.5 shrink-0 rounded-full"
                style={{ background: TONE[a.severity] ?? TONE.warn }}
              />
              <div className="min-w-0">
                <div className="flex flex-wrap items-baseline gap-1.5">
                  <span className="text-[12.5px] font-medium text-[var(--ra-text)]">
                    {a.asset}
                  </span>
                  {a.capacity_kbd > 0 && (
                    <span className="font-mono text-[9.5px] text-[var(--ra-faint)]">
                      {a.capacity_kbd} kbd
                    </span>
                  )}
                </div>
                <div className="text-[11px] leading-snug text-[var(--ra-dim)]">
                  {a.detail}
                </div>
              </div>
            </li>
          ))}
        </Section>
      )}

      {/* Strategic offset matrix */}
      {floater.strategic_offset.length > 0 && (
        <Section title="Strategic Offset Matrix">
          {floater.strategic_offset.map((s, i) => (
            <li key={i} className="py-1.5">
              <div className="flex items-center gap-1.5">
                <span className="text-[var(--ra-good)]">▸</span>
                <span className="text-[12.5px] font-medium text-[var(--ra-text)]">
                  {s.action}
                </span>
              </div>
              <div className="pl-4 text-[11px] leading-snug text-[var(--ra-dim)]">
                {s.detail}
              </div>
            </li>
          ))}
        </Section>
      )}

      {/* Constraint notes */}
      {(constraints.warnings.length > 0 || impact.added_days > 0) && (
        <div className="rounded-xl border border-[var(--ra-border)] bg-[var(--ra-inset)] px-3.5 py-2.5">
          <div className="font-mono text-[9.5px] uppercase tracking-widest text-[var(--ra-faint)]">
            Constraint Verification (RAG)
          </div>
          <div className="mt-1.5 text-[11.5px] text-[var(--ra-dim)]">
            Tightest draft {constraints.min_draft_m} m @ {constraints.min_draft_node} · dwell{" "}
            {constraints.dwell_days} d
          </div>
          {constraints.warnings.slice(0, 2).map((w, i) => (
            <div key={i} className="mt-1.5 text-[11px] leading-snug text-[var(--ra-warn)]">
              ⚠ {w}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-[var(--ra-border)] bg-[var(--ra-inset)] px-3.5 py-2.5">
      <div className="mb-1 font-mono text-[9.5px] uppercase tracking-widest text-[var(--ra-faint)]">
        {title}
      </div>
      <ul className="divide-y divide-[var(--ra-border)]">{children}</ul>
    </div>
  );
}
