"use client";

import { useEffect, useState } from "react";
import { fetchRuns, type AgentRun } from "@/lib/newsApi";

/** Header strip: agent liveness derived from the run ledger. */
export default function AgentStatus() {
  const [lastRun, setLastRun] = useState<AgentRun | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      fetchRuns()
        .then((runs) => {
          if (!cancelled && runs.length > 0) setLastRun(runs[0]);
        })
        .catch(() => undefined);
    load();
    const timer = setInterval(load, 60_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  if (!lastRun) return null;

  const finished = lastRun.finished_at
    ? new Date(lastRun.finished_at).toLocaleTimeString()
    : "running…";

  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 font-mono text-[10px] uppercase tracking-[0.16em] text-white/40">
      <span>
        Last cycle{" "}
        <span className={lastRun.ok ? "text-ok" : "text-alarm"}>
          {lastRun.ok ? "ok" : "failed"}
        </span>
      </span>
      <span>
        {lastRun.fetched} fetched · {lastRun.stored} stored
      </span>
      <span>{finished}</span>
    </div>
  );
}
