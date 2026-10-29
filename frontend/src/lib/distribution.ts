/**
 * League-distribution payloads that match the contract Ballnet serves.
 *
 * Every stat renders a KDE area chart from `curve[]`. Catalog `kind`
 * (continuous vs discrete) is formatting metadata only — it does not
 * select a histogram. Y-axis = KDE density (∫y dx ≈ 1).
 *
 * `format` is a catalog enum (JSON-safe). V2 percentiles are empirical
 * midranks; legacy percentiles come from the KDE. Both are oriented high = good.
 */

import type { ValueFormat } from "@/lib/catalog/types";
import { formatStatValue } from "@/lib/catalog/format";

export type StatAvailabilityStatus =
  | "ready"
  | "pending"
  | "insufficient_sample"
  | "insufficient_peers"
  | "missing_source"
  | "not_in_nflverse";

export type Point = { x: number; y: number };

export type StatPayload = {
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
  curve: Point[];
  bins?: Array<{ lower: number; upper: number; count: number }>;
  valueCounts?: Array<{ value: number; count: number }>;
  nSample?: number;
  /** Catalog domain used for the original KDE's degenerate-sample padding. */
  kdeDomain?: { xMin: number; xMax: number };
  kind: "continuous" | "discrete";
  lowerBound?: number;
  upperBound?: number;
};

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

export function shadedThrough(
  curve: Point[],
  playerValue: number,
  higherIsBetter = true,
): Point[] {
  const withValue = insertValuePoint(curve, playerValue);
  return higherIsBetter
    ? withValue.filter((point) => point.x <= playerValue + 1e-9)
    : withValue.filter((point) => point.x >= playerValue - 1e-9);
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

export function percentileAt(stat: StatPayload, value: number): number {
  if (stat.valueCounts?.length) {
    const n = stat.valueCounts.reduce((total, row) => total + row.count, 0);
    if (!n) return 0;
    const worse = stat.valueCounts.reduce((total, row) => total + ((stat.higherIsBetter ? row.value < value : row.value > value) ? row.count : 0), 0);
    const ties = stat.valueCounts.reduce((total, row) => total + (row.value === value ? row.count : 0), 0);
    return 100 * (worse + ties / 2) / n;
  }
  const pct = kdeCdf(stat.curve, value) * 100;
  return stat.higherIsBetter ? pct : 100 - pct;
}

export function playerStandingParts(stat: StatPayload): {
  prefix: string;
  pctLabel: string;
  rest: string;
} {
  const pct = Math.round(stat.percentile ?? 0);
  const note = stat.higherIsBetter ? "(Higher is better)" : "(Lower is better)";
  const value =
    stat.playerValue == null ? "—" : formatStatValue(stat.format, stat.playerValue);
  return {
    prefix: `${value} ${stat.label} is in the `,
    pctLabel: `${ordinal(pct)} percentile`,
    rest: stat.bins?.length ? ` among ${stat.nSample ?? "qualified"} qualified players; ties split evenly. ${note}` : ` of the modeled league distribution. ${note}`,
  };
}

export function hoverStandingCopy(stat: StatPayload, value: number): string {
  return `This ${stat.label} is in the ${ordinal(percentileAt(stat, value))} percentile.`;
}

export function relativeFrequencyCopy(y: number): string {
  // KDE y is density (∫y dx ≈ 1), not a percent of the league.
  return `Density: ${y.toFixed(2)} — how concentrated values are here (higher means more typical).`;
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

function parseRgb(rgb: string): [number, number, number] | null {
  const match = rgb.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
  if (!match) return null;
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

/** Savant-style blue (low) → red (high) percentile color. */
export function percentileColor(percentile: number): string {
  const t = Math.min(100, Math.max(0, percentile)) / 100;
  return savantGradient(t);
}

/** Dark text on pale mid-scale yellows/cyans; white on deep blue/red. */
export function percentileContrastText(percentile: number): string {
  return savantContrastText(percentileColor(percentile));
}

/**
 * Map oriented z-score to the Savant palette. Clip ±3σ → ends of the scale;
 * 0σ sits at mid yellow.
 */
export function sigmaColor(zScore: number): string {
  const clipped = Math.min(3, Math.max(-3, zScore));
  const t = (clipped + 3) / 6;
  return savantGradient(t);
}

export function sigmaContrastText(zScore: number): string {
  return savantContrastText(sigmaColor(zScore));
}

function savantGradient(t: number): string {
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

function savantContrastText(rgbColor: string): string {
  const rgb = parseRgb(rgbColor);
  if (!rgb) return "#ffffff";
  const [r, g, b] = rgb;
  const luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  return luminance > 0.62 ? "#18181b" : "#ffffff";
}

export function formatZScore(z: number): string {
  const sign = z >= 0 ? "+" : "";
  return `${sign}${z.toFixed(2)}σ`;
}

export function sigmaStandingParts(stat: {
  label: string;
  playerValue: number | null;
  format: ValueFormat;
  higherIsBetter: boolean;
  zScore: number;
}): {
  prefix: string;
  zLabel: string;
  rest: string;
} {
  const note = stat.higherIsBetter ? "(Higher is better)" : "(Lower is better)";
  const value =
    stat.playerValue == null ? "—" : formatStatValue(stat.format, stat.playerValue);
  return {
    prefix: `${value} ${stat.label} is `,
    zLabel: formatZScore(stat.zScore),
    rest: ` versus single-game peers this season. ${note}`,
  };
}

export function hoverSigmaStandingCopy(
  label: string,
  zScore: number,
): string {
  return `This ${label} is ${formatZScore(zScore)} versus single-game peers this season.`;
}

/** Order-of-magnitude rarity ladder (matches ballnet.scoring.RARITY_TIERS). */
export const RARITY_TIERS = Array.from({ length: 10 }, (_, k) => [1, 2, 5].map(n => n * 10 ** k)).flat();

/** Geometric nearest snap onto RARITY_TIERS (log space). */
export function snapOneInN(n: number | null | undefined): number | null {
  if (n == null || !Number.isFinite(n) || n < 1) return null;
  return RARITY_TIERS.filter(tier => tier <= n).at(-1) ?? null;
}

export function resolveRarityTier(row: {
  rarityTier?: number | null;
  oneInN: number | null;
  rarityMethod?: string;
}): number | null {
  if (row.rarityMethod !== "empirical-inclusive-v2") return null;
  if (row.rarityTier != null && Number.isFinite(row.rarityTier)) {
    return row.rarityTier;
  }
  return snapOneInN(row.oneInN);
}

export function formatOneInN(tier: number): string {
  return `1 in ${tier.toLocaleString("en-US")}`;
}

const RARITY_COLORS: Record<number, string> = {
  10: "rgb(112, 168, 104)", // common
  50: "rgb(173, 130, 80)", // bronze
  100: "rgb(168, 169, 173)", // silver
  1_000: "rgb(212, 175, 55)", // gold
  10_000: "rgb(126, 200, 227)", // diamond
  100_000: "rgb(123, 94, 167)", // purple
};

/** Higher 10^k reuse purple, stepping slightly lighter. */
export function rarityTierColor(tier: number): string {
  if (RARITY_COLORS[tier]) return RARITY_COLORS[tier]!;
  if (tier >= 1_000_000) return "rgb(168, 140, 210)";
  if (tier >= 100_000) return RARITY_COLORS[100_000]!;
  if (tier >= 10_000) return RARITY_COLORS[10_000]!;
  if (tier >= 1_000) return RARITY_COLORS[1_000]!;
  if (tier >= 100) return RARITY_COLORS[100]!;
  if (tier >= 50) return RARITY_COLORS[50]!;
  return RARITY_COLORS[10]!;
}

export function rarityTierContrastText(tier: number): string {
  return savantContrastText(rarityTierColor(tier));
}

/** Shimmer on bronze and rarer tiers. */
export function rarityTierShimmer(tier: number): boolean {
  return tier >= 50;
}

export function rarityStandingParts(stat: {
  label: string;
  playerValue: number | null;
  format: ValueFormat;
  higherIsBetter: boolean;
  rarityTier: number;
}): {
  prefix: string;
  rarityLabel: string;
  rest: string;
} {
  const note = stat.higherIsBetter ? "(Higher is better)" : "(Lower is better)";
  const value =
    stat.playerValue == null ? "—" : formatStatValue(stat.format, stat.playerValue);
  return {
    prefix: `${value} ${stat.label} is `,
    rarityLabel: formatOneInN(stat.rarityTier),
    rest: ` or more common among qualifying single-game peers since 2016. ${note}`,
  };
}

export function hoverRarityStandingCopy(label: string, rarityTier: number): string {
  return `This ${label} is ${formatOneInN(rarityTier)} or more common among qualifying single-game peers since 2016.`;
}
