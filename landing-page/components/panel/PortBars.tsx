"use client";

import { motion } from "motion/react";
import { EASE_OUT } from "@/lib/motion";

const BARS = [58, 72, 49, 80, 64, 90, 76, 68, 84, 60, 88, 71];

export default function PortBars({ ready }: { ready: boolean }) {
  return (
    <div className="mt-1.5 flex h-8 items-end gap-[5px]" aria-hidden>
      {BARS.map((h, i) => (
        <motion.div
          key={i}
          className="h-full flex-1 origin-bottom rounded-[3px] bg-gradient-to-t from-accent/60 to-accent-bright/70 transition-colors duration-300 hover:from-accent hover:to-accent-bright"
          initial={{ scaleY: 0 }}
          animate={ready ? { scaleY: h / 100 } : {}}
          transition={{ delay: 1.95 + i * 0.05, duration: 0.7, ease: EASE_OUT }}
        />
      ))}
    </div>
  );
}
