"use client";

import { motion } from "motion/react";
import { EASE_OUT } from "@/lib/motion";

export default function Tagline({ ready }: { ready: boolean }) {
  return (
    <>
      <motion.p
        initial={{ opacity: 0, y: 18, filter: "blur(8px)" }}
        animate={ready ? { opacity: 1, y: 0, filter: "blur(0px)" } : {}}
        transition={{ duration: 0.9, delay: 0.95, ease: EASE_OUT }}
        className="mt-3 text-lg font-normal text-soft sm:text-xl md:text-[22px]"
      >
        The Operating Layer for Trusted Decisions.
      </motion.p>
      <motion.p
        initial={{ opacity: 0, y: 12 }}
        animate={ready ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 0.8, delay: 1.15, ease: EASE_OUT }}
        className="mt-2 font-mono text-[10.5px] uppercase tracking-[0.22em] text-faint"
      >
        Autonomous crude-supply intelligence · before the market feels it
      </motion.p>
    </>
  );
}
