"use client";

import { motion } from "motion/react";
import { CHOKEPOINTS } from "@/lib/map-data";
import { EASE_OUT } from "@/lib/motion";

const COLOR: Record<string, string> = {
  critical: "#dc2626",
  elevated: "#d97706",
  stable: "#0d9488",
  failover: "#10b981",
};

const TOP3 = [...CHOKEPOINTS].sort((a, b) => b.risk - a.risk).slice(0, 3);

export default function RiskRows({ ready }: { ready: boolean }) {
  return (
    <div className="mt-1.5 space-y-1.5">
      {TOP3.map((cp, i) => {
        const color = COLOR[cp.status];
        return (
          <div key={cp.id} className="group/row">
            <div className="flex items-baseline justify-between font-mono text-[9.5px] uppercase tracking-[0.1em]">
              <span className="text-soft transition-colors duration-200 group-hover/row:text-ink">
                {cp.name}
              </span>
              <span className="font-bold tabular-nums" style={{ color }}>
                {cp.risk}%
              </span>
            </div>
            <div className="mt-0.5 h-[3px] overflow-hidden rounded-full bg-line">
              <motion.div
                className="h-full rounded-full"
                style={{ background: color }}
                initial={{ width: 0 }}
                animate={ready ? { width: `${cp.risk}%` } : {}}
                transition={{ delay: 2.1 + i * 0.12, duration: 1.1, ease: EASE_OUT }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
