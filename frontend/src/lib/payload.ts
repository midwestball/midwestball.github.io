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
  minN?: number;
  kind: "continuous" | "discrete";
  xMin?: number;
  xMax?: number;
  yMax?: number;
  lowerBound?: number;
  upperBound?: number;
  curve?: Point[];
  bins?: Array<{ lower: number; upper: number; count: number }>;
  valueCounts?: Array<{ value: number; count: number }>;
  nSample?: number;
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
  schemaVersion?: 1 | 2;
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
  favorableCount?: number;
  rarityScore?: number;
  rarityMethod?: string;
  oneInN: number | null;
  /** Geometric snap of oneInN onto 10^k (10, 100, 1000, …). */
  rarityTier?: number | null;
  rank: number;
  fantasyPosRank?: number;
  fantasyPosRankKind?: FantasyPosRankKind;
  /** Same-player secondary performances this week (omit on nested rows). */
  also?: HighlightRow[];
};

export type HighlightsBoardJson = {
  schemaVersion: 1 | 2;
  season: number;
  week: number;
  generatedAt?: string;
  top: HighlightRow[];
  byGroup: Record<string, HighlightRow[]>;
};

export type PlayMetricMode = "raw" | "epa";

/** One row on a play-level rarity board (`highlights/plays/{season}/w{week}.json`). */
export type PlayHighlightRow = {
  playerId: string;
  name: string;
  position: string;
  positionGroup: string;
  team: string;
  opponent: string;
  playClass: string;
  statId: string;
  statLabel: string;
  value: number;
  gameId?: string;
  playId?: number | null;
  quarter?: number | null;
  /** Game clock at snap, e.g. "14:56". */
  clock?: string | null;
  /** Display form, e.g. "Q1 14:56". */
  gameClock?: string | null;
  gameSecondsRemaining?: number | null;
  touchdown?: boolean;
  description?: string | null;
  zScore: number;
  peerN: number;
  peerKey?: string;
  /** Present on `completion` cards — the other actor's peer bucket. */
  secondaryPeerKey?: string;
  secondaryRole?: "pass" | "reception" | string;
  secondaryFavorableCount?: number;
  secondaryPeerN?: number;
  secondaryOneInN?: number;
  secondaryRarityTier?: number | null;
  secondaryRarityScore?: number;
  passerId?: string;
  passerName?: string;
  passerPosition?: string;
  receiverId?: string;
  receiverName?: string;
  receiverPosition?: string;
  favorableCount?: number;
  rarityScore?: number;
  rarityMethod?: string;
  oneInN: number | null;
  rarityTier?: number | null;
  rank: number;
  metricMode?: PlayMetricMode;
  /** Raw yards/etc. when the board is ranked on EPA. */
  rawValue?: number | null;
  also?: PlayHighlightRow[];
};

export type PlayHighlightsBoardJson = {
  schemaVersion: 1;
  season: number;
  week: number;
  generatedAt?: string;
  scope?: "play_all_time";
  metricMode?: PlayMetricMode;
  peerWindowStartYear?: number;
  missingPeerSeasons?: number[];
  top: PlayHighlightRow[];
  byClass: Record<string, PlayHighlightRow[]>;
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
  schemaVersion: 1 | 2;
  season: number;
  asOfWeek: number;
  /** Last fully scored REG week used for ramp–hold. Falls back to asOfWeek. */
  completedWeek?: number;
  positionGroup: string;
  stats: Record<string, LeaderboardRow[]>;
};
