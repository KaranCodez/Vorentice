"use client";

import { motion } from "motion/react";
import { projectPct } from "@/lib/geo";
import { CHOKEPOINTS, REFINERIES, type Chokepoint } from "@/lib/map-data";

const STATUS_COLOR: Record<Chokepoint["status"], string> = {
  critical: "#dc2626",
  elevated: "#d97706",
  stable: "#0d9488",
  failover: "#10b981",
};

/** HTML overlay on top of the SVG — crisp dots, chips and hover tooltips. */
export default function MarkerLayer({ ready }: { ready: boolean }) {
  return (
    <div className="absolute inset-0 z-10">
      {CHOKEPOINTS.map((cp, i) => {
        const color = STATUS_COLOR[cp.status];
        return (
          // outer div owns the centering transform; motion owns scale/opacity
          <div
            key={cp.id}
            className="group absolute -translate-x-1/2 -translate-y-1/2 hover:z-30"
            style={projectPct(cp.coords)}
          >
            <motion.div
              className="relative"
              initial={{ opacity: 0, scale: 0 }}
              animate={ready ? { opacity: 1, scale: 1 } : {}}
              transition={{
                delay: 2.05 + i * 0.09,
                type: "spring",
                stiffness: 320,
                damping: 17,
              }}
            >
              <span
                className="pulse-ring absolute -inset-[7px] rounded-full border"
                style={{ borderColor: color }}
              />
              <span
                className="block size-[9px] cursor-pointer rounded-full border-2 border-white shadow-md transition-transform duration-300 group-hover:scale-[1.55]"
                style={{ background: color }}
              />

              {cp.status === "critical" && (
                <span className="live-dot absolute -top-[26px] left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-alarm px-2 py-0.5 font-mono text-[9.5px] font-bold tracking-wide text-white shadow-lg">
                  {cp.risk}%
                </span>
              )}

              {/* tooltip */}
              <div className="pointer-events-none absolute bottom-[20px] left-1/2 w-[178px] -translate-x-1/2 translate-y-2 scale-95 rounded-lg border border-line bg-white/95 p-2.5 text-left opacity-0 shadow-xl backdrop-blur-sm transition-all duration-300 ease-out group-hover:translate-y-0 group-hover:scale-100 group-hover:opacity-100">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-semibold leading-tight text-ink">
                    {cp.name}
                  </span>
                  <span
                    className="font-mono text-[10px] font-bold"
                    style={{ color }}
                  >
                    {cp.risk}%
                  </span>
                </div>
                <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-line">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${cp.risk}%`, background: color }}
                  />
                </div>
                <p className="mt-1.5 font-mono text-[8.5px] uppercase leading-relaxed tracking-[0.08em] text-soft">
                  {cp.note}
                </p>
              </div>
            </motion.div>
          </div>
        );
      })}

      {REFINERIES.map((rf, i) => (
        <div
          key={rf.name}
          className="group absolute -translate-x-1/2 -translate-y-1/2 hover:z-30"
          style={projectPct(rf.coords)}
        >
          <motion.div
            className="relative flex items-center justify-center"
            initial={{ opacity: 0, scale: 0 }}
            animate={ready ? { opacity: 1, scale: 1 } : {}}
            transition={{
              delay: 2.75 + i * 0.12,
              type: "spring",
              stiffness: 320,
              damping: 17,
            }}
          >
            <span className="block size-[7px] rotate-45 cursor-pointer border border-white bg-warn shadow transition-transform duration-300 group-hover:scale-[1.5]" />
            <div className="pointer-events-none absolute bottom-[16px] left-1/2 -translate-x-1/2 translate-y-1.5 whitespace-nowrap rounded-md border border-line bg-white/95 px-2 py-1 opacity-0 shadow-lg backdrop-blur-sm transition-all duration-300 group-hover:translate-y-0 group-hover:opacity-100">
              <span className="text-[10px] font-semibold text-ink">
                {rf.name} Refinery
              </span>
              <span className="ml-1.5 font-mono text-[8.5px] uppercase tracking-wide text-warn">
                {rf.tag}
              </span>
            </div>
          </motion.div>
        </div>
      ))}
    </div>
  );
}
