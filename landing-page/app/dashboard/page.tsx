import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Command Center — VORENTICE",
};

/** Placeholder — the real execution layer plugs in here later. */
export default function Dashboard() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-6 bg-void px-6 text-center text-[#e8f2ef]">
      <span className="flex items-center gap-2 rounded-full border border-white/10 px-4 py-1.5 font-mono text-[10px] uppercase tracking-[0.22em] text-white/50">
        <span className="live-dot size-1.5 rounded-full bg-accent-bright" />
        Access pending
      </span>
      <h1 className="text-3xl font-bold tracking-tight sm:text-5xl">
        Command Center
      </h1>
      <p className="max-w-md text-sm leading-relaxed text-white/45">
        The execution layer is under construction. The four agents keep watch
        in the meantime.
      </p>
      <Link
        href="/"
        className="font-mono text-[11px] uppercase tracking-[0.2em] text-accent-bright underline-offset-4 transition-colors hover:text-white hover:underline"
      >
        ← Return to surface
      </Link>
    </main>
  );
}
