import { isPositionCode, positionGroupOf, type PositionGroup, type StatDefinition } from "@/lib/catalog";
import type { FantasyPosRankKind, LeaderboardJson, LeaderboardRow } from "@/lib/payload";
import { matchesSearch } from "./fuzzy";
/** Publishable groups for board fetches — returner has no Stage G spine. */
export const BOARD_GROUPS: PositionGroup[] = [
  "qb",
  "backfield",
  "pass_catcher",
  "ol",
  "def_front",
  "secondary",
  "kicker",
  "punter",
];

/** Search Position options. WR/TE split the pass_catcher board client-side only. */
export type SearchPositionFilter =
  | Exclude<PositionGroup, "pass_catcher" | "returner">
  | "wr"
  | "te";

export const FILTER_OPTIONS: { id: SearchPositionFilter; label: string }[] = [
  { id: "qb", label: "Quarterback" },
  { id: "backfield", label: "Backfield" },
  { id: "wr", label: "Wide receiver" },
  { id: "te", label: "Tight end" },
  { id: "ol", label: "Offensive line" },
  { id: "def_front", label: "Defensive front" },
  { id: "secondary", label: "Secondary" },
  { id: "kicker", label: "Kicker" },
  { id: "punter", label: "Punter" },
];

export function boardGroupOf(filter: SearchPositionFilter): PositionGroup {
  if (filter === "wr" || filter === "te") return "pass_catcher";
  return filter;
}

export function matchesPositionFilter(
  position: string,
  filter: SearchPositionFilter,
): boolean {
  if (filter === "wr") return position === "WR";
  if (filter === "te") return position === "TE";
  if (!isPositionCode(position)) return false;
  return positionGroupOf(position) === filter;
}

export type SortMode = "best" | "worst";
export type BoardStatus = "idle" | "loading" | "ready" | "error";

export type PublishedSeason = {
  season: number;
  asOfWeek: number;
  completedWeek?: number;
};

/** Mirror Ballnet ramp–hold: min_n = n_base × min(completedWeek, 5). */
export function rampHoldMin(stat: StatDefinition, completedWeek: number): number | null {
  if (stat.minNBase == null) return null;
  const week = Number(completedWeek);
  if (!Number.isFinite(week) || week < 1) return null;
  return stat.minNBase * Math.min(week, 5);
}

/** Search-only sort key — not a catalog `stat.id` and not on player-page sliders. */
export const FANTASY_RANK_STAT_ID = "fantasy_pos_rank";
export const FANTASY_RANK_BOARD_GROUPS: PositionGroup[] = [
  "qb",
  "backfield",
  "pass_catcher",
];

export function uniqueBoardPlayers(board: LeaderboardJson): LeaderboardRow[] {
  const map = new Map<string, LeaderboardRow>();
  for (const rows of Object.values(board.stats)) {
    for (const row of rows) {
      if (!map.has(row.playerId)) map.set(row.playerId, row);
    }
  }
  return [...map.values()];
}

export function sortFantasyRankRows(
  rows: LeaderboardRow[],
  mode: SortMode,
): LeaderboardRow[] {
  const copy = [...rows];
  copy.sort((a, b) => {
    const aRank = a.fantasyPosRank;
    const bRank = b.fantasyPosRank;
    if (aRank == null || bRank == null) {
      return a.playerId.localeCompare(b.playerId);
    }
    const diff =
      mode === "best" ? aRank - bRank : bRank - aRank;
    if (diff !== 0) return diff;
    return a.playerId.localeCompare(b.playerId);
  });
  return copy;
}

export function sortLeaderboardRows(
  rows: LeaderboardRow[],
  mode: SortMode,
  higherIsBetter: boolean,
): LeaderboardRow[] {
  const copy = [...rows];
  copy.sort((a, b) => {
    const aNull = a.percentile == null;
    const bNull = b.percentile == null;
    if (aNull !== bNull) return aNull ? 1 : -1;
    if (a.percentile == null || b.percentile == null) {
      if (a.value == null || b.value == null) {
        if (a.value == null && b.value != null) return 1;
        if (a.value != null && b.value == null) return -1;
      } else {
        const direction = (higherIsBetter === (mode === "best")) ? -1 : 1;
        const diff = direction * (a.value - b.value);
        if (diff !== 0) return diff;
      }
      return a.playerId.localeCompare(b.playerId);
    }
    const diff =
      mode === "best"
        ? b.percentile - a.percentile
        : a.percentile - b.percentile;
    if (diff !== 0) return diff;
    return a.playerId.localeCompare(b.playerId);
  });
  return copy;
}

export function matchesQuery(row: LeaderboardRow, needle: string): boolean {
  return matchesSearch({ ...row, id: row.playerId }, needle);
}

/** playerId → published counting-stat value for volumeStatId join. */
export function volumeByPlayer(
  board: LeaderboardJson | null,
  volumeStatId: string | undefined,
): Map<string, number> | null {
  if (!board || !volumeStatId) return null;
  const rows = board.stats[volumeStatId];
  if (!rows?.length) return null;
  const map = new Map<string, number>();
  for (const row of rows) {
    if (row.value != null && Number.isFinite(row.value)) {
      map.set(row.playerId, row.value);
    }
  }
  return map.size > 0 ? map : null;
}

export function resolveVolume(
  row: LeaderboardRow,
  byPlayer: Map<string, number> | null,
): number | null {
  if (byPlayer) {
    const joined = byPlayer.get(row.playerId);
    if (joined != null) return joined;
  }
  return row.denomYtd ?? null;
}

export function boardHasResolvedVolume(
  rows: LeaderboardRow[],
  byPlayer: Map<string, number> | null,
): boolean {
  return rows.some((row) => resolveVolume(row, byPlayer) != null);
}

export type SeasonAffiliation = {
  team: string;
  position: string;
  fantasyPosRank?: number;
  fantasyPosRankKind?: FantasyPosRankKind;
};
export const EMPTY_AFFILIATION = new Map<string, SeasonAffiliation>();

/** Index bios are latest-only; season boards carry team/position/rank as-of that year. */
export function affiliationFromBoard(board: LeaderboardJson): Map<string, SeasonAffiliation> {
  const map = new Map<string, SeasonAffiliation>();
  for (const rows of Object.values(board.stats)) {
    for (const row of rows) {
      if (!map.has(row.playerId)) {
        map.set(row.playerId, {
          team: row.team,
          position: row.position,
          fantasyPosRank: row.fantasyPosRank,
          fantasyPosRankKind: row.fantasyPosRankKind,
        });
      }
    }
  }
  return map;
}

