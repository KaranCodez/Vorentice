"use client";

import { motion } from "motion/react";
import {
  GRATICULE_PATH,
  LAND_PATH,
  MAP_H,
  MAP_W,
  project,
  smoothRoutePath,
} from "@/lib/geo";
import { OCEAN_LABELS, TRADE_ROUTES, type TradeRoute } from "@/lib/map-data";

const ROUTE_STYLE: Record<
  TradeRoute["kind"],
  { stroke: string; width: number; opacity: number; flow: string; flowOpacity: number }
> = {
  primary: {
    stroke: "#0d9488",
    width: 1.9,
    opacity: 0.9,
    flow: "route-flow",
    flowOpacity: 0.95,
  },
  standard: {
    stroke: "#4faea2",
    width: 1.15,
    opacity: 0.55,
    flow: "route-flow-slow",
    flowOpacity: 0.7,
  },
  failover: {
    stroke: "#10b981",
    width: 1.2,
    opacity: 0.3,
    flow: "route-flow-slow",
    flowOpacity: 0.9,
  },
};

export default function WorldMap({ ready }: { ready: boolean }) {
  return (
    <svg
      viewBox={`0 0 ${MAP_W} ${MAP_H}`}
      className="absolute inset-0 h-full w-full"
      role="img"
      aria-label="Global crude-oil trade routes with live chokepoint risk"
    >
      {/* graticule + landmass */}
      <path
        d={GRATICULE_PATH}
        fill="none"
        stroke="#0d9488"
        strokeOpacity={0.07}
        strokeWidth={0.6}
      />
      <motion.path
        d={LAND_PATH}
        fill="#dfe9e5"
        stroke="#c2d3cd"
        strokeWidth={0.6}
        initial={{ opacity: 0 }}
        animate={ready ? { opacity: 1 } : {}}
        transition={{ duration: 1.2, delay: 0.9 }}
      />

      {/* ocean labels */}
      <motion.g
        initial={{ opacity: 0 }}
        animate={ready ? { opacity: 1 } : {}}
        transition={{ duration: 1.2, delay: 1.7 }}
      >
        {OCEAN_LABELS.map((o) => {
          const [x, y] = project(o.coords);
          return (
            <text
              key={o.name}
              x={x}
              y={y}
              textAnchor="middle"
              fontSize={12.5}
              fontStyle="italic"
              fontFamily="Georgia, 'Times New Roman', serif"
              fill="#8fa39c"
              opacity={0.6}
            >
              {o.name}
            </text>
          );
        })}
      </motion.g>

      {/* trade routes: base draw-in + flowing dash overlay + vessels */}
      {TRADE_ROUTES.map((route, ri) => {
        const d = smoothRoutePath(route.waypoints);
        const s = ROUTE_STYLE[route.kind];
        return (
          <g key={route.id}>
            {route.kind === "primary" && (
              // soft glow under the primary artery
              <motion.path
                d={d}
                fill="none"
                stroke={s.stroke}
                strokeWidth={6}
                strokeLinecap="round"
                strokeOpacity={0.13}
                initial={{ opacity: 0 }}
                animate={ready ? { opacity: 1 } : {}}
                transition={{ duration: 1, delay: 2.2 }}
              />
            )}
            <motion.path
              id={`route-${route.id}`}
              d={d}
              fill="none"
              stroke={s.stroke}
              strokeWidth={s.width}
              strokeLinecap="round"
              strokeOpacity={s.opacity}
              initial={{ pathLength: 0 }}
              animate={ready ? { pathLength: 1 } : {}}
              transition={{ duration: 1.7, delay: 1.15 + ri * 0.14, ease: "easeInOut" }}
            />
            <motion.path
              className={s.flow}
              d={d}
              fill="none"
              stroke={s.stroke}
              strokeWidth={s.width + 0.4}
              strokeLinecap="round"
              initial={{ opacity: 0 }}
              animate={ready ? { opacity: s.flowOpacity } : {}}
              transition={{ duration: 1, delay: 2.6 + ri * 0.1 }}
            />
            <motion.g
              initial={{ opacity: 0 }}
              animate={ready ? { opacity: 1 } : {}}
              transition={{ duration: 0.9, delay: 2.9 }}
            >
              {Array.from({ length: route.vessels }).map((_, vi) => (
                <circle
                  key={vi}
                  r={2}
                  fill="#0f766e"
                  stroke="#fbfefd"
                  strokeWidth={0.7}
                >
                  <animateMotion
                    dur={`${route.vesselDuration}s`}
                    repeatCount="indefinite"
                    begin={`${(-(vi * route.vesselDuration) / route.vessels).toFixed(2)}s`}
                  >
                    <mpath href={`#route-${route.id}`} />
                  </animateMotion>
                </circle>
              ))}
            </motion.g>
          </g>
        );
      })}
    </svg>
  );
}
