"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { AnimatePresence, motion } from "motion/react";
import ImpactFloater from "@/components/route/ImpactFloater";
import type { RouteTheme } from "@/components/route/RouteMap";
import {
  DisruptStatus,
  RouteState,
  Topology,
  emptyRouteState,
  fetchLive,
  fetchTopology,
  simulate,
} from "@/lib/routeApi";

const RouteGlobe = dynamic(() => import("@/components/route/RouteMap"), {
  ssr: false,
  loading: () => (
    <div className="absolute inset-0 grid place-items-center">
      <span className="animate-pulse font-mono text-xs tracking-[0.3em] text-[var(--ra-faint)]">
        INITIALISING GLOBE ENGINE…
      </span>
    </div>
  ),
});

type Mode = "live" | "sandbox";
const LIVE_POLL_MS = 20_000;
const THEME_KEY = "ra-theme";

export default function RouteAgentPage() {
  const [topology, setTopology] = useState<Topology | null>(null);
  const [state, setState] = useState<RouteState | null>(null);
  const [mode, setMode] = useState<Mode>("live");
  const [theme, setTheme] = useState<RouteTheme>("dark");
  const [panelOpen, setPanelOpen] = useState(true);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<string>("");

  // sandbox disruption set (node id → status), independent of live feed
  const sandbox = useRef<Map<string, DisruptStatus>>(new Map());

  // ── theme bootstrap + persistence ──────────────────────────────
  useEffect(() => {
    const saved = window.localStorage.getItem(THEME_KEY);
    if (saved === "light" || saved === "dark") setTheme(saved);
  }, []);
  const toggleTheme = useCallback(() => {
    setTheme((t) => {
      const next = t === "dark" ? "light" : "dark";
      window.localStorage.setItem(THEME_KEY, next);
      return next;
    });
  }, []);

  // ── bootstrap topology ─────────────────────────────────────────
  useEffect(() => {
    let alive = true;
    fetchTopology()
      .then((t) => {
        if (!alive) return;
        setTopology(t);
        setState(emptyRouteState(t.baseline_path));
      })
      .catch((e) => alive && setError(String(e.message ?? e)));
    return () => {
      alive = false;
    };
  }, []);

  // ── live polling loop ──────────────────────────────────────────
  useEffect(() => {
    if (mode !== "live" || !topology) return;
    let alive = true;
    const tick = async () => {
      try {
        const s = await fetchLive(24);
        if (!alive) return;
        setState(s);
        setUpdatedAt(new Date().toLocaleTimeString());
        setError(null);
      } catch (e) {
        if (alive) setError(String((e as Error).message ?? e));
      }
    };
    tick();
    const id = setInterval(tick, LIVE_POLL_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [mode, topology]);

  const runSandbox = useCallback(async () => {
    setBusy(true);
    try {
      const disrupted = Array.from(sandbox.current.entries()).map(
        ([node_id, status]) => ({ node_id, status })
      );
      const s = await simulate(disrupted);
      setState(s);
      setUpdatedAt(new Date().toLocaleTimeString());
      setError(null);
    } catch (e) {
      setError(String((e as Error).message ?? e));
    } finally {
      setBusy(false);
    }
  }, []);

  // ── mode switch ────────────────────────────────────────────────
  const switchMode = useCallback(
    async (next: Mode) => {
      setSelectedId(null);
      setError(null);
      if (next === "sandbox") {
        // Clone the current live disruptions into the isolated sandbox.
        const seed = new Map<string, DisruptStatus>();
        state?.disrupted.forEach((d) => seed.set(d.node_id, d.status));
        sandbox.current = seed;
        setMode("sandbox");
        await runSandbox();
      } else {
        setMode("live");
      }
    },
    [state, runSandbox]
  );

  // ── node interaction ───────────────────────────────────────────
  const onClickNode = useCallback(
    (id: string) => {
      if (mode === "sandbox") {
        // toggle disruption on this node
        if (sandbox.current.has(id)) sandbox.current.delete(id);
        else sandbox.current.set(id, "blocked");
        setSelectedId(sandbox.current.has(id) ? id : null);
        runSandbox();
      } else {
        // live: only red nodes are interactive → lock the deep-dive
        setSelectedId(id);
      }
    },
    [mode, runSandbox]
  );

  const resetSandbox = useCallback(() => {
    sandbox.current.clear();
    setSelectedId(null);
    runSandbox();
  }, [runSandbox]);

  if (!topology || !state) {
    return (
      <main
        data-ra-theme={theme}
        className="grid min-h-dvh place-items-center bg-[var(--ra-bg)] text-[var(--ra-dim)]"
      >
        {error ? (
          <div className="max-w-md px-6 text-center">
            <p className="font-medium text-[var(--ra-bad)]">
              Route Agent backend unavailable.
            </p>
            <p className="mt-2 text-sm text-[var(--ra-faint)]">{error}</p>
            <p className="mt-3 font-mono text-xs text-[var(--ra-faint)]">
              Start it: <code>cd agents; .venv\Scripts\python route_agent/main.py</code>
            </p>
          </div>
        ) : (
          <div className="animate-pulse font-mono text-sm tracking-[0.3em]">
            INITIALISING NETWORK TOPOLOGY…
          </div>
        )}
      </main>
    );
  }

  return (
    <main
      data-ra-theme={theme}
      className="flex h-dvh flex-col overflow-hidden bg-[var(--ra-bg)] text-[var(--ra-text)]"
    >
      {/* ── header ── */}
      <header className="z-20 flex shrink-0 items-center justify-between gap-3 border-b border-[var(--ra-border)] bg-[var(--ra-surface)] px-4 py-2.5 backdrop-blur-md sm:px-5">
        <div className="flex min-w-0 items-center gap-3">
          <Link
            href="/"
            className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-[var(--ra-border)] text-[var(--ra-dim)] transition-colors hover:bg-[var(--ra-hover)] hover:text-[var(--ra-text)]"
            aria-label="Back to command center"
          >
            <svg viewBox="0 0 16 16" className="size-3.5" fill="none">
              <path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </Link>
          <div className="min-w-0">
            <h1 className="truncate text-[15px] font-semibold tracking-tight">
              Route Agent
            </h1>
            <p className="hidden truncate font-mono text-[9.5px] uppercase tracking-[0.2em] text-[var(--ra-faint)] sm:block">
              Spatial Intelligence · Network Topology Engine
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          {updatedAt && (
            <span className="hidden font-mono text-[10px] text-[var(--ra-faint)] lg:block">
              {mode === "live" ? "live · " : "sandbox · "}updated {updatedAt}
            </span>
          )}

          {/* mode toggle */}
          <div className="flex rounded-full border border-[var(--ra-border)] bg-[var(--ra-hover)] p-0.5">
            {(["live", "sandbox"] as Mode[]).map((m) => (
              <button
                key={m}
                onClick={() => switchMode(m)}
                className={`relative rounded-full px-3 py-1 text-[11px] font-medium transition-colors sm:px-3.5 ${
                  mode === m
                    ? "text-[var(--ra-pill-text)]"
                    : "text-[var(--ra-dim)] hover:text-[var(--ra-text)]"
                }`}
              >
                {mode === m && (
                  <motion.span
                    layoutId="mode-pill"
                    className="absolute inset-0 rounded-full"
                    style={{ background: m === "live" ? "var(--ra-good)" : "var(--ra-warn)" }}
                    transition={{ type: "spring", stiffness: 400, damping: 32 }}
                  />
                )}
                <span className="relative">
                  {m === "live" ? "Live Simulation" : "Sandbox"}
                </span>
              </button>
            ))}
          </div>

          {/* theme toggle */}
          <button
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
            title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
            className="grid size-8 place-items-center rounded-lg border border-[var(--ra-border)] text-[var(--ra-dim)] transition-colors hover:bg-[var(--ra-hover)] hover:text-[var(--ra-text)]"
          >
            {theme === "dark" ? (
              <svg viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round">
                <circle cx="8" cy="8" r="3.2" />
                <path d="M8 1.5v1.6M8 12.9v1.6M1.5 8h1.6M12.9 8h1.6M3.4 3.4l1.1 1.1M11.5 11.5l1.1 1.1M12.6 3.4l-1.1 1.1M4.5 11.5l-1.1 1.1" />
              </svg>
            ) : (
              <svg viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round">
                <path d="M13.5 9.5A5.5 5.5 0 0 1 6.5 2.5a5.5 5.5 0 1 0 7 7z" />
              </svg>
            )}
          </button>

          {/* panel toggle */}
          <button
            onClick={() => setPanelOpen((v) => !v)}
            aria-label={panelOpen ? "Hide intelligence panel" : "Show intelligence panel"}
            title={panelOpen ? "Hide intelligence panel" : "Show intelligence panel"}
            className={`grid size-8 place-items-center rounded-lg border transition-colors ${
              panelOpen
                ? "border-[var(--ra-good)]/40 bg-[var(--ra-good-wash)] text-[var(--ra-good)]"
                : "border-[var(--ra-border)] text-[var(--ra-dim)] hover:bg-[var(--ra-hover)] hover:text-[var(--ra-text)]"
            }`}
          >
            <svg viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round">
              <rect x="1.8" y="2.5" width="12.4" height="11" rx="1.5" />
              <path d="M10 2.5v11" />
            </svg>
          </button>
        </div>
      </header>

      {/* ── map stage ── */}
      <div className="relative flex-1 overflow-hidden">
        <RouteGlobe
          topology={topology}
          state={state}
          mode={mode}
          theme={theme}
          panelOpen={panelOpen}
          hoveredId={hoveredId}
          selectedId={selectedId}
          onHoverNode={setHoveredId}
          onClickNode={onClickNode}
          onBackgroundClick={() => setSelectedId(null)}
        />

        {/* legend */}
        <div className="pointer-events-none absolute bottom-6 left-4 z-10 flex flex-col gap-1.5 rounded-xl border border-[var(--ra-border)] bg-[var(--ra-surface)] px-3 py-2.5 shadow-lg backdrop-blur-md">
          {[
            ["var(--ra-blue)", "Latent option"],
            ["var(--ra-good)", "Active corridor"],
            ["var(--ra-bad)", "Disrupted"],
          ].map(([c, label]) => (
            <div key={label} className="flex items-center gap-2">
              <span className="size-2 rounded-full" style={{ background: c }} />
              <span className="text-[10.5px] text-[var(--ra-dim)]">{label}</span>
            </div>
          ))}
        </div>

        {/* sandbox hint / reset */}
        {mode === "sandbox" && (
          <div className="absolute left-1/2 top-3 z-10 flex -translate-x-1/2 items-center gap-2">
            <span className="rounded-full border border-[var(--ra-warn)]/30 bg-[var(--ra-warn-wash)] px-3 py-1 font-mono text-[10px] text-[var(--ra-warn)] shadow backdrop-blur">
              {busy ? "computing…" : "click any node to war-game a failure"}
            </span>
            {sandbox.current.size > 0 && (
              <button
                onClick={resetSandbox}
                className="rounded-full border border-[var(--ra-border)] bg-[var(--ra-surface)] px-3 py-1 text-[10.5px] text-[var(--ra-dim)] shadow backdrop-blur transition-colors hover:text-[var(--ra-text)]"
              >
                Reset
              </button>
            )}
          </div>
        )}

        {error && mode === "live" && (
          <div className="absolute left-1/2 top-3 z-20 -translate-x-1/2 rounded-full border border-[var(--ra-bad)]/30 bg-[var(--ra-bad-wash)] px-3 py-1 font-mono text-[10px] text-[var(--ra-bad)] shadow backdrop-blur">
            {error}
          </div>
        )}

        {/* ── intelligence side panel (scrollable) ── */}
        <AnimatePresence initial={false}>
          {panelOpen && (
            <motion.aside
              key="panel"
              initial={{ x: 400, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: 400, opacity: 0 }}
              transition={{ type: "spring", stiffness: 320, damping: 34 }}
              className="absolute bottom-3 right-3 top-3 z-10 flex w-[372px] max-w-[calc(100vw-24px)] flex-col overflow-hidden rounded-2xl border border-[var(--ra-border)] bg-[var(--ra-surface)] shadow-2xl backdrop-blur-xl"
            >
              <div className="ra-scroll min-h-0 flex-1 overflow-y-auto overscroll-contain">
                <ImpactFloater state={state} />
              </div>
            </motion.aside>
          )}
        </AnimatePresence>
      </div>
    </main>
  );
}
