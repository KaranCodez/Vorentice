"use client";

import Link from "next/link";
import { useRef } from "react";
import { motion, useSpring } from "motion/react";

/** Magnetic CTA — drifts toward the cursor, springs back on leave. */
export default function EnterButton() {
  const ref = useRef<HTMLDivElement>(null);
  const x = useSpring(0, { stiffness: 200, damping: 16 });
  const y = useSpring(0, { stiffness: 200, damping: 16 });

  function onMove(e: React.MouseEvent) {
    const r = ref.current?.getBoundingClientRect();
    if (!r) return;
    x.set((e.clientX - (r.left + r.width / 2)) * 0.28);
    y.set((e.clientY - (r.top + r.height / 2)) * 0.36);
  }

  function onLeave() {
    x.set(0);
    y.set(0);
  }

  return (
    <motion.div
      ref={ref}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      style={{ x, y }}
      whileTap={{ scale: 0.96 }}
    >
      <Link
        href="/dashboard"
        className="group relative flex items-center gap-3.5 overflow-hidden rounded-full bg-ink py-2 pl-7 pr-2 text-[15px] font-medium text-background shadow-[0_18px_40px_-16px_rgba(12,24,21,0.6)] transition-shadow duration-500 hover:shadow-[0_18px_50px_-12px_rgba(13,148,136,0.55)]"
      >
        {/* shine sweep */}
        <span className="pointer-events-none absolute inset-0 -translate-x-[130%] skew-x-[-20deg] bg-gradient-to-r from-transparent via-white/25 to-transparent transition-transform duration-1000 ease-out group-hover:translate-x-[130%]" />
        Enter Command Center
        <span className="relative flex size-10 items-center justify-center overflow-hidden rounded-full bg-white/15 transition-colors duration-300 group-hover:bg-accent">
          <ArrowIcon className="absolute size-4 transition-all duration-300 group-hover:translate-x-6 group-hover:opacity-0" />
          <ArrowIcon className="absolute size-4 -translate-x-6 opacity-0 transition-all duration-300 group-hover:translate-x-0 group-hover:opacity-100" />
        </span>
      </Link>
    </motion.div>
  );
}

function ArrowIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className} aria-hidden>
      <path
        d="M2 8h11M9 3.5 13.5 8 9 12.5"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
