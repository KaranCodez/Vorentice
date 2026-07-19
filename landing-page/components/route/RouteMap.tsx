"use client";

import {
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type WheelEvent as ReactWheelEvent,
} from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  GRATICULE_PATH,
  LAND_PATH,
  MAP_H,
  MAP_W,
  project,
  smoothRoutePath,
} from "@/lib/geo";
import type { GraphNode, NodeState, RouteState, Topology } from "@/lib/routeApi";

export type RouteTheme = "dark" | "light";

type Props = {
  topology: Topology;
  state: RouteState;
  mode: "live" | "sandbox";
  theme: RouteTheme;
  panelOpen: boolean;
  hoveredId: string | null;
  selectedId: string | null;
  onHoverNode: (id: string | null) => void;
  onClickNode: (id: string) => void;
  onBackgroundClick: () => void;
};

const DARK = {
  oceanCore: "#0a1c17", oceanEdge: "#03100c",
  landTop: "#16302a", landBot: "#0b1a17", landStroke: "#22463d", coast: "#1f5346",
  graticule: "#173029",
  blue: "#5b8cff", green: "#22e39a", red: "#ff5d5d",
  activeGlow: "#22e39a", activeFlow: "#eafff6", brokenColor: "#ff5d5d",
  latentOpacity: 0.24, ring: "rgba(255,255,255,0.72)",
  markStroke: "#04110d", labelFill: "rgba(235,248,244,0.9)", labelHalo: "rgba(3,14,11,0.92)",
  shadowOpacity: 0.6,
};
const LIGHT = {
  oceanCore: "#dcecf3", oceanEdge: "#bcd6e2",
  landTop: "#f0f4ee", landBot: "#dbe6dc", landStroke: "#b3cabd", coast: "#a7cad6",
  graticule: "#c3d7db",
  blue: "#2f56c8", green: "#059669", red: "#dc2626",
  activeGlow: "#059669", activeFlow: "#065f46", brokenColor: "#dc2626",
  latentOpacity: 0.4, ring: "rgba(12,24,21,0.55)",
  markStroke: "#ffffff", labelFill: "rgba(12,24,21,0.85)", labelHalo: "rgba(255,255,255,0.94)",
  shadowOpacity: 0.32,
};

const NODE_COLORS: Record<RouteTheme, Record<NodeState, string>> = {
  dark:  { blue: DARK.blue,  green: DARK.green,  red: DARK.red  },
  light: { blue: LIGHT.blue, green: LIGHT.green, red: LIGHT.red },
};

// ── pan-zoom math ───────────────────────────────────────────────
const MAX_SCALE = 16;

interface Transform { x: number; y: number; scale: number }

function clampXY(t: Transform, w: number, h: number): Transform {
  const mw = MAP_W * t.scale, mh = MAP_H * t.scale;
  const xMin = Math.min(0, w - mw), xMax = Math.max(0, w - mw);
  const yMin = Math.min(0, h - mh), yMax = Math.max(0, h - mh);
  return {
    scale: t.scale,
    x: Math.max(xMin, Math.min(xMax, t.x)),
    y: Math.max(yMin, Math.min(yMax, t.y)),
  };
}

function segPath(a: GraphNode, b: GraphNode): string {
  const [ax, ay] = project(a.coords);
  const [bx, by] = project(b.coords);
  return `M${ax},${ay}L${bx},${by}`;
}

function RouteMapImpl({
  topology, state, mode, theme, panelOpen,
  hoveredId, selectedId, onHoverNode, onClickNode, onBackgroundClick,
}: Props) {
  const c = theme === "dark" ? DARK : LIGHT;
  const nodeColor = NODE_COLORS[theme];

  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const [size, setSize] = useState({ w: 1200, h: 700 });
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) =>
      setSize({ w: e.contentRect.width, h: e.contentRect.height })
    );
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // ── fit-to-world ──────────────────────────────────────────────
  const minScaleRef = useRef(1);
  const fitTransform = useCallback((w: number, h: number): Transform => {
    const scale = Math.min(w / MAP_W, h / MAP_H) * 0.98;
    minScaleRef.current = scale;
    return { scale, x: (w - MAP_W * scale) / 2, y: (h - MAP_H * scale) / 2 };
  }, []);

  const [xform, setXform] = useState<Transform>(() => fitTransform(1200, 700));
  const sizeRef = useRef(size);
  sizeRef.current = size;

  const hasFitRef = useRef(false);
  useEffect(() => {
    if (hasFitRef.current || size.w < 10) return;
    hasFitRef.current = true;
    setXform(fitTransform(size.w, size.h));
  }, [size, fitTransform]);

  const zoomAt = useCallback((cx: number, cy: number, factor: number) => {
    setXform((t) => {
      const ns = Math.max(minScaleRef.current, Math.min(MAX_SCALE, t.scale * factor));
      const ratio = ns / t.scale;
      return clampXY(
        { scale: ns, x: cx - ratio * (cx - t.x), y: cy - ratio * (cy - t.y) },
        sizeRef.current.w, sizeRef.current.h
      );
    });
  }, []);

  // ── pan / click-vs-drag ───────────────────────────────────────
  const [isDragging, setIsDragging] = useState(false);
  const drag = useRef<{ sx: number; sy: number; moved: boolean; captured: boolean } | null>(null);
  const lastPt = useRef({ x: 0, y: 0 });
  const suppressClick = useRef(false);

  const onPointerDown = useCallback((e: ReactPointerEvent) => {
    if (e.button !== 0) return;
    drag.current = { sx: e.clientX, sy: e.clientY, moved: false, captured: false };
    lastPt.current = { x: e.clientX, y: e.clientY };
  }, []);

  const onPointerMove = useCallback((e: ReactPointerEvent) => {
    const d = drag.current;
    if (!d) return;
    if (!d.moved && Math.abs(e.clientX - d.sx) + Math.abs(e.clientY - d.sy) < 5) return;
    if (!d.moved) { d.moved = true; setIsDragging(true); }
    if (!d.captured) {
      try { (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); d.captured = true; } catch {}
    }
    const dx = e.clientX - lastPt.current.x;
    const dy = e.clientY - lastPt.current.y;
    lastPt.current = { x: e.clientX, y: e.clientY };
    setXform((t) => clampXY({ ...t, x: t.x + dx, y: t.y + dy }, sizeRef.current.w, sizeRef.current.h));
  }, []);

  const onPointerUp = useCallback((e: ReactPointerEvent) => {
    const d = drag.current;
    if (d?.moved) suppressClick.current = true;
    if (d?.captured) { try { (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId); } catch {} }
    drag.current = null;
    setIsDragging(false);
  }, []);

  const onContainerClick = useCallback(() => {
    if (suppressClick.current) { suppressClick.current = false; return; }
    onBackgroundClick();
  }, [onBackgroundClick]);

  const onWheel = useCallback((e: ReactWheelEvent) => {
    e.preventDefault();
    const rect = svgRef.current!.getBoundingClientRect();
    zoomAt(e.clientX - rect.left, e.clientY - rect.top, e.deltaY < 0 ? 1.15 : 1 / 1.15);
  }, [zoomAt]);

  const zoomInBtn  = useCallback(() => zoomAt(sizeRef.current.w / 2, sizeRef.current.h / 2, 1.4), [zoomAt]);
  const zoomOutBtn = useCallback(() => zoomAt(sizeRef.current.w / 2, sizeRef.current.h / 2, 1 / 1.4), [zoomAt]);
  const recenter   = useCallback(() => setXform(fitTransform(sizeRef.current.w, sizeRef.current.h)), [fitTransform]);

  // ── route graph ───────────────────────────────────────────────
  const nodeById = useMemo(() => new Map(topology.nodes.map((n) => [n.id, n])), [topology.nodes]);
  const nodeState = useCallback((id: string): NodeState => state.node_states[id] ?? "blue", [state.node_states]);

  const activeCoords = state.active_path.map((id) => nodeById.get(id)).filter(Boolean).map((n) => (n as GraphNode).coords);
  const activePath = activeCoords.length >= 2 ? smoothRoutePath(activeCoords) : "";

  const brokenSet = useMemo(() => new Set(state.broken_edges.map((e) => `${e.a}|${e.b}`)), [state.broken_edges]);
  const isBroken = (a: string, b: string) => brokenSet.has(`${a}|${b}`) || brokenSet.has(`${b}|${a}`);
  const activePairs = useMemo(() => {
    const s = new Set<string>();
    for (let i = 0; i < state.active_path.length - 1; i++) s.add(`${state.active_path[i]}|${state.active_path[i + 1]}`);
    return s;
  }, [state.active_path]);
  const isActiveEdge = (a: string, b: string) => activePairs.has(`${a}|${b}`) || activePairs.has(`${b}|${a}`);

  // a broken edge's canonical disruption node = its red endpoint
  const focusOf = (a: string, b: string) =>
    nodeState(a) === "red" ? a : nodeState(b) === "red" ? b : a;

  const deep    = selectedId ? state.deep_dive[selectedId] : undefined;
  const selNode = selectedId ? nodeById.get(selectedId)    : null;
  const hovNode = hoveredId  ? nodeById.get(hoveredId)     : null;
  const hovSpark = hoveredId ? state.sparks[hoveredId]     : undefined;

  const toScreen = useCallback(([lon, lat]: [number, number]) => {
    const [mx, my] = project([lon, lat]);
    return { left: mx * xform.scale + xform.x, top: my * xform.scale + xform.y };
  }, [xform]);
  const hovPx = hovNode ? toScreen(hovNode.coords) : null;
  const selPx = selNode ? toScreen(selNode.coords) : null;

  const s = xform.scale;
  const showLabel = (n: GraphNode) =>
    n.role !== "waypoint" ? s >= 1.7 : s >= 4.6;

  return (
    <div className="absolute inset-0 overflow-hidden">
      <div
        ref={containerRef}
        className="absolute inset-0 touch-none"
        style={{ cursor: isDragging ? "grabbing" : "grab" }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onWheel={onWheel}
        onClick={onContainerClick}
      >
        <svg
          ref={svgRef}
          viewBox={`0 0 ${size.w} ${size.h}`}
          width={size.w}
          height={size.h}
          className="absolute inset-0 select-none"
        >
          <defs>
            <radialGradient id="ra-ocean" cx="50%" cy="42%" r="78%">
              <stop offset="0%" stopColor={c.oceanCore} />
              <stop offset="100%" stopColor={c.oceanEdge} />
            </radialGradient>
            <linearGradient id="ra-land" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={c.landTop} />
              <stop offset="100%" stopColor={c.landBot} />
            </linearGradient>
            <radialGradient id="ra-red-glow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor={c.red} stopOpacity="0.55" />
              <stop offset="100%" stopColor={c.red} stopOpacity="0" />
            </radialGradient>
            <filter id="ra-node-shadow" x="-70%" y="-70%" width="240%" height="240%">
              <feDropShadow dx="0" dy={1 / s} stdDeviation={0.9 / s}
                floodColor="#000" floodOpacity={c.shadowOpacity} />
            </filter>
            <radialGradient id="ra-vignette" cx="50%" cy="50%" r="72%">
              <stop offset="0%" stopColor="#000" stopOpacity="0" />
              <stop offset="78%" stopColor="#000" stopOpacity="0" />
              <stop offset="100%" stopColor="#000" stopOpacity={theme === "dark" ? 0.42 : 0.14} />
            </radialGradient>
          </defs>

          {/* ocean */}
          <rect width={size.w} height={size.h} fill="url(#ra-ocean)" />

          <g transform={`translate(${xform.x},${xform.y}) scale(${s})`}>
            {/* graticule */}
            <path d={GRATICULE_PATH} fill="none" stroke={c.graticule} strokeOpacity={0.55} strokeWidth={0.5 / s} />

            {/* coastal shelf halo → depth */}
            <path d={LAND_PATH} fill="none" stroke={c.coast} strokeOpacity={0.35} strokeWidth={5 / s} strokeLinejoin="round" />
            {/* landmass with vertical light gradient */}
            <path d={LAND_PATH} fill="url(#ra-land)" stroke={c.landStroke} strokeWidth={0.7 / s} strokeLinejoin="round" />

            {/* latent edges */}
            <g strokeLinecap="round">
              {topology.edges.map((e) => {
                const a = nodeById.get(e.a), b = nodeById.get(e.b);
                if (!a || !b || isBroken(e.a, e.b) || isActiveEdge(e.a, e.b)) return null;
                return (
                  <path key={`base-${e.a}-${e.b}`} d={segPath(a, b)}
                    stroke={nodeColor.blue} strokeOpacity={c.latentOpacity}
                    strokeWidth={0.85 / s} fill="none" />
                );
              })}
            </g>

            {/* broken edges — hoverable + clickable, marching danger stripes */}
            <g strokeLinecap="round">
              {state.broken_edges.map((e) => {
                const a = nodeById.get(e.a), b = nodeById.get(e.b);
                if (!a || !b) return null;
                const focus = focusOf(e.a, e.b);
                const d = segPath(a, b);
                return (
                  <g key={`broken-${e.a}-${e.b}`}
                    onMouseEnter={(ev) => { ev.stopPropagation(); onHoverNode(focus); }}
                    onMouseLeave={() => onHoverNode(null)}
                    onClick={(ev) => { ev.stopPropagation(); onClickNode(focus); }}
                    style={{ cursor: "pointer" }}
                  >
                    <path d={d} stroke="transparent" strokeWidth={11 / s} fill="none" />
                    <path d={d} stroke={c.brokenColor} strokeOpacity={0.22} strokeWidth={6 / s} fill="none" />
                    <motion.path d={d} stroke={c.brokenColor} fill="none"
                      strokeWidth={2.2 / s}
                      strokeDasharray={`${7 / s} ${5 / s}`}
                      animate={{ strokeDashoffset: [0, -24 / s] }}
                      transition={{ duration: 0.9, repeat: Infinity, ease: "linear" }}
                      style={{ filter: `drop-shadow(0 0 ${2.5 / s}px ${c.brokenColor})` }} />
                  </g>
                );
              })}
            </g>

            {/* active corridor */}
            {activePath && (
              <g key={state.active_path.join(">")}>
                <path d={activePath} fill="none" stroke={c.activeGlow}
                  strokeWidth={8 / s} strokeOpacity={0.16} strokeLinecap="round" />
                <motion.path d={activePath} fill="none" stroke={c.green}
                  strokeWidth={2.6 / s} strokeLinecap="round"
                  initial={{ pathLength: 0, opacity: 0 }}
                  animate={{ pathLength: 1, opacity: 1 }}
                  transition={{ duration: 1.1, delay: 0.25, ease: "easeInOut" }}
                  style={{ filter: `drop-shadow(0 0 ${4 / s}px ${c.activeGlow})` }} />
                <motion.path className="rn-flow" d={activePath} fill="none"
                  stroke={c.activeFlow} strokeWidth={1.5 / s} strokeLinecap="round"
                  initial={{ opacity: 0 }} animate={{ opacity: 0.9 }}
                  transition={{ duration: 0.8, delay: 1.25 }} />
              </g>
            )}

            {/* nodes */}
            {topology.nodes.map((n, i) => {
              const st = nodeState(n.id);
              const color = nodeColor[st];
              const [x, y] = project(n.coords);
              const isHov = hoveredId === n.id;
              const isSel = selectedId === n.id;
              const interactive = mode === "sandbox" || st === "red";
              const base = n.role === "waypoint" ? 1.7 : n.role === "refinery" ? 3.9 : n.role === "source" ? 3.6 : 3.3;
              const r = (st === "blue" ? base : base + 0.7) / s;
              const opacity = st === "blue" ? (n.role === "waypoint" ? 0.5 : 0.8) : 1;

              return (
                <g key={n.id} transform={`translate(${x},${y})`}
                  onMouseEnter={(e) => { e.stopPropagation(); onHoverNode(n.id); }}
                  onMouseLeave={() => onHoverNode(null)}
                  onClick={(e) => { if (!interactive) return; e.stopPropagation(); onClickNode(n.id); }}
                  style={{ cursor: interactive ? "pointer" : "default" }}
                >
                  <motion.g
                    initial={{ scale: 0, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: Math.min(i * 0.011, 0.5), type: "spring", stiffness: 260, damping: 18 }}
                  >
                    {/* red pulse */}
                    {st === "red" && (
                      <>
                        <circle r={12 / s} fill="url(#ra-red-glow)">
                          <animate attributeName="r" values={`${8 / s};${17 / s};${8 / s}`} dur="1.8s" repeatCount="indefinite" />
                          <animate attributeName="opacity" values="0.85;0.2;0.85" dur="1.8s" repeatCount="indefinite" />
                        </circle>
                        <circle r={r + 2 / s} fill="none" stroke={color} strokeWidth={0.9 / s} opacity={0.7}>
                          <animate attributeName="r" values={`${r + 1 / s};${r + 7 / s};${r + 1 / s}`} dur="1.8s" repeatCount="indefinite" />
                          <animate attributeName="opacity" values="0.8;0;0.8" dur="1.8s" repeatCount="indefinite" />
                        </circle>
                      </>
                    )}
                    {/* green idle blink */}
                    {st === "green" && (
                      <circle r={r + 3 / s} fill="none" stroke={color} strokeWidth={0.8 / s} opacity={0.5}>
                        <animate attributeName="opacity" values="0.55;0.12;0.55" dur="2.4s" repeatCount="indefinite" />
                      </circle>
                    )}
                    {/* hover/select ring */}
                    {(isHov || isSel) && (
                      <circle r={r + 4 / s} fill="none" stroke={c.ring} strokeWidth={1 / s} />
                    )}
                    {/* mark */}
                    {n.role === "refinery" ? (
                      <rect x={-r} y={-r} width={r * 2} height={r * 2} transform="rotate(45)"
                        fill={color} fillOpacity={opacity} stroke={c.markStroke} strokeWidth={0.7 / s}
                        filter="url(#ra-node-shadow)" />
                    ) : n.role === "chokepoint" ? (
                      <circle r={r}
                        fill={st === "blue" ? (theme === "dark" ? "#0a1512" : "#eef5ee") : color}
                        fillOpacity={st === "blue" ? 0.92 : opacity}
                        stroke={color} strokeWidth={1.4 / s} filter="url(#ra-node-shadow)" />
                    ) : (
                      <circle r={r} fill={color} fillOpacity={opacity}
                        stroke={c.markStroke} strokeWidth={0.5 / s}
                        filter={n.role === "waypoint" ? undefined : "url(#ra-node-shadow)"} />
                    )}

                    {/* label */}
                    {showLabel(n) && (
                      <text x={r + 5 / s} y={0} dominantBaseline="middle"
                        fontSize={10 / s} fontFamily="var(--font-sans, system-ui)"
                        fontWeight={st !== "blue" ? 600 : 500}
                        fill={st !== "blue" ? color : c.labelFill}
                        style={{ pointerEvents: "none" }}
                        paintOrder="stroke" stroke={c.labelHalo} strokeWidth={3 / s}>
                        {n.name}
                      </text>
                    )}
                  </motion.g>
                </g>
              );
            })}
          </g>

          {/* screen-space vignette for depth */}
          <rect width={size.w} height={size.h} fill="url(#ra-vignette)" pointerEvents="none" />
        </svg>
      </div>

      {/* ── hover tooltip ── */}
      <AnimatePresence>
        {hovNode && hoveredId !== selectedId && hovPx && (
          <motion.div key={`tip-${hoveredId}`}
            initial={{ opacity: 0, y: 6, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, scale: 0.96 }}
            transition={{ duration: 0.14 }}
            className="pointer-events-none absolute z-30 w-max max-w-[250px]"
            style={{ left: hovPx.left, top: hovPx.top - 15, transform: "translate(-50%, -100%)" }}
          >
            <div className="rounded-lg border border-[var(--ra-border)] bg-[var(--ra-surface-solid)] px-2.5 py-1.5 shadow-xl">
              <div className="flex items-baseline gap-1.5">
                <span className="text-[12.5px] font-semibold text-[var(--ra-text)]">{hovNode.name}</span>
                <span className="font-mono text-[8.5px] uppercase tracking-wider text-[var(--ra-faint)]">{hovNode.role}</span>
              </div>
              {hovSpark
                ? <div className="mt-0.5 text-[11px] leading-snug text-[var(--ra-bad)]">⚡ {hovSpark}</div>
                : <div className="mt-0.5 font-mono text-[9.5px] text-[var(--ra-faint)]">{hovNode.country || hovNode.region}</div>}
              {mode === "sandbox" && (
                <div className="mt-0.5 font-mono text-[9px] text-[var(--ra-warn)]">
                  click to {nodeState(hoveredId!) === "red" ? "restore" : "disrupt"}
                </div>
              )}
              {hovSpark && (
                <div className="mt-0.5 font-mono text-[8.5px] uppercase tracking-wide text-[var(--ra-faint)]">
                  click to lock deep-dive
                </div>
              )}
            </div>
            <div className="mx-auto -mt-px size-2 w-2 rotate-45 border-b border-r border-[var(--ra-border)] bg-[var(--ra-surface-solid)]" style={{ marginTop: -4 }} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── deep-dive lock ── */}
      <AnimatePresence>
        {deep && selNode && selPx && (
          <motion.div key={`deep-${selectedId}`}
            initial={{ opacity: 0, scale: 0.94, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96 }}
            transition={{ type: "spring", stiffness: 320, damping: 26 }}
            className="ra-scroll pointer-events-auto absolute z-40 max-h-[52vh] w-[292px] overflow-y-auto overscroll-contain rounded-xl border border-[var(--ra-bad-border)] bg-[var(--ra-surface-solid)] shadow-2xl"
            style={{ left: selPx.left, top: selPx.top - 15, transform: "translate(-50%, -100%)" }}
            onClick={(e) => e.stopPropagation()}
            onPointerDown={(e) => e.stopPropagation()}
            onWheel={(e) => e.stopPropagation()}
          >
            <div className="sticky top-0 flex items-start justify-between gap-2 border-b border-[var(--ra-border)] bg-[var(--ra-bad-wash)] px-3.5 py-2.5 backdrop-blur">
              <div>
                <div className="flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-widest text-[var(--ra-bad)]">
                  <span className="inline-block size-1.5 animate-pulse rounded-full bg-[var(--ra-bad)]" />
                  Deep-Dive Lock · {deep.status.replace("_", " ")}
                </div>
                <div className="mt-0.5 text-[13.5px] font-semibold leading-tight text-[var(--ra-text)]">{deep.header}</div>
              </div>
              <button onClick={onBackgroundClick} aria-label="Close"
                className="mt-0.5 grid size-5 shrink-0 place-items-center rounded text-[var(--ra-faint)] hover:bg-[var(--ra-hover)] hover:text-[var(--ra-text)]">
                <svg viewBox="0 0 12 12" className="size-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M3 3l6 6M9 3l-6 6" /></svg>
              </button>
            </div>
            <div className="flex flex-col gap-2.5 px-3.5 py-3 text-[11.5px]">
              <DeepRow label="The Spark" value={deep.spark} accent />
              <DeepRow label="Alternative crude route" value={deep.alt_source_name || "—"} />
              <DeepRow label="Draft limit" value={`${deep.min_draft_m} m @ ${deep.min_draft_node}`} />
              <DeepRow label="Transit penalty" value={`+${deep.added_days} days`} />
              {deep.downstream.length > 0 && (
                <div>
                  <div className="font-mono text-[8.5px] uppercase tracking-wider text-[var(--ra-faint)]">Downstream impact</div>
                  <ol className="mt-1 flex flex-col gap-1">
                    {deep.downstream.map((d, i) => (
                      <li key={i} className="flex items-start gap-1.5 text-[var(--ra-dim)]">
                        <span className="mt-px font-mono text-[9px] text-[var(--ra-bad)]">{i + 1}</span>
                        <span className="leading-snug">{d}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── zoom / recenter ── */}
      <div className={`absolute bottom-6 z-20 flex flex-col overflow-hidden rounded-xl border border-[var(--ra-border)] bg-[var(--ra-surface)] shadow-lg backdrop-blur-md transition-[right] duration-300 ${panelOpen ? "right-[396px] max-md:right-4" : "right-4"}`}>
        <MapButton label="Zoom in" onClick={zoomInBtn}><path d="M8 3.5v9M3.5 8h9" /></MapButton>
        <div className="h-px bg-[var(--ra-border)]" />
        <MapButton label="Zoom out" onClick={zoomOutBtn}><path d="M3.5 8h9" /></MapButton>
        <div className="h-px bg-[var(--ra-border)]" />
        <MapButton label="Recenter" onClick={recenter}>
          <circle cx="8" cy="8" r="2.2" />
          <path d="M8 1.8v2.4M8 11.8v2.4M1.8 8h2.4M11.8 8h2.4" />
        </MapButton>
      </div>

      {/* ── zoom badge ── */}
      <div className="pointer-events-none absolute bottom-6 left-4 z-20 rounded-md border border-[var(--ra-border)] bg-[var(--ra-surface)] px-2 py-0.5 font-mono text-[10px] text-[var(--ra-faint)] backdrop-blur">
        ×{s.toFixed(1)}
      </div>
    </div>
  );
}

function MapButton({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={(e) => { e.stopPropagation(); onClick(); }} aria-label={label} title={label}
      className="grid size-10 place-items-center text-[var(--ra-dim)] transition-colors hover:bg-[var(--ra-hover)] hover:text-[var(--ra-text)]">
      <svg viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">{children}</svg>
    </button>
  );
}

function DeepRow({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <div className="font-mono text-[8.5px] uppercase tracking-wider text-[var(--ra-faint)]">{label}</div>
      <div className={`mt-0.5 leading-snug ${accent ? "text-[var(--ra-text)]" : "text-[var(--ra-dim)]"}`}>{value}</div>
    </div>
  );
}

export default memo(RouteMapImpl);
