/**
 * League-distribution payloads that match the contract Ballnet will serve.
 *
 * Continuous stats → precomputed Gaussian KDE with reflection at bounds.
 * Discrete stats   → uniform-width histograms (empty bins included).
 * Y-axis           → relative frequency (proportion), never raw counts.
 * X-axis           → fixed global [min, max] so charts stay comparable.
 *
 * `format` is a catalog enum (JSON-safe). Percentile is inclusive CDF P(X ≤ x),
 * already oriented so high = good.
 */

import type { ValueFormat } from "@/lib/catalog/types";
import { formatStatValue } from "@/lib/catalog/format";

export type StatAvailabilityStatus =
  | "ready"
  | "pending"
  | "insufficient_sample"
  | "missing_source"
  | "not_in_nflverse";

export type Point = { x: number; y: number };

export type HistogramBin = {
  x0: number;
  x1: number;
  mid: number;
  y: number;
  count: number;
};

type StatBase = {
  id: string;
  label: string;
  section: string;
  playerValue: number | null;
  percentile: number | null;
  higherIsBetter: boolean;
  xMin: number;
  xMax: number;
  yMax: number;
  format: ValueFormat;
  availability: StatAvailabilityStatus;
  minN: number | null;
  denom: string;
};

export type ContinuousStat = StatBase & {
  kind: "continuous";
  curve: Point[];
  lowerBound?: number;
  upperBound?: number;
};

export type DiscreteStat = StatBase & {
  kind: "discrete";
  binWidth: number;
  bins: HistogramBin[];
};

export type StatPayload = ContinuousStat | DiscreteStat;

export const CHART_PLOT = {
  left: 52,
  right: 16,
  top: 10,
  bottom: 28,
  height: 220,
} as const;

export function insertValuePoint(curve: Point[], x: number): Point[] {
  if (curve.length === 0) return curve;
  if (curve.some((point) => Math.abs(point.x - x) < 1e-9)) return curve;

  const nextIndex = curve.findIndex((point) => point.x > x);
  if (nextIndex === -1) {
    const last = curve[curve.length - 1];
    return last ? [...curve, { x, y: last.y }] : curve;
  }
  if (nextIndex === 0) {
    const first = curve[0];
    return first ? [{ x, y: first.y }, ...curve] : curve;
  }

  const left = curve[nextIndex - 1];
  const right = curve[nextIndex];
  if (!left || !right) return curve;
  const t = (x - left.x) / (right.x - left.x);
  const y = left.y + t * (right.y - left.y);
  return [...curve.slice(0, nextIndex), { x, y }, ...curve.slice(nextIndex)];
}

export function shadedThrough(curve: Point[], playerValue: number): Point[] {
  return insertValuePoint(curve, playerValue).filter(
    (point) => point.x <= playerValue + 1e-9,
  );
}

export function kdeCdf(curve: Point[], value: number): number {
  if (curve.length < 2) return 0;
  let mass = 0;
  let total = 0;
  for (let i = 1; i < curve.length; i += 1) {
    const left = curve[i - 1];
    const right = curve[i];
    if (!left || !right) continue;
    const slice = ((left.y + right.y) / 2) * (right.x - left.x);
    total += slice;
    if (right.x <= value) {
      mass += slice;
    } else if (left.x < value) {
      const t = (value - left.x) / (right.x - left.x);
      const y = left.y + t * (right.y - left.y);
      mass += ((left.y + y) / 2) * (value - left.x);
    }
  }
  return total > 0 ? Math.min(1, Math.max(0, mass / total)) : 0;
}

export function histogramCdf(bins: HistogramBin[], value: number): number {
  let mass = 0;
  for (const bin of bins) {
    if (value >= bin.x1) {
      mass += bin.y;
    } else if (value > bin.x0) {
      mass += bin.y * ((value - bin.x0) / (bin.x1 - bin.x0));
      break;
    } else {
      break;
    }
  }
  return Math.min(1, Math.max(0, mass));
}

export function percentileAt(stat: StatPayload, value: number): number {
  const cdf =
    stat.kind === "continuous"
      ? kdeCdf(stat.curve, value)
      : histogramCdf(stat.bins, value);
  const pct = cdf * 100;
  return stat.higherIsBetter ? pct : 100 - pct;
}

export function playerStandingParts(stat: StatPayload): {
  pctLabel: string;
  rest: string;
} {
  const pct = Math.round(stat.percentile ?? 0);
  const direction = stat.higherIsBetter ? "or lower" : "or higher";
  const value =
    stat.playerValue == null ? "—" : formatStatValue(stat.format, stat.playerValue);
  return {
    pctLabel: `${pct}%`,
    rest: ` of the league has a ${stat.label} of ${value} ${direction}.`,
  };
}

export function hoverStandingCopy(stat: StatPayload, value: number): string {
  return `This ${stat.label} is in the ${ordinal(percentileAt(stat, value))} percentile.`;
}

export function relativeFrequencyCopy(
  stat: StatPayload,
  y: number,
  bin?: HistogramBin,
): string {
  const pct = (y * 100).toFixed(1);
  if (stat.kind === "discrete" && bin) {
    return `${pct}% of the league has ${formatStatValue(stat.format, bin.x0)}.`;
  }
  return `Relative frequency: ${pct}% — how common this value is (higher means more typical).`;
}

export function binHighlighted(bin: HistogramBin, playerValue: number): boolean {
  return bin.x0 <= playerValue;
}

export function ordinal(value: number): string {
  const n = Math.round(value);
  const rem100 = n % 100;
  if (rem100 >= 11 && rem100 <= 13) return `${n}th`;
  switch (n % 10) {
    case 1:
      return `${n}st`;
    case 2:
      return `${n}nd`;
    case 3:
      return `${n}rd`;
    default:
      return `${n}th`;
  }
}

/** Savant-style blue (low) → red (high) percentile color. */
export function percentileColor(percentile: number): string {
  const t = Math.min(100, Math.max(0, percentile)) / 100;
  const stops: Array<{ t: number; c: [number, number, number] }> = [
    { t: 0, c: [44, 123, 182] },
    { t: 0.25, c: [171, 217, 233] },
    { t: 0.5, c: [255, 255, 191] },
    { t: 0.75, c: [253, 174, 97] },
    { t: 1, c: [215, 25, 28] },
  ];

  let left = stops[0];
  let right = stops[stops.length - 1];
  for (let i = 0; i < stops.length - 1; i += 1) {
    const current = stops[i];
    const next = stops[i + 1];
    if (current && next && t >= current.t && t <= next.t) {
      left = current;
      right = next;
      break;
    }
  }

  if (!left || !right) return "rgb(215, 25, 28)";
  const span = right.t - left.t || 1;
  const u = (t - left.t) / span;
  const mix = (a: number, b: number) => Math.round(a + (b - a) * u);
  return `rgb(${mix(left.c[0], right.c[0])}, ${mix(left.c[1], right.c[1])}, ${mix(left.c[2], right.c[2])})`;
}

export function withAlpha(rgb: string, alpha: number): string {
  const match = rgb.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
  if (!match) return rgb;
  return `rgba(${match[1]}, ${match[2]}, ${match[3]}, ${alpha})`;
}
