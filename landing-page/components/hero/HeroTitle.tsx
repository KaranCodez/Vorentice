"use client";

import { motion } from "motion/react";
import { EASE_OUT } from "@/lib/motion";

const LETTERS = "VORENTICE".split("");

export default function HeroTitle({ ready }: { ready: boolean }) {
  return (
    <h1
      aria-label="VORENTICE"
      className="flex overflow-hidden pb-1 text-[clamp(48px,8vw,110px)] font-black leading-[1.02] tracking-[-0.035em] text-ink"
    >
      {LETTERS.map((ch, i) => (
        <motion.span
          key={i}
          aria-hidden
          className="inline-block cursor-default will-change-transform"
          initial={{ y: "112%" }}
          animate={ready ? { y: "0%" } : {}}
          transition={{ duration: 1, ease: EASE_OUT, delay: 0.42 + i * 0.045 }}
          whileHover={{
            y: -10,
            color: "#0d9488",
            transition: { type: "spring", stiffness: 480, damping: 17 },
          }}
        >
          {ch}
        </motion.span>
      ))}
    </h1>
  );
}
