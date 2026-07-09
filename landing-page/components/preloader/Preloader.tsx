"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import NumberFlow from "@number-flow/react";
import { EASE_CURTAIN, EASE_OUT } from "@/lib/motion";

const WORD = "VORENTICE".split("");

/**
 * Boot screen: the wordmark assembles letter-by-letter as a simulated
 * telemetry counter runs to 100, then everything lifts and the dark
 * curtain slides up to reveal the hero underneath.
 */
export default function Preloader({ onDone }: { onDone: () => void }) {
  const [progress, setProgress] = useState(0);
  const [leaving, setLeaving] = useState(false);
  const reduced = useReducedMotion();
  const handedOff = useRef(false);

  // Uneven increments — reads like real systems coming online.
  useEffect(() => {
    if (reduced) {
      const t = window.setTimeout(() => {
        setProgress(100);
        setLeaving(true);
      }, 200);
      return () => window.clearTimeout(t);
    }
    let value = 0;
    let timer = 0;
    const tick = () => {
      value = Math.min(100, value + 2 + Math.random() * 12);
      setProgress(Math.round(value));
      timer =
        value < 100
          ? window.setTimeout(tick, 90 + Math.random() * 170)
          : window.setTimeout(() => setLeaving(true), 500);
    };
    timer = window.setTimeout(tick, 350);
    return () => window.clearTimeout(timer);
  }, [reduced]);

  // Let the letters lift out, then hand over to the curtain exit.
  useEffect(() => {
    if (!leaving || handedOff.current) return;
    handedOff.current = true;
    const t = window.setTimeout(onDone, 600);
    return () => window.clearTimeout(t);
  }, [leaving, onDone]);

  return (
    <motion.div
      role="status"
      aria-label="Loading Vorentice"
      className="fixed inset-0 z-[70] flex flex-col items-center justify-center bg-void text-[#eef6f3]"
      exit={{ y: "-100%" }}
      transition={{ duration: 0.95, ease: EASE_CURTAIN }}
    >
      {/* corner instrumentation */}
      <motion.div
        aria-hidden
        className="absolute inset-0 p-6 font-mono text-[9.5px] uppercase tracking-[0.22em] text-white/30 sm:p-8"
        animate={{ opacity: leaving ? 0 : 1 }}
        transition={{ duration: 0.4 }}
      >
        <span className="absolute left-6 top-6 sm:left-8 sm:top-8">
          Initializing intelligence layer
          <span className="live-dot ml-1 inline-block text-accent-bright">▍</span>
        </span>
        <span className="absolute right-6 top-6 sm:right-8 sm:top-8">
          EST · New Delhi
        </span>
        <span className="absolute bottom-6 left-6 sm:bottom-8 sm:left-8">
          Vorentice OS · v2.4
        </span>
        <span className="absolute bottom-6 right-6 sm:bottom-8 sm:right-8">
          Secure channel
        </span>
      </motion.div>

      {/* wordmark */}
      <div
        aria-label="VORENTICE"
        className="flex items-center overflow-hidden px-4 text-[clamp(44px,9vw,118px)] font-black leading-none tracking-[-0.02em]"
      >
        {WORD.map((ch, i) => {
          const revealed = progress >= ((i + 1) / WORD.length) * 92;
          const y = leaving ? "-118%" : revealed ? "0%" : "118%";
          if (ch === "O") {
            return (
              <motion.span
                key={i}
                className="relative mx-[0.05em] inline-flex h-[0.74em] w-[0.74em] items-center justify-center self-center will-change-transform"
                initial={{ y: "118%" }}
                animate={{ y }}
                transition={{
                  duration: 0.7,
                  ease: EASE_OUT,
                  delay: leaving ? i * 0.03 : 0,
                }}
              >
                <span className="absolute inset-0 rounded-full border-[0.055em] border-white/25" />
                <motion.span
                  className="absolute inset-0 rounded-full border-[0.055em] border-transparent border-t-accent-bright"
                  animate={{ rotate: 360 }}
                  transition={{ repeat: Infinity, duration: 1.3, ease: "linear" }}
                />
                <span className="live-dot h-[0.17em] w-[0.17em] rounded-full bg-accent-bright shadow-[0_0_0.4em_rgba(45,212,191,0.9)]" />
              </motion.span>
            );
          }
          return (
            <motion.span
              key={i}
              className="inline-block will-change-transform"
              initial={{ y: "118%" }}
              animate={{ y }}
              transition={{
                duration: 0.7,
                ease: EASE_OUT,
                delay: leaving ? i * 0.03 : 0,
              }}
            >
              {ch}
            </motion.span>
          );
        })}
      </div>

      {/* counter */}
      <motion.div
        className="absolute bottom-10 left-1/2 -translate-x-1/2 font-mono text-4xl font-semibold tabular-nums text-white/90"
        animate={{ opacity: leaving ? 0 : 1, y: leaving ? -14 : 0 }}
        transition={{ duration: 0.4 }}
      >
        <NumberFlow value={progress} />
      </motion.div>

      {/* progress hairline */}
      <motion.div
        aria-hidden
        className="absolute bottom-0 left-0 h-[2px] bg-gradient-to-r from-accent to-accent-bright shadow-[0_0_12px_rgba(45,212,191,0.8)]"
        animate={{ width: `${progress}%`, opacity: leaving ? 0 : 1 }}
        transition={{ width: { duration: 0.3, ease: "easeOut" } }}
      />
    </motion.div>
  );
}
