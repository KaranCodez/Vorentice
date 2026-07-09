# Vorentice — Landing Page

Cinematic single-screen landing page for **Vorentice**, the 24/7 multi-agent
AI intelligence layer for national crude-oil supply security.

## Experience

1. **Boot screen** — the wordmark assembles letter-by-letter (with a live
   radar "O") while a telemetry counter runs to 100, then the dark curtain
   lifts.
2. **Reveal** — title letters rise from a mask, the world map draws its
   tanker routes, chokepoint markers spring in, and the Global Operations
   panel counts its numbers up.
3. **Alive at rest** — vessels sail the routes (SMIL `animateMotion`),
   dashes flow, risk chips pulse, telemetry values drift, the live feed
   ticker scrolls, and the IST clock ticks.
4. **Hover** — magnetic Enter button with shine sweep and arrow swap, title
   letters lift, chokepoint tooltips with risk bars, card tilt toward the
   cursor, and a lat/lon crosshair readout tracks the mouse over the map.

## Stack

- **Next.js 16** (App Router, Turbopack) + TypeScript
- **Tailwind CSS v4** — design tokens in `app/globals.css`
- **motion** (`motion/react`) — entrance choreography, springs, path draws
- **@number-flow/react** — rolling-digit stat counters
- **d3-geo + topojson-client + world-atlas** — real equirectangular world
  map, projected once at module load in `lib/geo.ts`

## Structure

```
app/            layout, page (preloader → hero), dashboard placeholder
components/
  preloader/    boot screen + counter
  hero/         nav, title, tagline, CTA, bottom bar
  map/          map card, world SVG, routes, markers, ticker, cursor readout
  panel/        Global Operations telemetry (NumberFlow, sparkline, bars…)
lib/            geo projection helpers, domain data, shared easings
```

All route/chokepoint/telemetry figures come from the project brief
(`../project_A.pdf`): Hormuz 87% risk, $42M procurement saving, 1.2M bbl
deficit, Jamnagar/Paradip supply watch, Cape of Good Hope failover.

## Run

```bash
npm install
npm run dev    # http://localhost:3000
npm run build  # production build (all routes static)
```

The **Enter Command Center** button links to `/dashboard`, a placeholder
route where the real product will mount later.
