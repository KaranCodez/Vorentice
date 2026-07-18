"use client";

import { useEffect, useState } from "react";
import {
  fetchReport,
  type CategoryBrief,
  type CriticalEvent,
  type IntelligenceReport,
  type NewsItem,
  type Severity,
  type WatchlistEntry,
} from "@/lib/newsApi";

/** Qualitative criticality chips — the report never shows numbers. */
const CRITICALITY_CHIP: Record<string, string> = {
  Critical: "bg-alarm/15 text-alarm border-alarm/30",
  High: "bg-warn/15 text-warn border-warn/30",
  Moderate: "bg-accent-bright/10 text-accent-bright border-accent-bright/25",
  Low: "bg-white/5 text-white/40 border-white/10",
  Emerging: "bg-accent/15 text-accent-bright border-accent/30",
};

const SEVERITY_CHIP: Record<Severity, string> = {
  critical: "bg-alarm/15 text-alarm border-alarm/30",
  high: "bg-warn/15 text-warn border-warn/30",
  medium: "bg-accent-bright/10 text-accent-bright border-accent-bright/25",
  low: "bg-white/5 text-white/40 border-white/10",
};

function chipFor(criticality: string): string {
  return CRITICALITY_CHIP[criticality] ?? CRITICALITY_CHIP.Low;
}

/** The three-section intelligence report — the News Agent's primary
 *  product per the charter:
 *  1. Daily Brief — a narrative roundup for all 8 monitored categories
 *     (the complete newspaper replacement, quiet categories included);
 *  2. Critical Events Tracker — EVERY significant disruptive event with
 *     its qualitative criticality and current trade impact;
 *  3. Emerging Threats — the watchlist, with reasons and triggers.
 *  No numeric risk scores anywhere. */
export default function BriefingBoard() {
  const [report, setReport] = useState<IntelligenceReport | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      fetchReport()
        .then((data) => {
          if (!cancelled) setReport(data);
        })
        .catch(() => undefined);
    load();
    const timer = setInterval(load, 60_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  if (!report) return null;

  return (
    <div className="flex flex-col gap-8">
      <DailyBrief categories={report.daily_brief} hours={report.window_hours} />
      <CriticalEventsTracker events={report.critical_events} />
      <EmergingThreats entries={report.watchlist} />
    </div>
  );
}

/* ── Section 1: The Daily Brief ─────────────────────────────────── */

function DailyBrief({
  categories,
  hours,
}: {
  categories: CategoryBrief[];
  hours: number;
}) {
  return (
    <section>
      <SectionHeader
        index="01"
        title="The Daily Brief"
        subtitle={`Latest news roundup · every category · last ${hours}h`}
      />
      <div className="grid gap-3 lg:grid-cols-2">
        {categories.map((category) => (
          <CategoryCard key={category.segment} category={category} />
        ))}
      </div>
    </section>
  );
}

function CategoryCard({ category }: { category: CategoryBrief }) {
  const quiet = category.item_count === 0;
  return (
    <article
      className={`rounded-xl border p-4 ${
        quiet
          ? "border-white/5 bg-white/[0.01]"
          : "border-white/10 bg-white/[0.02]"
      }`}
    >
      <header className="mb-2 flex items-start justify-between gap-2">
        <h3
          className={`text-[12px] font-semibold leading-snug tracking-wide ${
            quiet ? "text-white/40" : "text-white/85"
          }`}
        >
          {category.label}
        </h3>
        <SeverityCounts counts={category.counts} />
      </header>
      <p
        className={`text-[12.5px] leading-relaxed ${
          quiet ? "text-white/30" : "text-white/60"
        }`}
      >
        {category.digest}
      </p>
      {category.headlines.length > 0 && (
        <details className="group mt-3">
          <summary className="cursor-pointer list-none font-mono text-[9px] uppercase tracking-[0.16em] text-white/35 transition-colors hover:text-accent-bright">
            <span className="group-open:hidden">
              ▸ {category.headlines.length} headline
              {category.headlines.length === 1 ? "" : "s"}
            </span>
            <span className="hidden group-open:inline">▾ collapse</span>
          </summary>
          <ul className="mt-2 flex flex-col gap-1.5 border-l border-white/10 pl-3">
            {category.headlines.map((headline) => (
              <Headline key={headline.id} item={headline} />
            ))}
          </ul>
        </details>
      )}
    </article>
  );
}

function Headline({ item }: { item: NewsItem }) {
  return (
    <li className="flex items-start gap-2">
      <span
        className={`mt-0.5 shrink-0 rounded-full border px-1.5 py-px font-mono text-[8px] font-semibold uppercase tracking-[0.12em] ${SEVERITY_CHIP[item.severity]}`}
      >
        {item.criticality}
      </span>
      <a
        href={item.url}
        target="_blank"
        rel="noreferrer"
        className="line-clamp-2 text-[11.5px] leading-snug text-white/55 underline-offset-2 transition-colors hover:text-accent-bright hover:underline"
      >
        {item.title}
      </a>
    </li>
  );
}

function SeverityCounts({
  counts,
}: {
  counts: Partial<Record<Severity, number>>;
}) {
  const critical = counts.critical ?? 0;
  const high = counts.high ?? 0;
  if (critical === 0 && high === 0) return null;
  return (
    <div className="flex shrink-0 gap-1.5 font-mono text-[9px] font-semibold">
      {critical > 0 && (
        <span className="rounded-full bg-alarm/15 px-2 py-0.5 text-alarm">
          {critical} critical
        </span>
      )}
      {high > 0 && (
        <span className="rounded-full bg-warn/15 px-2 py-0.5 text-warn">
          {high} high
        </span>
      )}
    </div>
  );
}

/* ── Section 2: Critical Events Tracker ─────────────────────────── */

function CriticalEventsTracker({ events }: { events: CriticalEvent[] }) {
  return (
    <section>
      <SectionHeader
        index="02"
        title="Critical Events Tracker"
        subtitle={
          events.length === 0
            ? "No critical or highly disruptive events in this window"
            : `${events.length} significant event${events.length === 1 ? "" : "s"} — all surfaced, none omitted`
        }
      />
      {events.length > 0 && (
        <div className="flex flex-col gap-3">
          {events.map((event, i) => (
            <CriticalEventCard key={`${event.url}-${i}`} event={event} />
          ))}
        </div>
      )}
    </section>
  );
}

function CriticalEventCard({ event }: { event: CriticalEvent }) {
  return (
    <article className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <header className="mb-2 flex flex-wrap items-center gap-2">
        <span
          className={`rounded-full border px-2 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-[0.14em] ${chipFor(event.criticality)}`}
        >
          {event.criticality}
        </span>
        <span className="font-mono text-[9px] uppercase tracking-[0.16em] text-white/45">
          {event.category}
        </span>
        {event.chokepoints.map((chokepoint) => (
          <span
            key={chokepoint}
            className="rounded-full bg-white/5 px-2 py-0.5 font-mono text-[9px] tracking-wide text-white/45"
          >
            {chokepoint}
          </span>
        ))}
      </header>
      <a
        href={event.url}
        target="_blank"
        rel="noreferrer"
        className="text-[13px] font-medium leading-snug text-white/85 underline-offset-2 transition-colors hover:text-accent-bright hover:underline"
      >
        {event.event_summary}
      </a>
      {event.trade_impact && (
        <p className="mt-2 border-l-2 border-warn/40 pl-3 text-[12px] leading-relaxed text-white/55">
          <span className="font-mono text-[9px] uppercase tracking-[0.16em] text-warn/80">
            Logistics / trade impact ·{" "}
          </span>
          {event.trade_impact}
        </p>
      )}
      <footer className="mt-2 flex flex-wrap items-center gap-2 font-mono text-[9px] uppercase tracking-[0.14em] text-white/30">
        <span>{event.region.replace(/_/g, " ")}</span>
        <span>·</span>
        <span>{event.sources.join(" + ")}</span>
      </footer>
    </article>
  );
}

/* ── Section 3: Emerging Threats (Watchlist) ────────────────────── */

function EmergingThreats({ entries }: { entries: WatchlistEntry[] }) {
  return (
    <section>
      <SectionHeader
        index="03"
        title="Emerging Threats — Watchlist"
        subtitle={
          entries.length === 0
            ? "Nothing on the watchlist in this window"
            : `${entries.length} development${entries.length === 1 ? "" : "s"} that could escalate`
        }
      />
      {entries.length > 0 && (
        <div className="flex flex-col gap-3">
          {entries.map((entry, i) => (
            <WatchlistCard key={`${entry.url}-${i}`} entry={entry} />
          ))}
        </div>
      )}
    </section>
  );
}

function WatchlistCard({ entry }: { entry: WatchlistEntry }) {
  return (
    <article className="rounded-xl border border-accent/20 bg-accent/[0.03] p-4">
      <header className="mb-2 flex flex-wrap items-center gap-2">
        <span
          className={`rounded-full border px-2 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-[0.14em] ${chipFor("Emerging")}`}
        >
          {entry.criticality}
        </span>
        <span className="font-mono text-[9px] uppercase tracking-[0.16em] text-white/45">
          {entry.category}
        </span>
        <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-white/30">
          {entry.region.replace(/_/g, " ")}
        </span>
      </header>
      <a
        href={entry.url}
        target="_blank"
        rel="noreferrer"
        className="text-[13px] font-medium leading-snug text-white/85 underline-offset-2 transition-colors hover:text-accent-bright hover:underline"
      >
        {entry.summary}
      </a>
      <dl className="mt-2 flex flex-col gap-1.5 text-[12px] leading-relaxed">
        {entry.watchlist_reason && (
          <div className="border-l-2 border-accent/40 pl-3">
            <dt className="inline font-mono text-[9px] uppercase tracking-[0.16em] text-accent-bright/80">
              Why it&apos;s watched ·{" "}
            </dt>
            <dd className="inline text-white/55">{entry.watchlist_reason}</dd>
          </div>
        )}
        {entry.escalation_triggers && (
          <div className="border-l-2 border-alarm/30 pl-3">
            <dt className="inline font-mono text-[9px] uppercase tracking-[0.16em] text-alarm/70">
              Escalation triggers ·{" "}
            </dt>
            <dd className="inline text-white/55">
              {entry.escalation_triggers}
            </dd>
          </div>
        )}
      </dl>
    </article>
  );
}

/* ── Shared ─────────────────────────────────────────────────────── */

function SectionHeader({
  index,
  title,
  subtitle,
}: {
  index: string;
  title: string;
  subtitle: string;
}) {
  return (
    <header className="mb-3 flex items-baseline gap-3">
      <span className="font-mono text-[10px] font-semibold text-accent-bright/60">
        {index}
      </span>
      <h2 className="font-mono text-[10px] font-semibold uppercase tracking-[0.2em] text-white/70">
        {title}
      </h2>
      <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-white/30">
        {subtitle}
      </span>
    </header>
  );
}
