// Geo projection + SVG path helpers for the hero world map.
// Computed once at module load — everything downstream is static strings.
/* eslint-disable @typescript-eslint/no-explicit-any */
import { geoEquirectangular, geoGraticule, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import worldTopo from "world-atlas/countries-110m.json";
import type { LonLat } from "./map-data";

export const MAP_W = 1000;
export const MAP_H = 560;

const topo = worldTopo as any;

// Drop Antarctica so the fit spends its pixels on shipping latitudes.
const landGeoms = {
  type: "GeometryCollection",
  geometries: topo.objects.countries.geometries.filter(
    (g: any) => g.properties?.name !== "Antarctica",
  ),
};

const land = feature(topo, landGeoms as any) as any;

const projection = geoEquirectangular().fitExtent(
  [
    [-6, -2],
    [MAP_W + 6, MAP_H + 2],
  ],
  land,
);
const path = geoPath(projection);

export const LAND_PATH = path(land) ?? "";
export const GRATICULE_PATH = path(geoGraticule().step([30, 20])()) ?? "";

export function project([lon, lat]: LonLat): [number, number] {
  const p = projection([lon, lat]);
  return p ? [Math.round(p[0] * 10) / 10, Math.round(p[1] * 10) / 10] : [0, 0];
}

/** Position helper for HTML overlays that sit on top of the SVG. */
export function projectPct([lon, lat]: LonLat): { left: string; top: string } {
  const [x, y] = project([lon, lat]);
  return {
    left: `${((x / MAP_W) * 100).toFixed(2)}%`,
    top: `${((y / MAP_H) * 100).toFixed(2)}%`,
  };
}

/** Inverse projection — viewBox px back to lon/lat (for the cursor readout). */
export function unproject(x: number, y: number): LonLat | null {
  const p = projection.invert?.([x, y]);
  if (!p || !Number.isFinite(p[0]) || !Number.isFinite(p[1])) return null;
  if (p[0] < -180 || p[0] > 180 || p[1] < -90 || p[1] > 90) return null;
  return [Math.round(p[0] * 10) / 10, Math.round(p[1] * 10) / 10];
}

/** Catmull-Rom → cubic Bézier smoothing through projected waypoints. */
export function smoothRoutePath(waypoints: LonLat[]): string {
  const pts = waypoints.map(project);
  if (pts.length < 2) return "";
  const r = (n: number) => Math.round(n * 10) / 10;
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(pts.length - 1, i + 2)];
    const c1x = r(p1[0] + (p2[0] - p0[0]) / 6);
    const c1y = r(p1[1] + (p2[1] - p0[1]) / 6);
    const c2x = r(p2[0] - (p3[0] - p1[0]) / 6);
    const c2y = r(p2[1] - (p3[1] - p1[1]) / 6);
    d += `C${c1x},${c1y} ${c2x},${c2y} ${p2[0]},${p2[1]}`;
  }
  return d;
}
