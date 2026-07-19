"use client";

import {
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Canvas, useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { Line, Html, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { geoContains } from "d3-geo";
import { feature } from "topojson-client";
import worldTopo from "world-atlas/countries-110m.json";
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

// ── theme palettes ──────────────────────────────────────────────
const THEME = {
  dark: {
    bg: "#04100d", ocean: "#0b211c", oceanEmissive: "#08312a",
    land: "#2ee6a4", atmosphere: "#25d3a6",
    blue: "#5b8cff", green: "#22e39a", red: "#ff5d5d",
    latent: "#5b8cff", latentOpacity: 0.28,
    graticule: "#1c473d",
  },
  light: {
    bg: "#e3eef2", ocean: "#c4dde8", oceanEmissive: "#a9ccd8",
    land: "#2f6fd0", atmosphere: "#7fb4d8",
    blue: "#2f56c8", green: "#059669", red: "#dc2626",
    latent: "#2f56c8", latentOpacity: 0.32,
    graticule: "#aecad6",
  },
} as const;

const R = 1; // globe radius

// ── lon/lat → sphere vector ─────────────────────────────────────
function ll2v3(lon: number, lat: number, r = R): THREE.Vector3 {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);
  return new THREE.Vector3(
    -r * Math.sin(phi) * Math.cos(theta),
    r * Math.cos(phi),
    r * Math.sin(phi) * Math.sin(theta)
  );
}

// ── great-circle arc with altitude bump ─────────────────────────
function greatCircle(
  a: [number, number],
  b: [number, number],
  segments = 40,
  liftScale = 0.35
): THREE.Vector3[] {
  const va = ll2v3(a[0], a[1]).normalize();
  const vb = ll2v3(b[0], b[1]).normalize();
  const angle = va.angleTo(vb);
  const maxAlt = angle * liftScale; // longer hops arc higher
  const pts: THREE.Vector3[] = [];
  const q = new THREE.Quaternion();
  for (let i = 0; i <= segments; i++) {
    const t = i / segments;
    q.slerpQuaternions(
      new THREE.Quaternion(), // identity
      new THREE.Quaternion().setFromUnitVectors(va, vb),
      t
    );
    const v = va.clone().applyQuaternion(q).normalize();
    const alt = Math.sin(Math.PI * t) * maxAlt;
    v.multiplyScalar(R + alt);
    pts.push(v);
  }
  return pts;
}

// ── land dot-matrix (offline, computed once) ────────────────────
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const topo = worldTopo as any;
const LAND = feature(topo, topo.objects.countries) as unknown as GeoJSON.GeoJSON;

let LAND_DOTS: Float32Array | null = null;
function landDots(): Float32Array {
  if (LAND_DOTS) return LAND_DOTS;
  const step = 2.2;
  const pts: number[] = [];
  for (let lat = -78; lat <= 84; lat += step) {
    // even angular density: skip lon steps proportional to cos(lat)
    const lonStep = step / Math.max(0.2, Math.cos((lat * Math.PI) / 180));
    for (let lon = -180; lon < 180; lon += lonStep) {
      if (geoContains(LAND, [lon, lat])) {
        const v = ll2v3(lon, lat, R + 0.004);
        pts.push(v.x, v.y, v.z);
      }
    }
  }
  LAND_DOTS = new Float32Array(pts);
  return LAND_DOTS;
}

// circular sprite for the land points
let DOT_TEX: THREE.CanvasTexture | null = null;
function dotTexture(): THREE.CanvasTexture {
  if (DOT_TEX) return DOT_TEX;
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const ctx = c.getContext("2d")!;
  const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.55, "rgba(255,255,255,1)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.arc(32, 32, 32, 0, Math.PI * 2);
  ctx.fill();
  DOT_TEX = new THREE.CanvasTexture(c);
  return DOT_TEX;
}

// graticule ring lines
function graticulePoints(): THREE.Vector3[][] {
  const lines: THREE.Vector3[][] = [];
  for (let lat = -60; lat <= 60; lat += 30) {
    const ring: THREE.Vector3[] = [];
    for (let lon = -180; lon <= 180; lon += 6) ring.push(ll2v3(lon, lat, R + 0.002));
    lines.push(ring);
  }
  for (let lon = -180; lon < 180; lon += 30) {
    const ring: THREE.Vector3[] = [];
    for (let lat = -90; lat <= 90; lat += 6) ring.push(ll2v3(lon, lat, R + 0.002));
    lines.push(ring);
  }
  return lines;
}

// ── atmosphere fresnel shader ───────────────────────────────────
function atmosphereMaterial(color: string, intensity: number): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms: {
      uColor: { value: new THREE.Color(color) },
      uIntensity: { value: intensity },
    },
    vertexShader: `
      varying vec3 vNormal;
      varying vec3 vView;
      void main() {
        vNormal = normalize(normalMatrix * normal);
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        vView = normalize(-mv.xyz);
        gl_Position = projectionMatrix * mv;
      }
    `,
    fragmentShader: `
      uniform vec3 uColor;
      uniform float uIntensity;
      varying vec3 vNormal;
      varying vec3 vView;
      void main() {
        float f = pow(1.0 - abs(dot(vNormal, vView)), 3.0);
        gl_FragColor = vec4(uColor, f * uIntensity);
      }
    `,
    transparent: true,
    blending: THREE.AdditiveBlending,
    side: THREE.BackSide,
    depthWrite: false,
  });
}

// ════════════════════════════════════════════════════════════════
//  Scene subcomponents
// ════════════════════════════════════════════════════════════════

function GlobeBody({ theme, occluderRef, onBg }: {
  theme: RouteTheme;
  occluderRef: React.RefObject<THREE.Mesh | null>;
  onBg: () => void;
}) {
  const t = THEME[theme];
  const dots = useMemo(() => landDots(), []);
  const tex = useMemo(() => dotTexture(), []);
  const grat = useMemo(() => graticulePoints(), []);
  const atmMat = useMemo(() => atmosphereMaterial(t.atmosphere, theme === "dark" ? 1.1 : 0.7), [t.atmosphere, theme]);

  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(dots, 3));
    return g;
  }, [dots]);

  return (
    <group>
      {/* ocean body — the raycast occluder (blocks far-side picks) */}
      <mesh ref={occluderRef} onClick={(e) => { e.stopPropagation(); onBg(); }}>
        <sphereGeometry args={[R - 0.003, 64, 64]} />
        <meshStandardMaterial
          color={t.ocean}
          emissive={t.oceanEmissive}
          emissiveIntensity={theme === "dark" ? 0.35 : 0.12}
          roughness={0.9}
          metalness={0.1}
        />
      </mesh>

      {/* graticule */}
      {grat.map((ring, i) => (
        <Line key={i} points={ring} color={t.graticule} lineWidth={0.6} transparent opacity={0.5} raycast={() => null} />
      ))}

      {/* land dots */}
      <points geometry={geo} raycast={() => null}>
        <pointsMaterial
          map={tex}
          color={t.land}
          size={0.02}
          sizeAttenuation
          transparent
          alphaTest={0.4}
          depthWrite={false}
        />
      </points>

      {/* atmosphere */}
      <mesh raycast={() => null} scale={1.16}>
        <sphereGeometry args={[R, 48, 48]} />
        <primitive object={atmMat} attach="material" />
      </mesh>
    </group>
  );
}

/** Latent (dim) edges as thin great-circle lines. */
function LatentEdges({ topology, brokenSet, activePairs, theme }: {
  topology: Topology;
  brokenSet: Set<string>;
  activePairs: Set<string>;
  theme: RouteTheme;
}) {
  const t = THEME[theme];
  const nodeById = useMemo(() => new Map(topology.nodes.map((n) => [n.id, n])), [topology.nodes]);
  const segments = useMemo(() => {
    const out: { key: string; pts: THREE.Vector3[] }[] = [];
    topology.edges.forEach((e) => {
      const a = nodeById.get(e.a), b = nodeById.get(e.b);
      if (!a || !b) return;
      const key = `${e.a}|${e.b}`, rev = `${e.b}|${e.a}`;
      if (brokenSet.has(key) || brokenSet.has(rev) || activePairs.has(key) || activePairs.has(rev)) return;
      out.push({ key, pts: greatCircle(a.coords, b.coords, 28, 0.18) });
    });
    return out;
  }, [topology.edges, nodeById, brokenSet, activePairs]);

  return (
    <group>
      {segments.map((s) => (
        <Line key={s.key} points={s.pts} color={t.latent} lineWidth={0.8}
          transparent opacity={t.latentOpacity} raycast={() => null} />
      ))}
    </group>
  );
}

/** A tube arc that carries a travelling pulse; hover/click aware. */
function PulseArc({
  points, color, radius, glow, dashed, onHover, onClick, cursor,
}: {
  points: THREE.Vector3[];
  color: string;
  radius: number;
  glow: boolean;
  dashed?: boolean;
  onHover?: (h: boolean) => void;
  onClick?: (e: ThreeEvent<MouseEvent>) => void;
  cursor?: boolean;
}) {
  const curve = useMemo(() => new THREE.CatmullRomCurve3(points), [points]);
  const tubeGeo = useMemo(() => new THREE.TubeGeometry(curve, Math.max(24, points.length), radius, 8, false), [curve, radius, points.length]);
  const glowGeo = useMemo(() => new THREE.TubeGeometry(curve, Math.max(24, points.length), radius * 3.2, 8, false), [curve, radius, points.length]);
  const pulseRef = useRef<THREE.Mesh>(null);
  const matRef = useRef<THREE.MeshBasicMaterial>(null);

  useFrame(({ clock }) => {
    const tt = (clock.getElapsedTime() * (dashed ? 0.35 : 0.28)) % 1;
    if (pulseRef.current) {
      const p = curve.getPointAt(tt);
      pulseRef.current.position.copy(p);
    }
    if (dashed && matRef.current) {
      matRef.current.opacity = 0.55 + 0.35 * Math.sin(clock.getElapsedTime() * 4);
    }
  });

  return (
    <group>
      {glow && (
        <mesh geometry={glowGeo} raycast={() => null}>
          <meshBasicMaterial color={color} transparent opacity={0.14} depthWrite={false} />
        </mesh>
      )}
      <mesh
        geometry={tubeGeo}
        onPointerOver={onHover ? (e) => { e.stopPropagation(); onHover(true); } : undefined}
        onPointerOut={onHover ? () => onHover(false) : undefined}
        onClick={onClick}
      >
        <meshBasicMaterial ref={matRef} color={color} transparent opacity={dashed ? 0.85 : 0.95} />
      </mesh>
      {/* travelling head */}
      <mesh ref={pulseRef} raycast={() => null}>
        <sphereGeometry args={[radius * 2.6, 12, 12]} />
        <meshBasicMaterial color={dashed ? color : "#ffffff"} transparent opacity={0.95} />
      </mesh>
      {cursor && <CursorHint />}
    </group>
  );
}

function CursorHint() {
  const { gl } = useThree();
  useEffect(() => {
    return () => { gl.domElement.style.cursor = "grab"; };
  }, [gl]);
  return null;
}

/** Node marker with hover/click + optional pulsing ring. */
function NodeMarker({
  node, st, theme, interactive, hovered, selected, onHover, onClick,
}: {
  node: GraphNode;
  st: NodeState;
  theme: RouteTheme;
  interactive: boolean;
  hovered: boolean;
  selected: boolean;
  onHover: (id: string | null) => void;
  onClick: (id: string) => void;
}) {
  const t = THEME[theme];
  const color = st === "red" ? t.red : st === "green" ? t.green : t.blue;
  const pos = useMemo(() => ll2v3(node.coords[0], node.coords[1], R + 0.006), [node.coords]);
  const ringRef = useRef<THREE.Mesh>(null);
  const coreRef = useRef<THREE.Mesh>(null);
  const isWaypoint = node.role === "waypoint";
  const baseSize = isWaypoint ? 0.008 : node.role === "refinery" ? 0.02 : node.role === "chokepoint" ? 0.017 : 0.018;

  // orient marker to face outward
  const quat = useMemo(() => {
    const q = new THREE.Quaternion();
    q.setFromUnitVectors(new THREE.Vector3(0, 0, 1), pos.clone().normalize());
    return q;
  }, [pos]);

  useFrame(({ clock }) => {
    const tm = clock.getElapsedTime();
    if (ringRef.current) {
      if (st === "red") {
        const s = 1 + 0.9 * ((Math.sin(tm * 3) + 1) / 2);
        ringRef.current.scale.setScalar(s);
        (ringRef.current.material as THREE.MeshBasicMaterial).opacity = 0.7 * (1 - ((Math.sin(tm * 3) + 1) / 2));
      } else if (st === "green") {
        (ringRef.current.material as THREE.MeshBasicMaterial).opacity = 0.3 + 0.25 * Math.sin(tm * 2.2);
      }
    }
    if (coreRef.current) {
      const target = hovered || selected ? 1.4 : 1;
      coreRef.current.scale.lerp(new THREE.Vector3(target, target, target), 0.2);
    }
  });

  const size = baseSize;

  return (
    <group position={pos} quaternion={quat}>
      {/* pulse / idle ring */}
      {(st === "red" || st === "green") && (
        <mesh ref={ringRef} raycast={() => null}>
          <ringGeometry args={[size * 1.3, size * 1.7, 32]} />
          <meshBasicMaterial color={color} transparent opacity={0.5} side={THREE.DoubleSide} depthWrite={false} />
        </mesh>
      )}
      {/* hover/select ring */}
      {(hovered || selected) && (
        <mesh raycast={() => null}>
          <ringGeometry args={[size * 1.8, size * 2.1, 32]} />
          <meshBasicMaterial color={theme === "dark" ? "#ffffff" : "#0c1815"} transparent opacity={0.8} side={THREE.DoubleSide} depthWrite={false} />
        </mesh>
      )}
      {/* core mark */}
      <mesh
        ref={coreRef}
        onPointerOver={(e) => { e.stopPropagation(); onHover(node.id); }}
        onPointerOut={() => onHover(null)}
        onClick={(e) => { if (!interactive) return; e.stopPropagation(); onClick(node.id); }}
      >
        {node.role === "refinery" ? (
          <boxGeometry args={[size * 1.7, size * 1.7, size * 0.6]} />
        ) : (
          <sphereGeometry args={[size, 16, 16]} />
        )}
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={st === "blue" ? 0.4 : 1.2}
          roughness={0.35}
          toneMapped={false}
        />
      </mesh>
    </group>
  );
}

/** Auto-rotate that pauses while the user interacts. */
function useIdleAutoRotate(controlsRef: React.RefObject<any>) { // eslint-disable-line @typescript-eslint/no-explicit-any
  const spinning = useRef(true);
  const resumeAt = useRef(0);
  useFrame(({ clock }) => {
    const ctrl = controlsRef.current;
    if (!ctrl) return;
    if (!spinning.current && clock.getElapsedTime() > resumeAt.current) spinning.current = true;
    ctrl.autoRotate = spinning.current;
  });
  const pause = useCallback((clockNow: number) => {
    spinning.current = false;
    resumeAt.current = clockNow + 4;
  }, []);
  return pause;
}

function Scene({
  topology, state, mode, theme, hoveredId, selectedId,
  onHoverNode, onClickNode, onBackgroundClick, controlsRef,
}: Props & { controlsRef: React.RefObject<any> }) { // eslint-disable-line @typescript-eslint/no-explicit-any
  const t = THEME[theme];
  const occluderRef = useRef<THREE.Mesh>(null);
  const { clock } = useThree();
  const pauseSpin = useIdleAutoRotate(controlsRef);

  const nodeById = useMemo(() => new Map(topology.nodes.map((n) => [n.id, n])), [topology.nodes]);
  const nodeState = useCallback((id: string): NodeState => state.node_states[id] ?? "blue", [state.node_states]);

  const brokenSet = useMemo(() => new Set(state.broken_edges.flatMap((e) => [`${e.a}|${e.b}`, `${e.b}|${e.a}`])), [state.broken_edges]);
  const activePairs = useMemo(() => {
    const s = new Set<string>();
    for (let i = 0; i < state.active_path.length - 1; i++) {
      s.add(`${state.active_path[i]}|${state.active_path[i + 1]}`);
      s.add(`${state.active_path[i + 1]}|${state.active_path[i]}`);
    }
    return s;
  }, [state.active_path]);

  const focusOf = (a: string, b: string) => (nodeState(a) === "red" ? a : nodeState(b) === "red" ? b : a);

  // active corridor points
  const corridorPts = useMemo(() => {
    const out: THREE.Vector3[] = [];
    for (let i = 0; i < state.active_path.length - 1; i++) {
      const a = nodeById.get(state.active_path[i]);
      const b = nodeById.get(state.active_path[i + 1]);
      if (!a || !b) continue;
      const seg = greatCircle(a.coords, b.coords, 44, 0.32);
      out.push(...(out.length ? seg.slice(1) : seg));
    }
    return out;
  }, [state.active_path, nodeById]);

  // broken arcs
  const brokenArcs = useMemo(() => {
    return state.broken_edges.map((e) => {
      const a = nodeById.get(e.a), b = nodeById.get(e.b);
      if (!a || !b) return null;
      return { key: `${e.a}-${e.b}`, focus: focusOf(e.a, e.b), pts: greatCircle(a.coords, b.coords, 40, 0.3) };
    }).filter(Boolean) as { key: string; focus: string; pts: THREE.Vector3[] }[];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.broken_edges, nodeById]);

  const setPointer = useCallback((h: boolean) => {
    document.body.style.cursor = h ? "pointer" : "";
  }, []);

  // labels: only for meaningful nodes to avoid clutter
  const labelIds = useMemo(() => {
    const s = new Set<string>();
    Object.entries(state.node_states).forEach(([id, st]) => { if (st !== "blue") s.add(id); });
    if (state.active_path.length) {
      s.add(state.active_path[0]);
      s.add(state.active_path[state.active_path.length - 1]);
    }
    return s;
  }, [state.node_states, state.active_path]);

  const deep = selectedId ? state.deep_dive[selectedId] : undefined;
  const selNode = selectedId ? nodeById.get(selectedId) : null;
  const hovNode = hoveredId ? nodeById.get(hoveredId) : null;
  const hovSpark = hoveredId ? state.sparks[hoveredId] : undefined;

  // drei's occlude wants non-null refs; cast our nullable mesh ref
  const occ = occluderRef.current
    ? ([occluderRef] as unknown as React.RefObject<THREE.Object3D>[])
    : undefined;

  return (
    <group>
      <ambientLight intensity={theme === "dark" ? 0.55 : 0.85} />
      <directionalLight position={[3, 2, 4]} intensity={theme === "dark" ? 1.5 : 1.1} />
      <pointLight position={[-4, -1, -3]} intensity={theme === "dark" ? 0.5 : 0.2} color={t.atmosphere} />

      <GlobeBody theme={theme} occluderRef={occluderRef} onBg={onBackgroundClick} />

      <LatentEdges topology={topology} brokenSet={brokenSet} activePairs={activePairs} theme={theme} />

      {/* active corridor */}
      {corridorPts.length >= 2 && (
        <PulseArc points={corridorPts} color={t.green} radius={0.006} glow />
      )}

      {/* broken arcs — hover/click to lock deep-dive */}
      {brokenArcs.map((arc) => (
        <PulseArc key={arc.key} points={arc.pts} color={t.red} radius={0.005} glow dashed cursor
          onHover={(h) => { setPointer(h); onHoverNode(h ? arc.focus : null); }}
          onClick={(e) => { e.stopPropagation(); onClickNode(arc.focus); }} />
      ))}

      {/* nodes */}
      {topology.nodes.map((n) => {
        const st = nodeState(n.id);
        const interactive = mode === "sandbox" || st === "red";
        return (
          <NodeMarker key={n.id} node={n} st={st} theme={theme}
            interactive={interactive}
            hovered={hoveredId === n.id} selected={selectedId === n.id}
            onHover={(id) => { setPointer(!!id && interactive); onHoverNode(id); }}
            onClick={onClickNode} />
        );
      })}

      {/* persistent labels */}
      {topology.nodes.filter((n) => labelIds.has(n.id)).map((n) => {
        const st = nodeState(n.id);
        const color = st === "red" ? t.red : st === "green" ? t.green : t.blue;
        return (
          <Html key={`lbl-${n.id}`} position={ll2v3(n.coords[0], n.coords[1], R + 0.02)}
            center distanceFactor={2.2} occlude={occ}
            style={{ pointerEvents: "none", transform: "translateY(-140%)" }}>
            <div className="whitespace-nowrap rounded px-1 py-0.5 text-[10px] font-semibold"
              style={{ color, textShadow: theme === "dark" ? "0 0 4px rgba(4,16,13,0.95),0 1px 2px rgba(4,16,13,0.95)" : "0 0 4px rgba(255,255,255,0.95)" }}>
              {n.name}
            </div>
          </Html>
        );
      })}

      {/* hover tooltip */}
      {hovNode && hoveredId !== selectedId && (
        <Html position={ll2v3(hovNode.coords[0], hovNode.coords[1], R + 0.03)}
          center distanceFactor={2.4} occlude={occ}
          style={{ pointerEvents: "none" }} zIndexRange={[60, 50]}>
          <div className="-translate-y-1/2 rounded-lg border border-[var(--ra-border)] bg-[var(--ra-surface-solid)] px-2.5 py-1.5 shadow-xl" style={{ transform: "translate(-50%,-135%)" }}>
            <div className="flex items-baseline gap-1.5">
              <span className="text-[12.5px] font-semibold text-[var(--ra-text)]">{hovNode.name}</span>
              <span className="font-mono text-[8.5px] uppercase tracking-wider text-[var(--ra-faint)]">{hovNode.role}</span>
            </div>
            {hovSpark
              ? <div className="mt-0.5 max-w-[220px] text-[11px] leading-snug text-[var(--ra-bad)]">⚡ {hovSpark}</div>
              : <div className="mt-0.5 font-mono text-[9.5px] text-[var(--ra-faint)]">{hovNode.country || hovNode.region}</div>}
            {mode === "sandbox" && (
              <div className="mt-0.5 font-mono text-[9px] text-[var(--ra-warn)]">
                click to {nodeState(hoveredId!) === "red" ? "restore" : "disrupt"}
              </div>
            )}
            {hovSpark && <div className="mt-0.5 font-mono text-[8.5px] uppercase tracking-wide text-[var(--ra-faint)]">click to lock deep-dive</div>}
          </div>
        </Html>
      )}

      {/* deep-dive lock */}
      {deep && selNode && (
        <Html position={ll2v3(selNode.coords[0], selNode.coords[1], R + 0.03)}
          center distanceFactor={2.4} zIndexRange={[80, 70]}
          style={{ pointerEvents: "auto" }}>
          <div className="ra-scroll max-h-[46vh] w-[280px] -translate-x-1/2 -translate-y-full overflow-y-auto overscroll-contain rounded-xl border border-[var(--ra-bad-border)] bg-[var(--ra-surface-solid)] shadow-2xl"
            style={{ transform: "translate(-50%,calc(-100% - 14px))" }}
            onClick={(e) => e.stopPropagation()} onPointerDown={(e) => e.stopPropagation()} onWheel={(e) => e.stopPropagation()}>
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
          </div>
        </Html>
      )}

      <OrbitControls
        ref={controlsRef}
        enablePan={false}
        enableDamping
        dampingFactor={0.08}
        rotateSpeed={0.5}
        minDistance={1.5}
        maxDistance={4.5}
        autoRotate
        autoRotateSpeed={0.35}
        onStart={() => pauseSpin(clock.getElapsedTime())}
      />
    </group>
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

// ════════════════════════════════════════════════════════════════
//  Public component
// ════════════════════════════════════════════════════════════════
function RouteGlobeImpl(props: Props) {
  const { theme, panelOpen, onBackgroundClick } = props;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const controlsRef = useRef<any>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    setReady(true);
    // r3f's initial ResizeObserver can miss the first layout in this host —
    // nudge it a few times after mount so the canvas fills its container.
    const timers = [60, 200, 450, 900, 1600].map((ms) =>
      setTimeout(() => window.dispatchEvent(new Event("resize")), ms)
    );
    return () => timers.forEach(clearTimeout);
  }, []);

  const dolly = useCallback((factor: number) => {
    const ctrl = controlsRef.current;
    if (!ctrl) return;
    const cam = ctrl.object as THREE.PerspectiveCamera;
    const tgt = ctrl.target as THREE.Vector3;
    const dir = cam.position.clone().sub(tgt);
    const len = THREE.MathUtils.clamp(dir.length() * factor, ctrl.minDistance, ctrl.maxDistance);
    dir.setLength(len);
    cam.position.copy(tgt).add(dir);
    ctrl.update();
  }, []);

  const recenter = useCallback(() => {
    const ctrl = controlsRef.current;
    if (!ctrl) return;
    ctrl.target.set(0, 0, 0);
    (ctrl.object as THREE.PerspectiveCamera).position.set(0.4, 0.5, 2.6);
    ctrl.update();
  }, []);

  return (
    <div className="absolute inset-0" style={{ background: THEME[theme].bg }}>
      <Canvas
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%", display: "block" }}
        camera={{ position: [0.4, 0.5, 2.6], fov: 42, near: 0.01, far: 100 }}
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: false }}
        resize={{ scroll: false, debounce: { scroll: 0, resize: 0 } }}
        onPointerMissed={() => onBackgroundClick()}
        onCreated={({ scene }) => { scene.background = new THREE.Color(THEME[theme].bg); }}
      >
        {ready && <Scene {...props} controlsRef={controlsRef} />}
      </Canvas>

      {/* zoom / recenter cluster */}
      <div className={`absolute bottom-6 z-20 flex flex-col overflow-hidden rounded-xl border border-[var(--ra-border)] bg-[var(--ra-surface)] shadow-lg backdrop-blur-md transition-[right] duration-300 ${panelOpen ? "right-[396px] max-md:right-4" : "right-4"}`}>
        <GlobeBtn label="Zoom in" onClick={() => dolly(1 / 1.3)}><path d="M8 3.5v9M3.5 8h9" /></GlobeBtn>
        <div className="h-px bg-[var(--ra-border)]" />
        <GlobeBtn label="Zoom out" onClick={() => dolly(1.3)}><path d="M3.5 8h9" /></GlobeBtn>
        <div className="h-px bg-[var(--ra-border)]" />
        <GlobeBtn label="Recenter" onClick={recenter}>
          <circle cx="8" cy="8" r="2.2" />
          <path d="M8 1.8v2.4M8 11.8v2.4M1.8 8h2.4M11.8 8h2.4" />
        </GlobeBtn>
      </div>

      {/* drag hint */}
      <div className="pointer-events-none absolute bottom-6 left-4 z-20 rounded-md border border-[var(--ra-border)] bg-[var(--ra-surface)] px-2 py-0.5 font-mono text-[10px] text-[var(--ra-faint)] backdrop-blur">
        drag to rotate · scroll to zoom
      </div>
    </div>
  );
}

function GlobeBtn({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={(e) => { e.stopPropagation(); onClick(); }} aria-label={label} title={label}
      className="grid size-10 place-items-center text-[var(--ra-dim)] transition-colors hover:bg-[var(--ra-hover)] hover:text-[var(--ra-text)]">
      <svg viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">{children}</svg>
    </button>
  );
}

export default memo(RouteGlobeImpl);
