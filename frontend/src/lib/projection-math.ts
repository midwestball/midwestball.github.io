import type { ProjectionEntityDistribution } from "@/lib/projections";

const EPS = 1e-12;

function assertCurve(grid: readonly number[], curve: ProjectionEntityDistribution) {
  if (grid.length < 2 || curve.pdf.length !== grid.length || curve.cdf.length !== grid.length) {
    throw new Error("Projection grid and distribution lengths do not match");
  }
}

/** Area under the published piecewise-linear PDF through x. */
export function probabilityAtPoints(grid: readonly number[], curve: ProjectionEntityDistribution, x: number): number {
  assertCurve(grid, curve);
  const wall = curve.lowerBound;
  if (!Number.isFinite(x)) throw new Error("Points must be finite");
  if ((wall !== null && x <= wall) || x <= grid[0]!) return 0;
  if (x >= grid[grid.length - 1]!) return 1;
  let lo = 0, hi = grid.length - 1;
  while (lo + 1 < hi) { const mid = (lo + hi) >> 1; if (grid[mid]! <= x) lo = mid; else hi = mid; }
  if (x === grid[lo]) return curve.cdf[lo]!;
  const width = grid[hi]! - grid[lo]!;
  const dx = x - grid[lo]!;
  const y = curve.pdf[lo]! + (curve.pdf[hi]! - curve.pdf[lo]!) * dx / width;
  return Math.min(1, Math.max(0, curve.cdf[lo]! + (curve.pdf[lo]! + y) * dx / 2));
}

/** Generalized inverse of the published piecewise-linear PDF's CDF. */
export function pointsAtProbability(grid: readonly number[], curve: ProjectionEntityDistribution, p: number): number {
  assertCurve(grid, curve);
  if (!Number.isFinite(p) || p < 0 || p > 1) throw new Error("Probability must be between 0 and 1");
  if (p === 0) return curve.lowerBound ?? grid[0]!;
  if (p === 1) return grid[grid.length - 1]!;
  let hi = curve.cdf.findIndex((v) => v >= p);
  if (hi < 0) return grid[grid.length - 1]!;
  if (hi === 0) return grid[0]!;
  // A plateau's first satisfying point is its left edge.
  while (hi > 0 && Math.abs(curve.cdf[hi - 1]! - p) <= EPS) hi--;
  const lo = hi - 1;
  const target = p - curve.cdf[lo]!;
  if (target <= EPS) return grid[lo]!;
  const width = grid[hi]! - grid[lo]!;
  const y0 = curve.pdf[lo]!, slope = (curve.pdf[hi]! - y0) / width;
  let dx: number;
  if (Math.abs(slope) < EPS) dx = y0 > EPS ? target / y0 : width;
  else {
    const disc = Math.max(0, y0 * y0 + 2 * slope * target);
    // Stable root for y0*dx + slope*dx^2/2 = target.
    dx = (2 * target) / (y0 + Math.sqrt(disc));
  }
  return grid[lo]! + Math.min(width, Math.max(0, dx));
}

export function pdfAtPoints(grid: readonly number[], pdf: readonly number[], x: number): number {
  if (x < grid[0]! || x > grid[grid.length - 1]!) return 0;
  const exact = grid.indexOf(x); if (exact >= 0) return pdf[exact]!;
  let i = 0; while (i + 1 < grid.length && grid[i + 1]! < x) i++;
  return pdf[i]! + (pdf[i + 1]! - pdf[i]!) * (x - grid[i]!) / (grid[i + 1]! - grid[i]!);
}

/**
 * Chance of scoring AT LEAST x points. The published CDF gives "at most", so this
 * is the complement. Fantasy decisions are upper-tail questions ("12+ points"),
 * which is why the UI presents this form rather than the raw CDF.
 */
export function probabilityAtLeast(grid: readonly number[], curve: ProjectionEntityDistribution, x: number): number {
  return 1 - probabilityAtPoints(grid, curve, x);
}

/** Fantasy comparison groups. Comparisons are only meaningful inside a group. */
export type ComparisonGroup = "QB" | "SKILL" | "K" | "DST";
export function comparisonGroup(position: string): ComparisonGroup {
  switch (position.toUpperCase()) {
    case "QB": return "QB";
    case "K": return "K";
    case "DST": return "DST";
    case "RB":
    case "WR":
    case "TE": return "SKILL";
    default: throw new Error(`unknown position: ${position}`);
  }
}
export function canCompare(a: string, b: string): boolean {
  return comparisonGroup(a) === comparisonGroup(b);
}

export type ThresholdQuery = { source: "points"; value: number } | { source: "probability"; value: number };
/**
 * Resolve a threshold. `probability` is always the chance of scoring AT LEAST
 * `points`, so a typed probability is inverted through the CDF on the way in.
 */
export function resolveThreshold(grid: readonly number[], curve: ProjectionEntityDistribution, query: ThresholdQuery) {
  const points = query.source === "points" ? query.value : pointsAtProbability(grid, curve, 1 - query.value);
  const atMost = probabilityAtPoints(grid, curve, points);
  return { points, probability: 1 - atMost, atMost };
}
