"use client";

import { useEffect, useState } from "react";
import { fetchAlerts, type Alert } from "@/lib/newsApi";

/** Standing banner for corroborated critical events. Silent when clear. */
export default function AlertBanner() {
  const [alerts, setAlerts] = useState<Alert[]>([]);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      fetchAlerts()
        .then((data) => {
          if (!cancelled) setAlerts(data);
        })
        .catch(() => undefined);
    load();
    const timer = setInterval(load, 30_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  if (alerts.length === 0) return null;

  return (
    <section className="flex flex-col gap-2">
      {alerts.slice(0, 3).map((alert) => (
        <article
          key={alert.id}
          className="flex items-start gap-3 rounded-lg border border-alarm/40 bg-alarm/[0.08] px-4 py-3"
        >
          <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center">
            <span className="live-dot size-2 rounded-full bg-alarm" />
          </span>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[9px] font-bold uppercase tracking-[0.2em] text-alarm">
                Critical event
              </span>
              <time className="font-mono text-[9px] uppercase tracking-[0.16em] text-white/30">
                {new Date(alert.created_at).toLocaleTimeString()}
              </time>
            </div>
            <p className="mt-0.5 text-sm font-medium text-white/90">
              {alert.reason}
            </p>
            <a
              href={alert.item.url}
              target="_blank"
              rel="noreferrer"
              className="mt-0.5 inline-block text-xs text-white/50 underline-offset-2 transition-colors hover:text-alarm hover:underline"
            >
              {alert.item.title}
            </a>
          </div>
        </article>
      ))}
    </section>
  );
}
