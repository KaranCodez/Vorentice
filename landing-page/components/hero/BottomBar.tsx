"use client";

import { motion } from "motion/react";
import EnterButton from "./EnterButton";
import { AGENTS } from "@/lib/map-data";
import { EASE_OUT } from "@/lib/motion";

export default function BottomBar({ ready }: { ready: boolean }) {
  return (
    <motion.footer
      initial={{ opacity: 0, y: 20 }}
      animate={ready ? { opacity: 1, y: 0 } : {}}
      transition={{ delay: 1.35, duration: 0.9, ease: EASE_OUT }}
      className="relative z-10 mx-auto mt-auto grid w-full max-w-[1060px] grid-cols-1 items-center gap-5 pb-4 pt-3 md:grid-cols-3"
    >
      <div className="hidden flex-col gap-1 font-mono text-[9.5px] uppercase tracking-[0.16em] text-faint md:flex">
        <span className="text-soft">4 autonomous agents</span>
        <span>
          {AGENTS.map((a) => a.name.replace(" Agent", "")).join(" · ")}
        </span>
      </div>
      <div className="flex justify-center">
        <EnterButton />
      </div>
      <div className="hidden flex-col gap-1 text-right font-mono text-[9.5px] uppercase tracking-[0.16em] text-faint md:flex">
        <span className="text-soft">Monitoring 24/7</span>
        <span>100+ ports · 8 chokepoints · New Delhi</span>
      </div>
    </motion.footer>
  );
}
