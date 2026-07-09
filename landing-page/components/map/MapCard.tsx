"use client";

import { useRef } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "motion/react";
import WorldMap from "./WorldMap";
import MarkerLayer from "./MarkerLayer";
import Ticker from "./Ticker";
import CursorReadout, { useMapCursor } from "./CursorReadout";
import OpsPanel from "@/components/panel/OpsPanel";
import { EASE_OUT } from "@/lib/motion";

/**
 * The instrument: world map + telemetry panel + live feed, in one card
 * that tilts a couple of degrees toward the cursor.
 */
export default function MapCard({ ready }: { ready: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const mx = useMotionValue(0.5);
  const my = useMotionValue(0.5);
  const rotateX = useSpring(useTransform(my, [0, 1], [1.7, -1.7]), {
    stiffness: 90,
    damping: 18,
  });
  const rotateY = useSpring(useTransform(mx, [0, 1], [-2.4, 2.4]), {
    stiffness: 90,
    damping: 18,
  });

  function onMove(e: React.MouseEvent) {
    const r = ref.current?.getBoundingClientRect();
    if (!r) return;
    mx.set((e.clientX - r.left) / r.width);
    my.set((e.clientY - r.top) / r.height);
  }

  function onLeave() {
    mx.set(0.5);
    my.set(0.5);
  }

  const mapCursor = useMapCursor();

  return (
    <motion.div
      initial={{ opacity: 0, y: 44, scale: 0.97 }}
      animate={ready ? { opacity: 1, y: 0, scale: 1 } : {}}
      transition={{ duration: 1.15, delay: 0.65, ease: EASE_OUT }}
      className="relative"
      style={{ perspective: 1400 }}
    >
      {/* teal bloom behind the card */}
      <motion.div
        aria-hidden
        initial={{ opacity: 0 }}
        animate={ready ? { opacity: 1 } : {}}
        transition={{ duration: 1.8, delay: 1.5 }}
        className="absolute -inset-8 -z-10 rounded-[40px]"
        style={{
          background:
            "radial-gradient(56% 64% at 50% 44%, rgba(20,184,166,0.42), transparent 70%)",
          filter: "blur(30px)",
        }}
      />

      <motion.div
        ref={ref}
        onMouseMove={onMove}
        onMouseLeave={onLeave}
        style={{ rotateX, rotateY, transformStyle: "preserve-3d" }}
        className="overflow-hidden rounded-2xl border border-line bg-card shadow-[0_24px_70px_-28px_rgba(12,24,21,0.35)]"
      >
        <div className="grid md:grid-cols-[minmax(0,1fr)_246px]">
          <div className="relative">
            <div
              className="relative aspect-[1000/560] w-full"
              onMouseMove={mapCursor.onMouseMove}
              onMouseLeave={mapCursor.onMouseLeave}
            >
              <WorldMap ready={ready} />
              <MarkerLayer ready={ready} />
              <CursorReadout cursor={mapCursor.cursor} />
            </div>

            {/* map header */}
            <div className="pointer-events-none absolute left-4 top-3 z-20 text-left font-mono uppercase">
              <p className="text-[10px] font-semibold tracking-[0.2em] text-ink/80">
                Dynamic route &amp; supply map
              </p>
              <p className="mt-0.5 text-[8.5px] tracking-[0.18em] text-faint">
                Knowledge-graph digital twin · live
              </p>
            </div>

            {/* legend */}
            <div className="pointer-events-none absolute right-4 top-3 z-20 hidden flex-col gap-1.5 font-mono text-[8.5px] uppercase tracking-[0.16em] text-soft sm:flex">
              <span className="flex items-center justify-end gap-2">
                Primary artery
                <span className="h-[2.5px] w-6 rounded-full bg-accent" />
              </span>
              <span className="flex items-center justify-end gap-2">
                Active route
                <span className="h-[2px] w-6 rounded-full bg-flow/70" />
              </span>
              <span className="flex items-center justify-end gap-2">
                Failover · armed
                <span
                  className="h-[2px] w-6 rounded-full"
                  style={{
                    background:
                      "repeating-linear-gradient(to right, #10b981 0 4px, transparent 4px 7px)",
                  }}
                />
              </span>
            </div>
          </div>

          <OpsPanel ready={ready} />
        </div>

        <Ticker ready={ready} />
      </motion.div>
    </motion.div>
  );
}
