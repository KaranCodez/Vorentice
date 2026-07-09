"use client";

const ITEMS = [
  { label: "Wind", value: "14 KT", icon: WindIcon },
  { label: "Swell", value: "1.8 M", icon: SwellIcon },
  { label: "Vis", value: "8 NM", icon: VisIcon },
];

export default function WeatherRow() {
  return (
    <div className="mt-1.5 grid grid-cols-3 divide-x divide-line">
      {ITEMS.map(({ label, value, icon: Icon }) => (
        <div
          key={label}
          className="flex flex-col items-center gap-0.5 py-0.5 text-soft transition-colors duration-200 hover:text-accent"
        >
          <Icon className="size-[13px]" />
          <span className="font-mono text-[9px] font-semibold tabular-nums tracking-wide text-ink">
            {value}
          </span>
          <span className="font-mono text-[8px] uppercase tracking-[0.16em]">
            {label}
          </span>
        </div>
      ))}
    </div>
  );
}

function WindIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className} aria-hidden>
      <path
        d="M1.5 5.5h7a2 2 0 1 0-1.9-2.6M1.5 8.5h11a2 2 0 1 1-1.9 2.6M1.5 11.5h5.5"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function SwellIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className} aria-hidden>
      <path
        d="M1 6.5c2.3-3 4.7-3 7 0s4.7 3 7 0M1 10.5c2.3-3 4.7-3 7 0s4.7 3 7 0"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function VisIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className} aria-hidden>
      <path
        d="M1.5 8s2.4-4 6.5-4 6.5 4 6.5 4-2.4 4-6.5 4S1.5 8 1.5 8Z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
      />
      <circle cx="8" cy="8" r="1.8" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}
