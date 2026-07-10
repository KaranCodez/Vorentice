"use client";

import { useEffect, useState } from "react";
import {
  fetchLatest,
  subscribeToNews,
  type NewsItem,
} from "@/lib/newsApi";
import FeedItem from "./FeedItem";

type ConnState = "connecting" | "live" | "offline";

/** Live intelligence feed — initial load via REST, updates via SSE. */
export default function NewsFeed() {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [conn, setConn] = useState<ConnState>("connecting");

  useEffect(() => {
    let cancelled = false;

    fetchLatest()
      .then((latest) => {
        if (!cancelled) setItems(latest);
      })
      .catch(() => {
        if (!cancelled) setConn("offline");
      });

    const unsubscribe = subscribeToNews(
      (item) =>
        setItems((current) =>
          current.some((existing) => existing.id === item.id)
            ? current
            : [item, ...current].slice(0, 100),
        ),
      (connected) => setConn(connected ? "live" : "offline"),
    );
    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  return (
    <section className="overflow-hidden rounded-xl border border-white/10 bg-white/[0.02]">
      <header className="flex items-center justify-between border-b border-white/10 px-5 py-3">
        <h2 className="font-mono text-[10px] font-semibold uppercase tracking-[0.2em] text-white/70">
          News Agent · live intelligence
        </h2>
        <ConnBadge state={conn} />
      </header>

      {items.length === 0 ? (
        <EmptyState conn={conn} />
      ) : (
        <ul className="max-h-[62vh] overflow-y-auto">
          {items.map((item) => (
            <FeedItem key={item.id} item={item} />
          ))}
        </ul>
      )}
    </section>
  );
}

function ConnBadge({ state }: { state: ConnState }) {
  const style = {
    live: { dot: "bg-ok", text: "text-ok", label: "Live" },
    connecting: {
      dot: "bg-warn",
      text: "text-warn",
      label: "Connecting",
    },
    offline: { dot: "bg-alarm", text: "text-alarm", label: "Agent offline" },
  }[state];
  return (
    <span
      className={`flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-[0.16em] ${style.text}`}
    >
      <span className={`live-dot size-1.5 rounded-full ${style.dot}`} />
      {style.label}
    </span>
  );
}

function EmptyState({ conn }: { conn: ConnState }) {
  return (
    <div className="px-5 py-14 text-center">
      <p className="text-sm text-white/45">
        {conn === "offline"
          ? "Agent backend unreachable — start it with `python main.py` in D:\\Vorentice\\agents."
          : "No intelligence items yet. The agent reports every 30 minutes."}
      </p>
    </div>
  );
}
