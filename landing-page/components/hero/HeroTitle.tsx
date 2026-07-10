"use client";

import { useRef } from "react";
import { motion } from "motion/react";
import TitlePaint from "./TitlePaint";
import { EASE_OUT } from "@/lib/motion";

const LETTERS = "VORENTICE".split("");

/**
 * Masked letter-rise entrance; after reveal, TitlePaint lets the cursor
 * "paint" the hidden command layer inside the glyphs.
 */
export default function HeroTitle({ ready }: { ready: boolean }) {
  const host = useRef<HTMLDivElement>(null);

  return (
    <div ref={host} className="relative cursor-crosshair select-none">
      <h1
        aria-label="VORENTICE"
        className="font-wordmark flex overflow-hidden pb-1 text-[clamp(46px,7.6vw,104px)] font-extrabold leading-[1.04] tracking-[0.005em] text-ink"
      >
        {LETTERS.map((ch, i) => (
          <motion.span
            key={i}
            aria-hidden
            data-paint-letter={ch}
            className="inline-block will-change-transform"
            initial={{ y: "112%" }}
            animate={ready ? { y: "0%" } : {}}
            transition={{ duration: 1, ease: EASE_OUT, delay: 0.42 + i * 0.045 }}
          >
            {ch}
          </motion.span>
        ))}
      </h1>
      <TitlePaint ready={ready} host={host} />
    </div>
  );
}
