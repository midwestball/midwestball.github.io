/**
 * NFL primary + secondary brand colors for UI swatches and compare chart identity.
 * Abbreviations match Ballnet / nflverse team codes.
 * Same-team brightness is resolved in `compareFillColor` (primary only).
 */

const TEAM_PRIMARY: Record<string, string> = {
  ARI: "#97233F",
  ATL: "#A71930",
  BAL: "#241773",
  BUF: "#00338D",
  CAR: "#0085CA",
  CHI: "#0B162A",
  CIN: "#FB4F14",
  CLE: "#311D00",
  DAL: "#003594",
  DEN: "#FB4F14",
  DET: "#0076B6",
  GB: "#203731",
  HOU: "#03202F",
  IND: "#002C5F",
  JAX: "#006778",
  KC: "#E31837",
  LAC: "#0080C6",
  LAR: "#003594",
  LV: "#000000",
  MIA: "#008E97",
  MIN: "#4F2683",
  NE: "#002244",
  NO: "#D3BC8D",
  NYG: "#0B2265",
  NYJ: "#125740",
  PHI: "#004C54",
  PIT: "#FFB612",
  SEA: "#002244",
  SF: "#AA0000",
  TB: "#D50A0A",
  TEN: "#0C2340",
  WAS: "#5A1414",
  WSH: "#5A1414",
};

/** Secondary brand color (paired with primary for diagonal swatches). */
const TEAM_SECONDARY: Record<string, string> = {
  ARI: "#000000",
  ATL: "#000000",
  BAL: "#9E7C0C",
  BUF: "#C60C30",
  CAR: "#101820",
  CHI: "#C83803",
  CIN: "#000000",
  CLE: "#FF3C00",
  DAL: "#869397",
  DEN: "#002244",
  DET: "#B0B7BC",
  GB: "#FFB612",
  HOU: "#A71930",
  IND: "#A2AAAD",
  JAX: "#D7A22A",
  KC: "#FFB81C",
  LAC: "#FFC20E",
  LAR: "#FFA300",
  LV: "#A5ACAF",
  MIA: "#FC4C02",
  MIN: "#FFC62F",
  NE: "#C60C30",
  NO: "#000000",
  NYG: "#A71930",
  NYJ: "#000000",
  PHI: "#A5ACAF",
  PIT: "#101820",
  SEA: "#69BE28",
  SF: "#B3995D",
  TB: "#34302B",
  TEN: "#4B92DB",
  WAS: "#FFB612",
  WSH: "#FFB612",
};

const FALLBACK_PRIMARY = "#52525b";
const FALLBACK_SECONDARY = "#a1a1aa";

export function teamPrimaryColor(team: string): string {
  const key = team.trim().toUpperCase();
  return TEAM_PRIMARY[key] ?? FALLBACK_PRIMARY;
}

export function teamSecondaryColor(team: string): string {
  const key = team.trim().toUpperCase();
  return TEAM_SECONDARY[key] ?? FALLBACK_SECONDARY;
}

/** CSS for a square swatch: primary top half, secondary bottom half. */
export function teamSwatchBackground(team: string): string {
  const primary = teamPrimaryColor(team);
  const secondary = teamSecondaryColor(team);
  return `linear-gradient(to bottom, ${primary} 50%, ${secondary} 50%)`;
}

function parseHex(hex: string): { r: number; g: number; b: number } | null {
  const raw = hex.replace("#", "").trim();
  if (raw.length !== 6) return null;
  const r = Number.parseInt(raw.slice(0, 2), 16);
  const g = Number.parseInt(raw.slice(2, 4), 16);
  const b = Number.parseInt(raw.slice(4, 6), 16);
  if ([r, g, b].some((n) => Number.isNaN(n))) return null;
  return { r, g, b };
}

function toHex({ r, g, b }: { r: number; g: number; b: number }): string {
  const clamp = (n: number) => Math.max(0, Math.min(255, Math.round(n)));
  return `#${[clamp(r), clamp(g), clamp(b)]
    .map((n) => n.toString(16).padStart(2, "0"))
    .join("")}`;
}

/** Mix toward white (`amount` 0 = base, 1 = white) so better teammates read brighter. */
function lighten(hex: string, amount: number): string {
  const rgb = parseHex(hex);
  if (!rgb) return hex;
  const t = Math.max(0, Math.min(1, amount));
  return toHex({
    r: rgb.r + (255 - rgb.r) * t,
    g: rgb.g + (255 - rgb.g) * t,
    b: rgb.b + (255 - rgb.b) * t,
  });
}

/** Mix toward black so weaker teammates stay darker on the same primary. */
function darken(hex: string, amount: number): string {
  const rgb = parseHex(hex);
  if (!rgb) return hex;
  const t = Math.max(0, Math.min(1, amount));
  return toHex({
    r: rgb.r * (1 - t),
    g: rgb.g * (1 - t),
    b: rgb.b * (1 - t),
  });
}

/**
 * Chart fill for a compare column. Same-team players share a primary;
 * higher `overallScore` (mean ready percentile) gets a brighter tint.
 */
export function compareFillColor(
  team: string,
  overallScore: number,
  teammateScores: number[],
): string {
  const primary = teamPrimaryColor(team);
  if (teammateScores.length <= 1) return primary;

  const sorted = [...teammateScores].sort((a, b) => a - b);
  const unique = [...new Set(sorted)];
  if (unique.length === 1) return primary;

  const rank = unique.indexOf(overallScore);
  const t = rank / (unique.length - 1);
  // Weakest ~25% darker; strongest ~35% lighter — keeps identity on dark primaries.
  if (t < 0.5) {
    return darken(primary, (0.5 - t) * 0.5);
  }
  return lighten(primary, (t - 0.5) * 0.7);
}
