"use client";

import { motion } from "motion/react";

const VALUES = [12, 16, 14, 19, 17, 22, 20, 25, 23, 27, 24, 28, 26, 30, 29];

const W = 100;
const H = 30;
const MAX = 32;

const pts = VALUES.map((v, i) => [
  (i / (VALUES.length - 1)) * W,
  H - (v / MAX) * (H - 4),
]);
const line = `M${pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join("L")}`;
const area = `${line}L${W},${H}L0,${H}Z`;

export default function Sparkline({ ready }: { ready: boolean }) {
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className="mt-1.5 h-7 w-full"
      aria-hidden
    >
      <defs>
        <linearGradient id="spark-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#14b8a6" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#14b8a6" stopOpacity="0" />
        </linearGradient>
      </defs>
      <motion.path
        d={area}
        fill="url(#spark-fill)"
        initial={{ opacity: 0 }}
        animate={ready ? { opacity: 1 } : {}}
        transition={{ delay: 2.5, duration: 1 }}
      />
      <motion.path
        d={line}
        fill="none"
        stroke="#0d9488"
        strokeWidth={1.4}
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
        initial={{ pathLength: 0 }}
        animate={ready ? { pathLength: 1 } : {}}
        transition={{ delay: 1.75, duration: 1.5, ease: "easeInOut" }}
      />
    </svg>
  );
}
