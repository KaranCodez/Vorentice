// Domain data for the Vorentice hero map — chokepoints, tanker routes,
// telemetry and ticker feed. All figures come from the project brief
// (project_A.pdf): Hormuz 87% risk, $42M saving, 1.2M bbl deficit, etc.

export type LonLat = [lon: number, lat: number];

export type Chokepoint = {
  id: string;
  name: string;
  coords: LonLat;
  risk: number; // live risk score, %
  status: "critical" | "elevated" | "stable" | "failover";
  note: string;
};

export type TradeRoute = {
  id: string;
  name: string;
  kind: "primary" | "standard" | "failover";
  waypoints: LonLat[];
  /** seconds for one vessel to traverse the route */
  vesselDuration: number;
  vessels: number;
};

export const CHOKEPOINTS: Chokepoint[] = [
  {
    id: "hormuz",
    name: "Strait of Hormuz",
    coords: [56.5, 26.4],
    risk: 87,
    status: "critical",
    note: "Closure threat detected · What-If sim running",
  },
  {
    id: "bab-el-mandeb",
    name: "Bab el-Mandeb",
    coords: [43.4, 12.6],
    risk: 71,
    status: "elevated",
    note: "Red Sea corridor under advisory",
  },
  {
    id: "suez",
    name: "Suez Canal",
    coords: [32.5, 30.2],
    risk: 64,
    status: "elevated",
    note: "Convoy spacing increased",
  },
  {
    id: "malacca",
    name: "Malacca Strait",
    coords: [100.5, 3.2],
    risk: 12,
    status: "stable",
    note: "Nominal traffic · 214 transits/day",
  },
  {
    id: "singapore",
    name: "Singapore",
    coords: [103.8, 1.35],
    risk: 9,
    status: "stable",
    note: "Bunkering hub · full capacity",
  },
  {
    id: "gibraltar",
    name: "Gibraltar",
    coords: [-5.6, 35.9],
    risk: 8,
    status: "stable",
    note: "Westbound flow nominal",
  },
  {
    id: "panama",
    name: "Panama Canal",
    coords: [-79.6, 9.1],
    risk: 23,
    status: "stable",
    note: "Draft restrictions · monitoring",
  },
  {
    id: "cape",
    name: "Cape of Good Hope",
    coords: [18.9, -34.8],
    risk: 4,
    status: "failover",
    note: "Failover corridor armed · +9.5 days ETA",
  },
];

export const TRADE_ROUTES: TradeRoute[] = [
  {
    // Ras Tanura → Hormuz → Jamnagar: India's primary crude artery
    id: "gulf-india",
    name: "Persian Gulf → India",
    kind: "primary",
    waypoints: [
      [50.2, 26.9],
      [54.2, 25.6],
      [56.5, 26.4],
      [59.5, 24.4],
      [64.5, 22.6],
      [69.1, 22.1],
    ],
    vesselDuration: 14,
    vessels: 3,
  },
  {
    // Gulf → Red Sea → Suez → Gibraltar → US Gulf coast
    id: "gulf-west",
    name: "Gulf → Suez → Atlantic",
    kind: "standard",
    waypoints: [
      [56.5, 26.4],
      [57.8, 22.0],
      [51.0, 13.4],
      [43.4, 12.6],
      [38.5, 20.5],
      [33.8, 27.4],
      [32.5, 30.2],
      [28.0, 33.2],
      [19.5, 34.6],
      [5.0, 37.2],
      [-5.6, 35.9],
      [-20.0, 36.5],
      [-45.0, 33.0],
      [-70.0, 26.5],
      [-88.0, 25.5],
      [-94.5, 28.8],
    ],
    vesselDuration: 34,
    vessels: 4,
  },
  {
    // Cape of Good Hope failover, bypassing Suez
    id: "cape-failover",
    name: "Cape of Good Hope failover",
    kind: "failover",
    waypoints: [
      [57.8, 22.0],
      [60.0, 8.0],
      [52.0, -12.0],
      [38.0, -28.0],
      [18.9, -34.8],
      [6.0, -22.0],
      [-4.0, -2.0],
      [-14.0, 16.0],
      [-14.5, 30.0],
      [-5.6, 35.9],
    ],
    vesselDuration: 40,
    vessels: 2,
  },
  {
    // Malacca → Singapore → East Asia
    id: "malacca-east",
    name: "Malacca → East Asia",
    kind: "standard",
    waypoints: [
      [95.0, 6.2],
      [100.5, 3.2],
      [103.8, 1.35],
      [108.5, 5.5],
      [113.0, 12.0],
      [118.5, 21.5],
      [122.3, 30.5],
    ],
    vesselDuration: 20,
    vessels: 3,
  },
  {
    // India → Malacca connector
    id: "india-malacca",
    name: "India → Malacca",
    kind: "standard",
    waypoints: [
      [69.1, 22.1],
      [72.5, 15.5],
      [77.0, 7.0],
      [84.0, 5.0],
      [95.0, 6.2],
    ],
    vesselDuration: 18,
    vessels: 2,
  },
  {
    // Panama ↔ Pacific
    id: "panama-pacific",
    name: "Panama → Pacific",
    kind: "standard",
    waypoints: [
      [-64.0, 18.0],
      [-72.0, 13.5],
      [-79.6, 9.1],
      [-90.0, 8.0],
      [-110.0, 14.0],
      [-130.0, 24.0],
      [-146.0, 33.0],
    ],
    vesselDuration: 26,
    vessels: 2,
  },
  {
    // West Africa → India (Atlantic supply diversification)
    id: "wafrica-india",
    name: "West Africa → India",
    kind: "standard",
    waypoints: [
      [5.5, 3.5],
      [10.0, -12.0],
      [18.9, -34.8],
      [40.0, -30.0],
      [58.0, -8.0],
      [69.1, 22.1],
    ],
    vesselDuration: 36,
    vessels: 2,
  },
];

export const OCEAN_LABELS: { name: string; coords: LonLat }[] = [
  { name: "Pacific Ocean", coords: [-152, 8] },
  { name: "Atlantic Ocean", coords: [-38, 12] },
  { name: "Indian Ocean", coords: [78, -22] },
];

export const REFINERIES: { name: string; coords: LonLat; tag: string }[] = [
  { name: "Jamnagar", coords: [70.05, 22.47], tag: "supply watch · 8d" },
  { name: "Paradip", coords: [86.6, 20.3], tag: "supply watch · 8d" },
];

export const TICKER_ITEMS = [
  "CRITICAL — News Agent: closure threat detected · Strait of Hormuz · risk 87%",
  "Route Agent: Cape of Good Hope failover armed · +9.5 days ETA",
  "Economic Agent: projected retail petrol +2.4% · $42M procurement saving identified",
  "Risk Agent: Jamnagar & Paradip refineries on critical supply watch · deficit in 8 days",
  "Advisory: release 3 days of Strategic Petroleum Reserve to stabilize domestic prices",
  "Risk Agent: predicted deficit 1.2M barrels over 14 days if no action taken",
];

export const AGENTS = [
  { name: "News Agent", role: "Geopolitical OSINT" },
  { name: "Risk Agent", role: "What-If Engine" },
  { name: "Route Agent", role: "Dynamic Rerouting" },
  { name: "Economic Agent", role: "Impact Forecasting" },
];
