import { cache } from "react";
import type {
  JsonStatSnapshot,
  PlayerBio,
  PlayerPageJson,
  HighlightsBoardJson,
  LeaderboardJson,
} from "@/lib/payload";
import type { Point } from "@/lib/distribution";
import type { PositionGroup } from "@/lib/catalog/types";
import { vizStorageBase } from "@/lib/viz-config";

export type SeasonsEnvelope = {
  schemaVersion: 1;
  seasons: Array<{ season: number; asOfWeek: number; completedWeek?: number }>;
};

export type CurrentEnvelope = {
  schemaVersion: 1;
  season: number;
  asOfWeek: number;
  completedWeek?: number;
};

export type PlayersEnvelope = {
  schemaVersion: 1;
  players: PlayerBio[];
};

/** Shared league shapes for one (season, week, position group). */
export type LeagueStatShape = {
  kind: "continuous" | "discrete";
  xMin: number;
  xMax: number;
  yMax: number;
  lowerBound?: number;
  upperBound?: number;
  curve?: Point[];
};

export type LeagueGroupJson = {
  schemaVersion: 1;
  season: number;
  asOfWeek: number;
  completedWeek?: number;
  positionGroup: string;
  /** Present on Stage H game-level files; absent on YTD league shapes. */
  scope?: "league_weekly" | "league_game_all_time";
  stats: Record<string, LeagueStatShape>;
};

async function tryFetchRemoteJson<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

async function loadStorageJson<T>(rel: string): Promise<T | null> {
  const base = vizStorageBase();
  if (!base) return null;
  return tryFetchRemoteJson<T>(`${base}/${rel}`);
}

export const loadSeasonsMeta = cache(async (): Promise<SeasonsEnvelope | null> =>
  loadStorageJson<SeasonsEnvelope>("index/seasons.json"),
);

export const loadCurrentMeta = cache(async (): Promise<CurrentEnvelope | null> =>
  loadStorageJson<CurrentEnvelope>("index/current.json"),
);

export const loadPlayersIndex = cache(async (): Promise<PlayersEnvelope | null> =>
  loadStorageJson<PlayersEnvelope>("index/players.json"),
);

/** Final published as-of week for a season, if Ballnet has published it. */
export async function asOfWeekForSeason(
  season: number,
): Promise<number | undefined> {
  const meta = await loadSeasonsMeta();
  return meta?.seasons.find((s) => s.season === season)?.asOfWeek;
}

async function resolveCurrentPointer(): Promise<{
  season: number;
  week: number;
} | null> {
  const current = await loadCurrentMeta();
  if (!current) return null;
  return { season: current.season, week: current.asOfWeek };
}

async function resolveWeek(
  opts?: { season?: number; asOfWeek?: number },
): Promise<{ season: number; week: number } | null> {
  if (opts?.season != null && opts?.asOfWeek != null) {
    return { season: opts.season, week: opts.asOfWeek };
  }
  if (opts?.season != null) {
    const known = await asOfWeekForSeason(opts.season);
    if (known != null) return { season: opts.season, week: known };
    return null;
  }
  return resolveCurrentPointer();
}

export async function loadLeagueGroupJson(
  positionGroup: PositionGroup | string,
  opts?: { season?: number; asOfWeek?: number },
): Promise<LeagueGroupJson | null> {
  const resolved = await resolveWeek(opts);
  if (!resolved) return null;
  const { season, week } = resolved;
  return loadStorageJson<LeagueGroupJson>(
    `league/${season}/w${week}/${positionGroup}.json`,
  );
}

/** Stage H single-game KDEs (`dists/league_weekly/...`). Not `league_ytd`. */
export async function loadLeagueWeeklyGroupJson(
  positionGroup: PositionGroup | string,
  opts?: { season?: number; asOfWeek?: number },
): Promise<LeagueGroupJson | null> {
  const resolved = await resolveWeek(opts);
  if (!resolved) return null;
  const { season, week } = resolved;
  return loadStorageJson<LeagueGroupJson>(
    `dists/league_weekly/${season}/w${week}/${positionGroup}.json`,
  );
}

/**
 * Merge player scalar snapshots with shared league shapes.
 * Embedded curve on the page (legacy) still wins when present.
 */
export function mergeLeagueIntoSnapshots(
  snapshots: JsonStatSnapshot[],
  league: LeagueGroupJson | null,
): JsonStatSnapshot[] {
  if (!league) return snapshots;
  return snapshots.map((snap) => {
    const shape = league.stats[snap.id];
    if (!shape) return snap;
    const hasEmbedded = Boolean(snap.curve?.length);
    if (hasEmbedded) return snap;
    return {
      ...snap,
      kind: shape.kind,
      xMin: shape.xMin,
      xMax: shape.xMax,
      yMax: shape.yMax,
      curve: shape.curve ?? [],
      ...(shape.lowerBound != null ? { lowerBound: shape.lowerBound } : {}),
      ...(shape.upperBound != null ? { upperBound: shape.upperBound } : {}),
    };
  });
}

export async function loadPlayerPageJson(
  playerId: string,
  opts?: { season?: number; asOfWeek?: number },
): Promise<PlayerPageJson | null> {
  const current = await resolveCurrentPointer();
  const base = vizStorageBase();
  if (!base) return null;

  let week = opts?.asOfWeek;
  if (opts?.season != null && week == null) {
    week = await asOfWeekForSeason(opts.season);
  }
  const urls: string[] = [];
  if (opts?.season != null && week != null) {
    urls.push(`${base}/pages/${opts.season}/w${week}/${playerId}.json`);
  } else if (opts?.season == null && current) {
    urls.push(
      `${base}/pages/${current.season}/w${current.week}/${playerId}.json`,
    );
  }
  urls.push(`${base}/pages/current/${playerId}.json`);

  for (const url of urls) {
    const page = await tryFetchRemoteJson<PlayerPageJson>(url);
    if (!page) continue;
    if (opts?.season != null && page.season !== opts.season) continue;
    return page;
  }
  return null;
}

/** Player page scalars + league curves for the player's position group. */
export async function loadHydratedPlayerSnapshots(
  playerId: string,
  positionGroup: PositionGroup | string,
  opts?: { season?: number; asOfWeek?: number },
): Promise<{ page: PlayerPageJson | null; snapshots: JsonStatSnapshot[] }> {
  const page = await loadPlayerPageJson(playerId, opts);
  if (!page) return { page: null, snapshots: [] };

  const leagueOpts = {
    season: page.season,
    asOfWeek: page.asOfWeek,
  };
  const league = await loadLeagueGroupJson(positionGroup, leagueOpts);
  return {
    page,
    snapshots: mergeLeagueIntoSnapshots(page.stats ?? [], league),
  };
}

/** Weekly highlight board (`highlights/{season}/w{week}.json`). */
export const loadHighlightsBoard = cache(
  async (opts?: {
    season?: number;
    week?: number;
  }): Promise<HighlightsBoardJson | null> => {
    let season = opts?.season;
    let week = opts?.week;
    if (season == null || week == null) {
      const current = await resolveCurrentPointer();
      if (!current) return null;
      season = season ?? current.season;
      week = week ?? current.week;
    }
    return loadStorageJson<HighlightsBoardJson>(
      `highlights/${season}/w${week}.json`,
    );
  },
);

/** Search sort board (`leaderboards/{season}/w{week}/{group}.json`). */
export async function loadLeaderboard(
  positionGroup: PositionGroup | string,
  opts?: { season?: number; asOfWeek?: number },
): Promise<LeaderboardJson | null> {
  let season = opts?.season;
  let asOfWeek = opts?.asOfWeek;
  if (season == null || asOfWeek == null) {
    const current = await resolveCurrentPointer();
    if (!current) return null;
    season = season ?? current.season;
    asOfWeek = asOfWeek ?? current.week;
  }
  return loadStorageJson<LeaderboardJson>(
    `leaderboards/${season}/w${asOfWeek}/${positionGroup}.json`,
  );
}

/** Client-callable alias used by Search (no Server Actions on static export). */
export async function fetchLeaderboard(
  positionGroup: PositionGroup,
  season: number,
  asOfWeek: number,
): Promise<LeaderboardJson | null> {
  return loadLeaderboard(positionGroup, { season, asOfWeek });
}

/** Client fetch for home week/year picker. */
export async function fetchHighlightsBoard(
  season: number,
  week: number,
): Promise<HighlightsBoardJson | null> {
  return loadHighlightsBoard({ season, week });
}

/** Client fetch for Stage H expand curves. */
export async function fetchLeagueWeeklyGroup(
  positionGroup: PositionGroup | string,
  season: number,
  week: number,
): Promise<LeagueGroupJson | null> {
  return loadLeagueWeeklyGroupJson(positionGroup, {
    season,
    asOfWeek: week,
  });
}
