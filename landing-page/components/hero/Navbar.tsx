"use client";

import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { EASE_OUT } from "@/lib/motion";

export default function Navbar({ ready }: { ready: boolean }) {
  const [time, setTime] = useState("");

  useEffect(() => {
    const fmt = new Intl.DateTimeFormat("en-GB", {
      timeZone: "Asia/Kolkata",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
    const update = () => setTime(fmt.format(new Date()));
    update();
    const id = window.setInterval(update, 1000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <motion.header
      initial={{ y: -18, opacity: 0 }}
      animate={ready ? { y: 0, opacity: 1 } : {}}
      transition={{ duration: 0.8, delay: 0.35, ease: EASE_OUT }}
      className="relative z-20 mx-auto flex h-12 w-full max-w-[1160px] items-center justify-between"
    >
      <div className="font-wordmark flex items-center gap-2 text-[15px] font-extrabold tracking-[0.08em] text-ink">
        <span className="inline-block size-2 rounded-full bg-accent shadow-[0_0_10px_rgba(13,148,136,0.8)]" />
        VORENTICE
      </div>
      <div className="flex items-center gap-2.5 font-mono text-[10px] uppercase tracking-[0.18em] text-soft">
        <span className="hidden items-center gap-1.5 rounded-full border border-line bg-card px-3 py-1.5 sm:flex">
          <span className="live-dot size-1.5 rounded-full bg-ok" />
          Systems nominal
        </span>
        <span className="hidden rounded-full border border-line bg-card px-3 py-1.5 tabular-nums md:block">
          {time || "--:--:--"} IST
        </span>
      </div>
    </motion.header>
  );
}
