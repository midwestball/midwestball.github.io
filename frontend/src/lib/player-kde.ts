import type { Point, StatPayload } from "@/lib/distribution";

type ValueCount = { value: number; count: number };
type Domain = { xMin: number; xMax: number; lowerBound?: number; upperBound?: number };
type PlayerKde = { curve: Point[]; xMin: number; xMax: number; yMax: number };

/** Reproduce Ballnet's original 512-point, reflected Scott-bandwidth KDE. */
export function playerKdeFromCounts(counts: ValueCount[], domain: Domain): PlayerKde | null {
  if (!counts.length || counts.some(({ value, count }) =>
    !Number.isFinite(value) || !Number.isSafeInteger(count) || count <= 0)) return null;

  const n = counts.reduce((sum, row) => sum + row.count, 0);
  if (!Number.isSafeInteger(n)) return null;
  const xMin = Math.min(...counts.map(row => row.value));
  const maxValue = Math.max(...counts.map(row => row.value));
  const xMax = maxValue > xMin ? maxValue : xMin + Math.max((domain.xMax - domain.xMin) * 0.01, 1e-6);
  const dx = (xMax - xMin) / 511;
  const mean = counts.reduce((sum, row) => sum + row.value * row.count, 0) / n;
  const sumSquares = counts.reduce((sum, row) => sum + row.count * (row.value - mean) ** 2, 0);
  const standardDeviation = Math.sqrt(sumSquares / n);

  if (n === 1 || standardDeviation < 1e-12) {
    const curve = Array.from({ length: 512 }, (_, i) => ({ x: xMin + i * dx, y: i === 0 ? 1 / dx : 0 }));
    return { curve, xMin, xMax, yMax: 1 / dx };
  }

  const bandwidth = Math.sqrt(sumSquares / (n - 1)) * n ** (-0.2);
  const evaluate = (point: number) => counts.reduce((sum, row) => {
    const z = (point - row.value) / bandwidth;
    return sum + row.count * Math.exp(-0.5 * z * z);
  }, 0) / (n * bandwidth * Math.sqrt(2 * Math.PI));
  const curve = Array.from({ length: 512 }, (_, i) => {
    const x = xMin + i * dx;
    if ((domain.lowerBound != null && x < domain.lowerBound) || (domain.upperBound != null && x > domain.upperBound)) return { x, y: 0 };
    let y = evaluate(x);
    if (domain.lowerBound != null) y += evaluate(2 * domain.lowerBound - x);
    if (domain.upperBound != null) y += evaluate(2 * domain.upperBound - x);
    return { x, y };
  });
  let integral = 0;
  for (let i = 1; i < curve.length; i++) integral += (curve[i - 1].y + curve[i].y) * dx / 2;
  const normalized = integral > 0 ? curve.map(point => ({ ...point, y: point.y / integral })) : curve;
  return { curve: normalized, xMin, xMax, yMax: Math.max(...normalized.map(point => point.y)) };
}

/** Legacy curves are kept verbatim; v2 curves use exact counts, never histogram bins. */
export function playerKdeForStat(stat: StatPayload): PlayerKde | null {
  if (stat.curve.length) return { curve: stat.curve, xMin: stat.xMin, xMax: stat.xMax, yMax: stat.yMax };
  return playerKdeFromCounts(stat.valueCounts ?? [], {
    ...(stat.kdeDomain ?? { xMin: stat.xMin, xMax: stat.xMax }),
    lowerBound: stat.lowerBound,
    upperBound: stat.upperBound,
  });
}
