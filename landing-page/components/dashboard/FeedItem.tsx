import { isSignal, type NewsItem, type Severity } from "@/lib/newsApi";

const SEVERITY_STYLE: Record<Severity, string> = {
  critical: "bg-alarm/15 text-alarm border-alarm/30",
  high: "bg-warn/15 text-warn border-warn/30",
  medium: "bg-accent-bright/10 text-accent-bright border-accent-bright/25",
  low: "bg-white/5 text-white/40 border-white/10",
};

function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const mins = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 60000));
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m`;
  const hours = Math.round(mins / 60);
  return hours < 24 ? `${hours}h` : `${Math.round(hours / 24)}d`;
}

/** One intelligence item row in the live feed. */
export default function FeedItem({ item }: { item: NewsItem }) {
  return (
    <li className="group border-b border-white/5 px-5 py-3.5 transition-colors hover:bg-white/[0.03]">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="mb-1.5 flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full border px-2 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-[0.14em] ${
                item.criticality === "Emerging"
                  ? "border-accent/30 bg-accent/15 text-accent-bright"
                  : SEVERITY_STYLE[item.severity]
              }`}
            >
              {item.criticality}
            </span>
            {isSignal(item) ? (
              <span className="rounded-full border border-accent/30 bg-accent/10 px-2 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-[0.14em] text-accent-bright">
                ◆ signal · {item.source_name}
              </span>
            ) : (
              <span className="font-mono text-[9px] uppercase tracking-[0.16em] text-white/30">
                {item.source_name.replace("gdelt:", "")}
              </span>
            )}
            {item.corroboration_count > 1 && (
              <span className="rounded-full bg-accent-bright/10 px-2 py-0.5 font-mono text-[9px] font-semibold tracking-wide text-accent-bright">
                ×{item.corroboration_count} sources
              </span>
            )}
            {item.chokepoints.map((c) => (
              <span
                key={c}
                className="rounded-full bg-white/5 px-2 py-0.5 font-mono text-[9px] tracking-wide text-white/45"
              >
                {c}
              </span>
            ))}
          </div>
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="text-[13.5px] font-medium leading-snug text-white/85 underline-offset-2 transition-colors hover:text-accent-bright hover:underline"
          >
            {item.title}
          </a>
          {item.summary && item.summary !== item.title && (
            <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-white/40">
              {item.summary}
            </p>
          )}
          {item.trade_impact && (
            <p className="mt-1.5 line-clamp-2 border-l-2 border-warn/30 pl-2 text-[11px] leading-relaxed text-white/45">
              <span className="font-mono text-[8px] uppercase tracking-[0.14em] text-warn/70">
                Trade impact ·{" "}
              </span>
              {item.trade_impact}
            </p>
          )}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5 pt-0.5">
          <span className="font-mono text-[10px] tabular-nums text-white/35">
            {timeAgo(item.published_at ?? item.fetched_at)}
          </span>
        </div>
      </div>
    </li>
  );
}
