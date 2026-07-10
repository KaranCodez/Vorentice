import type { Metadata } from "next";
import Link from "next/link";
import NewsFeed from "@/components/dashboard/NewsFeed";
import AgentStatus from "@/components/dashboard/AgentStatus";
import AlertBanner from "@/components/dashboard/AlertBanner";

export const metadata: Metadata = {
  title: "Command Center — VORENTICE",
};

/** Command Center — currently surfaces the News Agent's live feed.
 *  Risk, Route and Economic agent panels dock here in later phases. */
export default function Dashboard() {
  return (
    <main className="min-h-dvh bg-void px-4 py-8 text-[#e8f2ef] sm:px-8">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.22em] text-accent-bright">
              Command Center
            </p>
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
              Crude-Supply Intelligence
            </h1>
          </div>
          <Link
            href="/"
            className="font-mono text-[10px] uppercase tracking-[0.2em] text-white/40 underline-offset-4 transition-colors hover:text-accent-bright hover:underline"
          >
            ← Surface
          </Link>
        </header>

        <AgentStatus />
        <AlertBanner />
        <NewsFeed />

        <p className="text-center font-mono text-[9px] uppercase tracking-[0.2em] text-white/20">
          Risk · Route · Economic agents — docking soon
        </p>
      </div>
    </main>
  );
}
