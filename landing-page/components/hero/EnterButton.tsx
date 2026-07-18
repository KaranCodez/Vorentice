"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { motion, useSpring, AnimatePresence } from "motion/react";

type AgentDef = {
  id: string;
  label: string;
  sub: string;
  href: string;
  active: boolean;
  color: string;
  Icon: (p: { className?: string }) => React.ReactElement;
};

const AGENTS: AgentDef[] = [
  {
    id: "news",
    label: "News Agent",
    sub: "Live global intelligence feed",
    href: "/dashboard",
    active: true,
    color: "#2dd4bf",
    Icon: NewsIcon,
  },
  {
    id: "risk",
    label: "Risk Agent",
    sub: "India-centric supply-chain risk",
    href: "/risk-agent",
    active: true,
    color: "#f97316",
    Icon: ShieldIcon,
  },
  {
    id: "route",
    label: "Route Agent",
    sub: "Optimal crude shipping routes",
    href: "#",
    active: false,
    color: "#818cf8",
    Icon: RouteIcon,
  },
];

/** Magnetic CTA — click reveals the agent selector inline. */
export default function EnterButton() {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const ref = useRef<HTMLDivElement>(null);
  const x = useSpring(0, { stiffness: 200, damping: 16 });
  const y = useSpring(0, { stiffness: 200, damping: 16 });

  // close on outside click / escape
  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function onMove(e: React.MouseEvent) {
    if (open) return;
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
    <div ref={wrapRef} className="relative flex flex-col items-center">
      <AnimatePresence>
        {open && (
          <motion.div
            key="agent-panel"
            initial={{ opacity: 0, y: 16, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.97 }}
            transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
            className="absolute bottom-[calc(100%+16px)] left-1/2 w-[330px] -translate-x-1/2"
          >
            <div className="overflow-hidden rounded-2xl border border-white/10 bg-[#0b1613]/95 shadow-[0_28px_70px_-14px_rgba(4,10,8,0.8)] backdrop-blur-xl">
              {/* header */}
              <div className="flex items-center justify-between border-b border-white/[0.07] px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="relative flex size-1.5">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent-bright opacity-70" />
                    <span className="relative inline-flex size-1.5 rounded-full bg-accent-bright" />
                  </span>
                  <span className="font-mono text-[9px] uppercase tracking-[0.22em] text-white/45">
                    Select Agent
                  </span>
                </div>
                <button
                  onClick={() => setOpen(false)}
                  className="flex size-5 items-center justify-center rounded text-white/30 transition-colors hover:bg-white/10 hover:text-white/70"
                  aria-label="Close"
                >
                  <svg viewBox="0 0 16 16" className="size-3" fill="none">
                    <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                  </svg>
                </button>
              </div>

              {/* agents */}
              <div className="flex flex-col p-1.5">
                {AGENTS.map((agent) =>
                  agent.active ? (
                    <Link
                      key={agent.id}
                      href={agent.href}
                      className="group relative flex items-center gap-3.5 rounded-xl px-3 py-3 transition-colors hover:bg-white/[0.05]"
                    >
                      <span
                        className="flex size-9 shrink-0 items-center justify-center rounded-lg transition-transform group-hover:scale-105"
                        style={{ background: `${agent.color}1e`, border: `1px solid ${agent.color}3a` }}
                      >
                        <agent.Icon className="size-4" />
                      </span>
                      <span className="flex min-w-0 flex-col">
                        <span className="text-[13px] font-semibold text-white/90 transition-colors group-hover:text-white">
                          {agent.label}
                        </span>
                        <span className="truncate font-mono text-[10px] tracking-wide text-white/40">
                          {agent.sub}
                        </span>
                      </span>
                      <span
                        className="ml-auto flex size-6 shrink-0 items-center justify-center rounded-full transition-all group-hover:translate-x-0.5"
                        style={{ color: agent.color }}
                      >
                        <svg viewBox="0 0 16 16" fill="none" className="size-3.5">
                          <path d="M2 8h10M8 4l4 4-4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </span>
                    </Link>
                  ) : (
                    <div
                      key={agent.id}
                      className="flex cursor-not-allowed items-center gap-3.5 rounded-xl px-3 py-3 opacity-45"
                    >
                      <span
                        className="flex size-9 shrink-0 items-center justify-center rounded-lg"
                        style={{ background: `${agent.color}14`, border: `1px solid ${agent.color}26` }}
                      >
                        <agent.Icon className="size-4" />
                      </span>
                      <span className="flex min-w-0 flex-col">
                        <span className="text-[13px] font-semibold text-white/70">{agent.label}</span>
                        <span className="truncate font-mono text-[10px] tracking-wide text-white/35">
                          {agent.sub}
                        </span>
                      </span>
                      <span className="ml-auto shrink-0 rounded-full border border-white/15 px-2 py-0.5 font-mono text-[8px] uppercase tracking-widest text-white/30">
                        Soon
                      </span>
                    </div>
                  )
                )}
              </div>
            </div>

            {/* caret */}
            <div className="absolute left-1/2 top-full -translate-x-1/2 -translate-y-1/2">
              <div className="size-3 rotate-45 border-b border-r border-white/10 bg-[#0b1613]" />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* button */}
      <motion.div
        ref={ref}
        onMouseMove={onMove}
        onMouseLeave={onLeave}
        style={open ? {} : { x, y }}
        whileTap={{ scale: 0.96 }}
      >
        <button
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="group relative flex items-center gap-3.5 overflow-hidden rounded-full bg-ink py-2 pl-7 pr-2 text-[15px] font-medium text-background shadow-[0_18px_40px_-16px_rgba(12,24,21,0.6)] transition-shadow duration-500 hover:shadow-[0_18px_50px_-12px_rgba(13,148,136,0.55)]"
        >
          <span className="pointer-events-none absolute inset-0 -translate-x-[130%] skew-x-[-20deg] bg-gradient-to-r from-transparent via-white/25 to-transparent transition-transform duration-1000 ease-out group-hover:translate-x-[130%]" />
          Enter Command Center
          <span className="relative flex size-10 items-center justify-center overflow-hidden rounded-full bg-white/15 transition-colors duration-300 group-hover:bg-accent">
            <GridIcon className={`absolute size-4 transition-all duration-300 ${open ? "rotate-45 opacity-0" : "group-hover:rotate-90"}`} />
            <GridIcon className={`absolute size-4 transition-all duration-300 ${open ? "rotate-0 opacity-100" : "-rotate-45 opacity-0"}`} />
          </span>
        </button>
      </motion.div>
    </div>
  );
}

/* ── icons ── */
function NewsIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className} style={{ color: "#2dd4bf" }} aria-hidden>
      <rect x="2" y="3" width="12" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.3" />
      <path d="M4.5 6h5M4.5 8.5h5M4.5 11h3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  );
}
function ShieldIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className} style={{ color: "#f97316" }} aria-hidden>
      <path d="M8 2L3 4v4c0 3 2.3 5.3 5 6 2.7-.7 5-3 5-6V4L8 2z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
      <path d="M5.6 8l1.7 1.7L10.4 6.2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function RouteIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className} style={{ color: "#818cf8" }} aria-hidden>
      <circle cx="4" cy="12" r="1.6" stroke="currentColor" strokeWidth="1.3" />
      <circle cx="12" cy="4" r="1.6" stroke="currentColor" strokeWidth="1.3" />
      <path d="M5.4 11C9 10 10.5 8 11 5.4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeDasharray="1 1.6" />
    </svg>
  );
}
function GridIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className} aria-hidden>
      <rect x="2" y="2" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.4" />
      <rect x="9" y="2" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.4" />
      <rect x="2" y="9" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.4" />
      <rect x="9" y="9" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}
