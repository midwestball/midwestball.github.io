import type { Point, StatAvailabilityStatus } from "@/lib/distribution";

/**
 * Per-player scalar overlay. League `curve` (and usually domain fields)
 * come from `league/{season}/w{week}/{group}.json` and are merged at load time.
 */
export type JsonStatSnapshot = {
  id: string;
  playerValue: number | null;
  percentile: number | null;
  qualified: boolean;
  denomYtd?: number;
  kind: "continuous" | "discrete";
  xMin?: number;
  xMax?: number;
  yMax?: number;
  lowerBound?: number;
  upperBound?: number;
  curve?: Point[];
  unavailableReason?: Exclude<StatAvailabilityStatus, "ready" | "pending">;
};

export type FantasyPosRankKind = "consensus" | "finish";

export type PlayerBio = {
  id: string;
  name: string;
  position: string;
  team: string;
  seasons: number[];
  /** Season-scoped; omitted on `index/players.json` (latest-only bios). */
  fantasyPosRank?: number;
  fantasyPosRankKind?: FantasyPosRankKind;
};

export type PlayerPageJson = {
  schemaVersion?: 1;
  player: PlayerBio;
  season: number;
  asOfWeek: number;
  /** Last fully scored REG week used for ramp–hold. Falls back to asOfWeek. */
  completedWeek?: number;
  stats: JsonStatSnapshot[];
};

/** One row on a Stage H weekly board (ballnet `highlights/{season}/w{week}.json`). */
export type HighlightRow = {
  playerId: string;
  name: string;
  position: string;
  team: string;
  opponent: string;
  positionGroup: string;
  statId: string;
  statLabel: string;
  value: number;
  zScore: number;
  peerN: number;
  oneInN: number | null;
  rank: number;
  fantasyPosRank?: number;
  fantasyPosRankKind?: FantasyPosRankKind;
};

export type HighlightsBoardJson = {
  schemaVersion: 1;
  season: number;
  week: number;
  generatedAt?: string;
  top: HighlightRow[];
  byGroup: Record<string, HighlightRow[]>;
};

/** One row on a search leaderboard (`leaderboards/{season}/w{week}/{group}.json`). */
export type LeaderboardRow = {
  playerId: string;
  name: string;
  position: string;
  team: string;
  value: number | null;
  /** Oriented inclusive CDF — 100 is the good end for every catalog stat. */
  percentile: number | null;
  /** Season-to-date denominator used in ramp–hold (attempts, targets, …). */
  denomYtd: number | null;
  qualified: boolean;
  fantasyPosRank?: number;
  fantasyPosRankKind?: FantasyPosRankKind;
};

export type LeaderboardJson = {
  schemaVersion: 1;
  season: number;
  asOfWeek: number;
  /** Last fully scored REG week used for ramp–hold. Falls back to asOfWeek. */
  completedWeek?: number;
  positionGroup: string;
  stats: Record<string, LeaderboardRow[]>;
};
