"use client";

import { useEffect, useRef } from "react";
import { CHOKEPOINTS, TRADE_ROUTES } from "@/lib/map-data";
import { LAND_PATH, MAP_W, project, smoothRoutePath } from "@/lib/geo";

/**
 * Paint-brush reveal over the hero title (benchmark: noth.in).
 * Moving the cursor across the letters "paints" a hidden layer inside the
 * glyphs: the dark command view with glowing tanker routes and chokepoints.
 *
 * Composition per frame (2D canvas, no WebGL):
 *   glyph stencil  ∩  decaying brush trail  ∩  animated route-map texture
 *
 * The stencil is drawn from the real DOM letter spans (offsetLeft/Top ignore
 * the entrance transform), so alignment survives any viewport size.
 */

const STATUS_DOT: Record<string, string> = {
  critical: "#f87171",
  elevated: "#fbbf24",
  stable: "#2dd4bf",
  failover: "#34d399",
};

const ROUTE_STROKE: Record<string, { color: string; width: number; dash?: [number, number] }> = {
  primary: { color: "#3ee6cf", width: 3.6 },
  standard: { color: "#1cc7b3", width: 2, dash: [10, 14] },
  failover: { color: "#34d399", width: 2.2, dash: [7, 9] },
};

// Static geometry, computed once at module load.
const ROUTES = TRADE_ROUTES.map((r) => ({
  d: smoothRoutePath(r.waypoints),
  kind: r.kind,
}));
const DOTS = CHOKEPOINTS.map((c) => ({
  xy: project(c.coords),
  color: STATUS_DOT[c.status],
  critical: c.status === "critical",
}));
// Slice of the world the texture centers on — the Gulf → India corridor.
const ANCHOR = project([58, 23]);

export default function TitlePaint({
  ready,
  host,
}: {
  ready: boolean;
  host: React.RefObject<HTMLDivElement | null>;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!ready) return;
    const wrap = host.current;
    const canvas = canvasRef.current;
    if (!wrap || !canvas) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const stencil = document.createElement("canvas");
    const trail = document.createElement("canvas");
    const tex = document.createElement("canvas");
    const sctx = stencil.getContext("2d")!;
    const tctx = trail.getContext("2d")!;
    const xctx = tex.getContext("2d")!;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let W = 0;
    let H = 0;

    const landPath = new Path2D(LAND_PATH);
    const routePaths = ROUTES.map((r) => ({ p: new Path2D(r.d), kind: r.kind }));

    const pointer = {
      x: -1e3,
      y: -1e3,
      px: -1e3,
      py: -1e3,
      last: 0,
      inside: false,
    };
    let energy = 0; // rough "how much paint is on screen"
    let sweep: { start: number; dur: number } | null = null;
    let lastSweepEnd = 0;
    let raf = 0;
    let disposed = false;
    const born = performance.now();

    function buildStencil() {
      sctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      sctx.clearRect(0, 0, W, H);
      sctx.fillStyle = "#fff";
      sctx.textBaseline = "alphabetic";
      const spans = wrap!.querySelectorAll<HTMLElement>("[data-paint-letter]");
      spans.forEach((el) => {
        const ch = el.dataset.paintLetter || "";
        const cs = getComputedStyle(el);
        sctx.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
        const m = sctx.measureText(ch);
        const fs = parseFloat(cs.fontSize);
        const asc = m.fontBoundingBoxAscent ?? fs * 0.78;
        const desc = m.fontBoundingBoxDescent ?? fs * 0.22;
        // center the font box inside the line box, then drop to baseline
        const y = el.offsetTop + (el.offsetHeight - (asc + desc)) / 2 + asc;
        sctx.fillText(ch, el.offsetLeft, y);
      });
    }

    function sizeAll() {
      const r = wrap!.getBoundingClientRect();
      W = Math.max(1, Math.round(r.width));
      H = Math.max(1, Math.round(r.height));
      for (const c of [canvas!, stencil, trail, tex]) {
        c.width = Math.round(W * dpr);
        c.height = Math.round(H * dpr);
      }
      canvas!.style.width = `${W}px`;
      canvas!.style.height = `${H}px`;
      buildStencil();
    }

    function fadeTrail() {
      tctx.setTransform(1, 0, 0, 1, 0, 0);
      tctx.globalCompositeOperation = "destination-out";
      tctx.fillStyle = "rgba(0,0,0,0.01)";
      tctx.fillRect(0, 0, trail.width, trail.height);
      tctx.globalCompositeOperation = "source-over";
    }

    function blob(x: number, y: number, r: number, a: number) {
      const g = tctx.createRadialGradient(x, y, 0, x, y, r);
      g.addColorStop(0, `rgba(255,255,255,${a})`);
      g.addColorStop(1, "rgba(255,255,255,0)");
      tctx.fillStyle = g;
      tctx.beginPath();
      tctx.arc(x, y, r, 0, Math.PI * 2);
      tctx.fill();
    }

    /** One organic brush dab at CSS-px coords. */
    function paintAt(cssX: number, cssY: number, size = 1) {
      const x = cssX * dpr;
      const y = cssY * dpr;
      const base = H * 0.4 * dpr * size;
      blob(x, y, base, 0.5);
      for (let i = 0; i < 3; i++) {
        blob(
          x + (Math.random() - 0.5) * base * 0.9,
          y + (Math.random() - 0.5) * base * 0.7,
          base * (0.35 + Math.random() * 0.3),
          0.3,
        );
      }
      energy = 1; // full paint on screen; decays in step with the trail fade
    }

    function drawTexture(now: number) {
      xctx.setTransform(1, 0, 0, 1, 0, 0);
      xctx.fillStyle = "#06201b";
      xctx.fillRect(0, 0, tex.width, tex.height);

      // drifting aurora glow, nudged toward the cursor
      const ax =
        tex.width * (0.5 + Math.sin(now * 0.00012) * 0.3) +
        (pointer.inside ? (pointer.x / W - 0.5) * tex.width * 0.25 : 0);
      const ay = tex.height * (0.45 + Math.cos(now * 0.00009) * 0.2);
      const aurora = xctx.createRadialGradient(ax, ay, 0, ax, ay, tex.width * 0.38);
      aurora.addColorStop(0, "rgba(45,212,191,0.28)");
      aurora.addColorStop(1, "rgba(45,212,191,0)");
      xctx.fillStyle = aurora;
      xctx.fillRect(0, 0, tex.width, tex.height);

      // Zoomed onto the Gulf → India corridor, drifting slowly, nudged by
      // the cursor for parallax.
      const scale = (tex.width / MAP_W) * 2.3;
      const drift = Math.sin(now * 0.00005) * 44 * dpr;
      const parallax = pointer.inside ? (pointer.x / W - 0.5) * 70 * dpr : 0;
      const ox = tex.width * 0.5 - ANCHOR[0] * scale + drift + parallax;
      const oy = tex.height * 0.55 - ANCHOR[1] * scale;
      xctx.setTransform(scale, 0, 0, scale, ox, oy);

      xctx.fillStyle = "rgba(82, 148, 131, 0.55)";
      xctx.fill(landPath);

      const t = (now - born) * 0.018;
      for (const r of routePaths) {
        const s = ROUTE_STROKE[r.kind];
        xctx.strokeStyle = s.color;
        xctx.lineWidth = (s.width * dpr) / scale;
        xctx.setLineDash(s.dash ?? []);
        xctx.lineDashOffset = -t;
        xctx.shadowColor = s.color;
        xctx.shadowBlur = 16;
        xctx.stroke(r.p);
      }
      xctx.setLineDash([]);
      xctx.shadowBlur = 18;
      DOTS.forEach((d, i) => {
        const base = d.critical ? 4 : 3;
        const r =
          ((base + Math.sin(now * 0.004 + i * 1.7) * 1.3) * dpr) / scale;
        xctx.fillStyle = d.color;
        xctx.shadowColor = d.color;
        xctx.beginPath();
        xctx.arc(d.xy[0], d.xy[1], Math.max(r, 0.6), 0, Math.PI * 2);
        xctx.fill();
        if (d.critical) {
          // expanding alarm ring around critical chokepoints
          const k = ((now * 0.0011 + i) % 1 + 1) % 1;
          xctx.strokeStyle = `rgba(248,113,113,${(1 - k) * 0.8})`;
          xctx.lineWidth = (1.4 * dpr) / scale;
          xctx.beginPath();
          xctx.arc(d.xy[0], d.xy[1], r * (1 + k * 2.6), 0, Math.PI * 2);
          xctx.stroke();
        }
      });
      xctx.shadowBlur = 0;

      // soft teal sheen across the top of the slice
      xctx.setTransform(1, 0, 0, 1, 0, 0);
      const sheen = xctx.createLinearGradient(0, 0, 0, tex.height);
      sheen.addColorStop(0, "rgba(45,212,191,0.18)");
      sheen.addColorStop(0.45, "rgba(45,212,191,0)");
      xctx.fillStyle = sheen;
      xctx.fillRect(0, 0, tex.width, tex.height);
    }

    function compose() {
      ctx!.setTransform(1, 0, 0, 1, 0, 0);
      ctx!.clearRect(0, 0, canvas!.width, canvas!.height);
      ctx!.globalCompositeOperation = "source-over";
      ctx!.drawImage(stencil, 0, 0);
      ctx!.globalCompositeOperation = "source-in";
      ctx!.drawImage(trail, 0, 0);
      ctx!.globalCompositeOperation = "source-in";
      ctx!.drawImage(tex, 0, 0);
      ctx!.globalCompositeOperation = "source-over";
    }

    /** Showcase sweep after the entrance, then a gentle keep-alive when idle. */
    function maybeSweep(now: number) {
      if (sweep) return;
      const firstShowcase = lastSweepEnd === 0 && now - born > 2000;
      const idleLoop =
        lastSweepEnd > 0 &&
        now - pointer.last > 8000 &&
        now - lastSweepEnd > 9000;
      if (firstShowcase || idleLoop) sweep = { start: now, dur: 2600 };
    }

    function runSweep(now: number) {
      if (!sweep) return;
      const k = (now - sweep.start) / sweep.dur;
      if (k >= 1) {
        lastSweepEnd = now;
        sweep = null;
        return;
      }
      const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      const x = (-0.08 + 1.16 * e) * W;
      const y = H * (0.5 + Math.sin(k * Math.PI * 2.2) * 0.16);
      paintAt(x, y, 1.15);
    }

    function frame(now: number) {
      if (disposed) return;
      raf = requestAnimationFrame(frame);
      maybeSweep(now);
      const active =
        sweep !== null || now - pointer.last < 3000 || energy > 0.03;
      if (!active) return; // everything faded — skip all work until next event

      fadeTrail();
      energy *= 0.99; // tracks the trail's own decay rate
      runSweep(now);

      if (pointer.inside && (pointer.x !== pointer.px || pointer.y !== pointer.py)) {
        const dx = pointer.x - pointer.px;
        const dy = pointer.y - pointer.py;
        const dist = Math.hypot(dx, dy);
        const steps = Math.max(1, Math.min(14, Math.floor(dist / (H * 0.16))));
        for (let i = 1; i <= steps; i++) {
          paintAt(pointer.px + (dx * i) / steps, pointer.py + (dy * i) / steps);
        }
        pointer.px = pointer.x;
        pointer.py = pointer.y;
      }

      drawTexture(now);
      compose();
    }

    function onPointerMove(e: PointerEvent) {
      const r = wrap!.getBoundingClientRect();
      const x = e.clientX - r.left;
      const y = e.clientY - r.top;
      if (pointer.px < -100) {
        pointer.px = x;
        pointer.py = y;
      }
      pointer.x = x;
      pointer.y = y;
      pointer.inside = true;
      pointer.last = performance.now();
    }

    function onPointerLeave() {
      pointer.inside = false;
      pointer.px = -1e3; // avoid a paint streak on re-entry
      pointer.py = -1e3;
    }

    sizeAll();
    document.fonts.ready.then(() => {
      if (!disposed) buildStencil();
    });
    const ro = new ResizeObserver(sizeAll);
    ro.observe(wrap);
    wrap.addEventListener("pointermove", onPointerMove);
    wrap.addEventListener("pointerleave", onPointerLeave);
    raf = requestAnimationFrame(frame);

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      ro.disconnect();
      wrap.removeEventListener("pointermove", onPointerMove);
      wrap.removeEventListener("pointerleave", onPointerLeave);
    };
  }, [ready, host]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className="pointer-events-none absolute inset-0"
    />
  );
}
