"use client";

import Navbar from "./Navbar";
import HeroTitle from "./HeroTitle";
import Tagline from "./Tagline";
import BottomBar from "./BottomBar";
import MapCard from "@/components/map/MapCard";

/** Full-viewport hero — the only section of the page. */
export default function Hero({ ready }: { ready: boolean }) {
  return (
    <main className="relative flex min-h-dvh flex-col overflow-clip px-4 sm:px-8">
      <BackgroundField />
      <Navbar ready={ready} />

      <section className="relative z-10 mx-auto mt-3 flex w-full max-w-[1160px] flex-col items-center text-center md:mt-4">
        <HeroTitle ready={ready} />
        <Tagline ready={ready} />
      </section>

      <section className="relative z-10 mx-auto mt-5 w-full max-w-[1060px]">
        <MapCard ready={ready} />
      </section>

      <BottomBar ready={ready} />
    </main>
  );
}

/** Faint blueprint grid + mint bloom behind everything. */
function BackgroundField() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 z-0">
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            "linear-gradient(to right, rgba(13,148,136,0.05) 1px, transparent 1px), linear-gradient(to bottom, rgba(13,148,136,0.05) 1px, transparent 1px)",
          backgroundSize: "56px 56px",
          maskImage:
            "radial-gradient(ellipse 90% 75% at 50% 28%, black 25%, transparent 78%)",
          WebkitMaskImage:
            "radial-gradient(ellipse 90% 75% at 50% 28%, black 25%, transparent 78%)",
        }}
      />
      <div className="absolute left-1/2 top-[-240px] h-[430px] w-[780px] -translate-x-1/2 rounded-full bg-mint opacity-70 blur-3xl" />
    </div>
  );
}
