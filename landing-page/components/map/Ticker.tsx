"use client";

import { motion } from "motion/react";
import { TICKER_ITEMS } from "@/lib/map-data";

/** Marquee of AI-filtered alerts along the bottom edge of the card. */
export default function Ticker({ ready }: { ready: boolean }) {
  const items = [...TICKER_ITEMS, ...TICKER_ITEMS];
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={ready ? { opacity: 1 } : {}}
      transition={{ duration: 0.8, delay: 2.3 }}
      className="relative flex h-9 items-stretch border-t border-line"
    >
      <div className="flex shrink-0 items-center gap-2 border-r border-line bg-mint/60 px-3">
        <span className="live-dot size-1.5 rounded-full bg-alarm" />
        <span className="font-mono text-[9.5px] font-semibold uppercase tracking-[0.18em] text-ink">
          Live feed
        </span>
      </div>
      <div
        className="ticker-viewport relative flex-1 overflow-hidden"
        style={{
          maskImage:
            "linear-gradient(to right, transparent, black 4%, black 96%, transparent)",
          WebkitMaskImage:
            "linear-gradient(to right, transparent, black 4%, black 96%, transparent)",
        }}
      >
        <div className="ticker-track flex h-full w-max items-center gap-10 pl-6">
          {items.map((item, i) => (
            <span
              key={i}
              className={`flex items-center gap-10 whitespace-nowrap font-mono text-[10px] uppercase tracking-[0.14em] ${
                item.startsWith("CRITICAL") ? "text-alarm" : "text-soft"
              }`}
            >
              {item}
              <span aria-hidden className="text-[8px] text-accent/60">
                ◆
              </span>
            </span>
          ))}
        </div>
      </div>
    </motion.div>
  );
}
