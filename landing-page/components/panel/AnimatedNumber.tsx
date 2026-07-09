"use client";

import { useEffect, useState } from "react";
import NumberFlow, { type Format } from "@number-flow/react";

/**
 * NumberFlow wrapper: counts up from 0 once the hero is revealed, then
 * optionally random-walks around the base value so the feed feels live.
 */
export default function AnimatedNumber({
  value,
  ready,
  delay = 0,
  format,
  className,
  suffix,
  live,
}: {
  value: number;
  ready: boolean;
  delay?: number;
  format?: Format;
  className?: string;
  suffix?: string;
  /** amp: max drift from base; every: ms between ticks; decimals: rounding */
  live?: { amp: number; every: number; decimals?: number };
}) {
  const [v, setV] = useState(0);

  const amp = live?.amp;
  const every = live?.every;
  const decimals = live?.decimals ?? 0;

  // Count up after `delay`, then (optionally) drift around the base value.
  useEffect(() => {
    if (!ready) return;
    let interval: number | undefined;
    const t = window.setTimeout(() => {
      setV(value);
      if (amp !== undefined && every !== undefined) {
        const scale = 10 ** decimals;
        interval = window.setInterval(() => {
          const next = value + (Math.random() - 0.5) * 2 * amp;
          setV(Math.round(next * scale) / scale);
        }, every);
      }
    }, delay);
    return () => {
      window.clearTimeout(t);
      if (interval !== undefined) window.clearInterval(interval);
    };
  }, [ready, value, delay, amp, every, decimals]);

  return (
    <span className={className}>
      <NumberFlow
        value={v}
        format={format}
        transformTiming={{ duration: 800, easing: "cubic-bezier(0.16,1,0.3,1)" }}
        spinTiming={{ duration: 1300, easing: "cubic-bezier(0.16,1,0.3,1)" }}
        className="tabular-nums"
      />
      {suffix && (
        <span className="ml-0.5 text-[0.62em] font-medium text-soft">
          {suffix}
        </span>
      )}
    </span>
  );
}
