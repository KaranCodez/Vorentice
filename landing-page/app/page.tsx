"use client";

import { useState } from "react";
import { AnimatePresence } from "motion/react";
import Preloader from "@/components/preloader/Preloader";
import Hero from "@/components/hero/Hero";

export default function Home() {
  const [loading, setLoading] = useState(true);

  return (
    <>
      <AnimatePresence>
        {loading && <Preloader onDone={() => setLoading(false)} />}
      </AnimatePresence>
      {/* Hero mounts immediately so the map is ready behind the curtain. */}
      <Hero ready={!loading} />
    </>
  );
}
