"use client";

import { memo, useMemo } from "react";
import { motion } from "motion/react";
import {
  GRATICULE_PATH,
  LAND_PATH,
  MAP_H,
  MAP_W,
  project,
  smoothRoutePath,
} from "@/lib/geo";
import type { GraphNode, NodeState, RouteState, Topology } from "@/lib/routeApi";

type Props = {
  topology: Topology;
  state: RouteState;
  mode: "live" | "sandbox";
  hoveredId: string | null;
  selectedId: string | null;
  onHoverNode: (id: string | null) => void;
  onClickNode: (id: string) => void;
  onBackgroundClick: () => void;
};

const NODE_COLOR: Record<NodeState, string> = {
  blue: "#4f7fff",
  green: "#22e39a",
  red: "#ff4d4d",
};

/** Straight projected segment between two node ids. */
function segPath(a: GraphNode, b: GraphNode): string {
  const [ax, ay] = project(a.coords);
  const [bx, by] = project(b.coords);
  return `M${ax},${ay}L${bx},${by}`;
}

function RouteNetworkImpl({
  topology,
  state,
  mode,
  hoveredId,
  selectedId,
  onHoverNode,
  onClickNode,
  onBackgroundClick,
}: Props) {
  const nodeById = useMemo(
    () => new Map(topology.nodes.map((n) => [n.id, n])),
    [topology.nodes]
  );

  const nodeState = (id: string): NodeState => state.node_states[id] ?? "blue";

  // Active corridor as one smooth glowing path through the surviving route.
  const activeCoords = state.active_path
    .map((id) => nodeById.get(id))
    .filter(Boolean)
    .map((n) => (n as GraphNode).coords);
  const activePath =
    activeCoords.length >= 2 ? smoothRoutePath(activeCoords) : "";

  const brokenSet = useMemo(
    () => new Set(state.broken_edges.map((e) => `${e.a}|${e.b}`)),
    [state.broken_edges]
  );
  const isBroken = (a: string, b: string) =>
    brokenSet.has(`${a}|${b}`) || brokenSet.has(`${b}|${a}`);

  const activePairs = useMemo(() => {
    const s = new Set<string>();
    for (let i = 0; i < state.active_path.length - 1; i++) {
      s.add(`${state.active_path[i]}|${state.active_path[i + 1]}`);
    }
    return s;
  }, [state.active_path]);
  const isActiveEdge = (a: string, b: string) =>
    activePairs.has(`${a}|${b}`) || activePairs.has(`${b}|${a}`);

  return (
    <svg
      viewBox={`0 0 ${MAP_W} ${MAP_H}`}
      className="absolute inset-0 h-full w-full"
      role="img"
      aria-label="Global crude-supply network graph with live rerouting"
      onClick={onBackgroundClick}
    >
      <defs>
        <radialGradient id="rn-red-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#ff4d4d" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#ff4d4d" stopOpacity="0" />
        </radialGradient>
        <filter id="rn-soft" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2.4" />
        </filter>
      </defs>

      {/* graticule + landmass (dark command-center basemap) */}
      <path d={GRATICULE_PATH} fill="none" stroke="#1f3b34" strokeOpacity={0.5} strokeWidth={0.5} />
      <path d={LAND_PATH} fill="#0e1c1a" stroke="#1c3630" strokeWidth={0.6} />

      {/* ── EDGES: blue baseline grid ── */}
      <g strokeLinecap="round">
        {topology.edges.map((e) => {
          const a = nodeById.get(e.a);
          const b = nodeById.get(e.b);
          if (!a || !b) return null;
          if (isBroken(e.a, e.b) || isActiveEdge(e.a, e.b)) return null;
          return (
            <path
              key={`base-${e.a}-${e.b}`}
              d={segPath(a, b)}
              stroke={NODE_COLOR.blue}
              strokeOpacity={0.14}
              strokeWidth={0.7}
              fill="none"
            />
          );
        })}
      </g>

      {/* ── BROKEN EDGES: red, fade to dim over 500ms but stay hoverable ── */}
      <g strokeLinecap="round">
        {state.broken_edges.map((e) => {
          const a = nodeById.get(e.a);
          const b = nodeById.get(e.b);
          if (!a || !b) return null;
          const d = segPath(a, b);
          return (
            <motion.path
              key={`broken-${e.a}-${e.b}`}
              d={d}
              stroke={NODE_COLOR.red}
              fill="none"
              strokeWidth={2}
              initial={{ opacity: 1 }}
              animate={{ opacity: 0.6 }}
              transition={{ duration: 0.5 }}
              style={{ filter: "drop-shadow(0 0 3px #ff4d4d)" }}
            />
          );
        })}
      </g>

      {/* ── ACTIVE CORRIDOR: green glow + trace-in + flowing dash ── */}
      {activePath && (
        <g key={state.active_path.join(">")}>
          <path
            d={activePath}
            fill="none"
            stroke={NODE_COLOR.green}
            strokeWidth={5}
            strokeOpacity={0.16}
            strokeLinecap="round"
          />
          <motion.path
            d={activePath}
            fill="none"
            stroke={NODE_COLOR.green}
            strokeWidth={1.9}
            strokeLinecap="round"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={{ duration: 1.1, delay: 0.45, ease: "easeInOut" }}
            style={{ filter: "drop-shadow(0 0 4px #22e39a)" }}
          />
          <motion.path
            className="rn-flow"
            d={activePath}
            fill="none"
            stroke="#eafff6"
            strokeWidth={1.1}
            strokeLinecap="round"
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.85 }}
            transition={{ duration: 0.8, delay: 1.4 }}
          />
        </g>
      )}

      {/* ── NODES ── */}
      <g>
        {topology.nodes.map((n) => {
          const st = nodeState(n.id);
          const color = NODE_COLOR[st];
          const [x, y] = project(n.coords);
          const isHovered = hoveredId === n.id;
          const isSelected = selectedId === n.id;
          const interactive = mode === "sandbox" || st === "red";

          // sizing by role
          const base =
            n.role === "waypoint"
              ? 1.5
              : n.role === "refinery"
                ? 3.4
                : n.role === "source"
                  ? 3.2
                  : 3.0;
          const r = st === "blue" ? base : base + 0.6;
          const opacity =
            st === "blue" ? (n.role === "waypoint" ? 0.4 : 0.72) : 1;

          return (
            <g
              key={n.id}
              transform={`translate(${x},${y})`}
              onMouseEnter={() => onHoverNode(n.id)}
              onMouseLeave={() => onHoverNode(null)}
              onClick={(e) => {
                if (!interactive) return;
                e.stopPropagation();
                onClickNode(n.id);
              }}
              style={{ cursor: interactive ? "pointer" : "default" }}
            >
              {/* red pulsing glow */}
              {st === "red" && (
                <>
                  <circle r={12} fill="url(#rn-red-glow)" filter="url(#rn-soft)">
                    <animate attributeName="r" values="9;15;9" dur="1.8s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.9;0.35;0.9" dur="1.8s" repeatCount="indefinite" />
                  </circle>
                  <circle r={r + 2} fill="none" stroke={color} strokeWidth={0.9} opacity={0.7}>
                    <animate attributeName="r" values={`${r + 1};${r + 6};${r + 1}`} dur="1.8s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.8;0;0.8" dur="1.8s" repeatCount="indefinite" />
                  </circle>
                </>
              )}

              {/* green active subtle blink */}
              {st === "green" && (
                <circle r={r + 3} fill="none" stroke={color} strokeWidth={0.8} opacity={0.5}>
                  <animate attributeName="opacity" values="0.55;0.12;0.55" dur="2.4s" repeatCount="indefinite" />
                </circle>
              )}

              {/* hover / selection ring */}
              {(isHovered || isSelected) && (
                <circle r={r + 4} fill="none" stroke="#ffffff" strokeOpacity={0.65} strokeWidth={0.8} />
              )}

              {/* the node mark */}
              {n.role === "refinery" ? (
                <rect
                  x={-r}
                  y={-r}
                  width={r * 2}
                  height={r * 2}
                  transform="rotate(45)"
                  fill={color}
                  fillOpacity={opacity}
                  stroke="#04110d"
                  strokeWidth={0.7}
                />
              ) : n.role === "chokepoint" ? (
                <circle
                  r={r}
                  fill={st === "blue" ? "#0a1512" : color}
                  fillOpacity={st === "blue" ? 0.9 : opacity}
                  stroke={color}
                  strokeWidth={1.2}
                />
              ) : (
                <circle r={r} fill={color} fillOpacity={opacity} stroke="#04110d" strokeWidth={0.5} />
              )}
            </g>
          );
        })}
      </g>
    </svg>
  );
}

export default memo(RouteNetworkImpl);
