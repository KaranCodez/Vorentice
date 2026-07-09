"use client";

import { motion } from "motion/react";
import AnimatedNumber from "./AnimatedNumber";
import Sparkline from "./Sparkline";
import PortBars from "./PortBars";
import RiskRows from "./RiskRows";
import WeatherRow from "./WeatherRow";
import { EASE_OUT } from "@/lib/motion";

function Section({
  ready,
  order,
  className = "",
  children,
}: {
  ready: boolean;
  order: number;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={ready ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.7, delay: 1.45 + order * 0.12, ease: EASE_OUT }}
      className={`border-b border-line px-4 py-2 last:border-b-0 ${className}`}
    >
      {children}
    </motion.div>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-faint">
      {children}
    </p>
  );
}

/** Right-hand telemetry column — the "Global Operations" panel. */
export default function OpsPanel({ ready }: { ready: boolean }) {
  return (
    <aside className="relative z-10 flex flex-col border-t border-line bg-white/50 md:border-l md:border-t-0">
      <Section ready={ready} order={0} className="flex items-center justify-between">
        <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.2em] text-ink">
          Global operations
        </p>
        <span className="flex items-center gap-1.5 font-mono text-[8.5px] uppercase tracking-[0.16em] text-ok">
          <span className="live-dot size-1.5 rounded-full bg-ok" />
          Live
        </span>
      </Section>

      <Section ready={ready} order={1} className="group transition-colors duration-300 hover:bg-mint/40">
        <Label>Fleet efficiency</Label>
        <div className="mt-1 flex items-baseline gap-1">
          <AnimatedNumber
            ready={ready}
            value={96.4}
            delay={1700}
            format={{ minimumFractionDigits: 1, maximumFractionDigits: 1 }}
            className="text-[22px] font-semibold leading-none text-ink"
            suffix="%"
            live={{ amp: 0.3, every: 4200, decimals: 1 }}
          />
        </div>
        <Sparkline ready={ready} />
      </Section>

      <Section ready={ready} order={2} className="group transition-colors duration-300 hover:bg-mint/40">
        <Label>Active vessels</Label>
        <div className="mt-1 flex items-center justify-between">
          <AnimatedNumber
            ready={ready}
            value={3406}
            delay={1900}
            className="text-[22px] font-semibold leading-none text-ink"
            live={{ amp: 5, every: 5100 }}
          />
          <span className="rounded-full bg-ok/10 px-2 py-0.5 font-mono text-[9px] font-semibold tracking-wide text-ok">
            +12 · 24H
          </span>
        </div>
      </Section>

      <Section ready={ready} order={3} className="group transition-colors duration-300 hover:bg-mint/40">
        <div className="flex items-baseline justify-between">
          <Label>Port performance</Label>
          <AnimatedNumber
            ready={ready}
            value={89}
            delay={2100}
            className="text-sm font-semibold text-ink"
            suffix="%"
            live={{ amp: 1, every: 6300 }}
          />
        </div>
        <PortBars ready={ready} />
      </Section>

      <Section ready={ready} order={4}>
        <Label>Chokepoint risk · top 3</Label>
        <RiskRows ready={ready} />
      </Section>

      <Section ready={ready} order={5} className="mt-auto">
        <Label>Live weather patterns</Label>
        <WeatherRow />
      </Section>
    </aside>
  );
}
