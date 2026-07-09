"use client";

import { useState } from "react";
import { MAP_H, MAP_W, unproject } from "@/lib/geo";

type Cursor = { xPct: number; yPct: number; lon: number; lat: number };

/**
 * Crosshair + live lat/lon readout that tracks the cursor over the map.
 * Attach the returned handlers to the map's aspect box.
 */
export function useMapCursor() {
  const [cursor, setCursor] = useState<Cursor | null>(null);

  function onMouseMove(e: React.MouseEvent<HTMLDivElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    const xPct = ((e.clientX - r.left) / r.width) * 100;
    const yPct = ((e.clientY - r.top) / r.height) * 100;
    const ll = unproject((xPct / 100) * MAP_W, (yPct / 100) * MAP_H);
    setCursor(ll ? { xPct, yPct, lon: ll[0], lat: ll[1] } : null);
  }

  function onMouseLeave() {
    setCursor(null);
  }

  return { cursor, onMouseMove, onMouseLeave };
}

export default function CursorReadout({ cursor }: { cursor: Cursor | null }) {
  if (!cursor) return null;
  const latLabel = `${Math.abs(cursor.lat).toFixed(1)}°${cursor.lat >= 0 ? "N" : "S"}`;
  const lonLabel = `${Math.abs(cursor.lon).toFixed(1)}°${cursor.lon >= 0 ? "E" : "W"}`;
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 z-20">
      {/* crosshair hairlines */}
      <div
        className="absolute bottom-0 top-0 w-px bg-accent/15"
        style={{ left: `${cursor.xPct}%` }}
      />
      <div
        className="absolute left-0 right-0 h-px bg-accent/15"
        style={{ top: `${cursor.yPct}%` }}
      />
      <div
        className="absolute size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border border-accent/50"
        style={{ left: `${cursor.xPct}%`, top: `${cursor.yPct}%` }}
      />
      {/* readout */}
      <div className="absolute bottom-2.5 left-4 flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.18em] text-soft">
        <span className="live-dot size-1 rounded-full bg-accent" />
        Tracking
        <span className="tabular-nums text-ink/80">
          {latLabel} · {lonLabel}
        </span>
      </div>
    </div>
  );
}
