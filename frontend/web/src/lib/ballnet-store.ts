import "server-only";

import { cache } from "react";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
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

function ballnetDataRoot(): string {
  if (process.env.BALLNET_DATA_DIR) {
    return path.resolve(process.env.BALLNET_DATA_DIR);
  }
  return path.resolve(process.cwd(), "../../ballnet/data");
}

function knowballBundledIndexDir(): string {
  return path.join(process.cwd(), "src/data/ballnet");
}

export type SeasonsEnvelope = {
  schemaVersion: 1;
  seasons: Array<{ season: number; asOfWeek: number }>;
};

export type CurrentEnvelope = {
  schemaVersion: 1;
  season: number;
  asOfWeek: number;
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
  positionGroup: string;
  /** Present on Stage H game-level files; absent on YTD league shapes. */
  scope?: "league_weekly";
  stats: Record<string, LeagueStatShape>;
};

async function tryReadLocalJson<T>(file: string): Promise<T | null> {
  try {
    const text = await readFile(file, "utf8");
    return JSON.parse(text) as T;
  } catch {
    return null;
  }
}

async function tryFetchRemoteJson<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(url, { next: { revalidate: 3600 } });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

async function loadIndexArtifact<T>(
  storagePath: string,
  localNames: string[],
): Promise<T | null> {
  const base = vizStorageBase();
  if (base) {
    const remote = await tryFetchRemoteJson<T>(`${base}/${storagePath}`);
    if (remote) return remote;
  }

  for (const name of localNames) {
    const ballnet = await tryReadLocalJson<T>(
      path.join(ballnetDataRoot(), "index", name),
    );
    if (ballnet) return ballnet;
    const bundled = await tryReadLocalJson<T>(
      path.join(knowballBundledIndexDir(), name),
    );
    if (bundled) return bundled;
  }

  return null;
}

export const loadSeasonsMeta = cache(async (): Promise<SeasonsEnvelope | null> =>
  loadIndexArtifact<SeasonsEnvelope>("index/seasons.json", ["seasons.json"]),
);

export const loadCurrentMeta = cache(async (): Promise<CurrentEnvelope | null> =>
  loadIndexArtifact<CurrentEnvelope>("index/current.json", ["current.json"]),
);

export const loadPlayersIndex = cache(async (): Promise<PlayersEnvelope | null> =>
  loadIndexArtifact<PlayersEnvelope>("index/players.json", ["players.json"]),
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
  const rel = `league/${season}/w${week}/${positionGroup}.json`;

  const base = vizStorageBase();
  if (base) {
    const remote = await tryFetchRemoteJson<LeagueGroupJson>(`${base}/${rel}`);
    if (remote) return remote;
  }

  return tryReadLocalJson<LeagueGroupJson>(path.join(ballnetDataRoot(), rel));
}

/** Stage H single-game KDEs (`dists/league_weekly/...`). Not `league_ytd`. */
export async function loadLeagueWeeklyGroupJson(
  positionGroup: PositionGroup | string,
  opts?: { season?: number; asOfWeek?: number },
): Promise<LeagueGroupJson | null> {
  const resolved = await resolveWeek(opts);
  if (!resolved) return null;
  const { season, week } = resolved;
  const rel = `dists/league_weekly/${season}/w${week}/${positionGroup}.json`;

  const base = vizStorageBase();
  if (base) {
    const remote = await tryFetchRemoteJson<LeagueGroupJson>(`${base}/${rel}`);
    if (remote) return remote;
  }

  return tryReadLocalJson<LeagueGroupJson>(path.join(ballnetDataRoot(), rel));
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
  if (base) {
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
  }

  // Local fallback (sibling ballnet/data) for seasons not yet on Storage.
  const root = ballnetDataRoot();
  const candidates: string[] = [];

  if (opts?.season != null && opts?.asOfWeek != null) {
    candidates.push(
      path.join(
        root,
        "pages",
        String(opts.season),
        `w${opts.asOfWeek}`,
        `${playerId}.json`,
      ),
    );
  } else if (opts?.season != null) {
    const known = await asOfWeekForSeason(opts.season);
    if (known != null) {
      candidates.push(
        path.join(
          root,
          "pages",
          String(opts.season),
          `w${known}`,
          `${playerId}.json`,
        ),
      );
    }
    for (const week of [18, 17]) {
      if (week === known) continue;
      candidates.push(
        path.join(
          root,
          "pages",
          String(opts.season),
          `w${week}`,
          `${playerId}.json`,
        ),
      );
    }
  }

  candidates.push(path.join(root, "pages", "current", `${playerId}.json`));

  for (const file of candidates) {
    const page = await tryReadLocalJson<PlayerPageJson>(file);
    if (!page) continue;
    if (opts?.season != null && page.season !== opts.season) continue;
    return page;
  }

  if (opts?.season != null) {
    const seasonDir = path.join(root, "pages", String(opts.season));
    try {
      const weeks = (await readdir(seasonDir, { withFileTypes: true }))
        .filter((d) => d.isDirectory() && /^w\d+$/.test(d.name))
        .map((d) => d.name)
        .sort()
        .reverse();
      for (const week of weeks) {
        const page = await tryReadLocalJson<PlayerPageJson>(
          path.join(seasonDir, week, `${playerId}.json`),
        );
        if (page && page.season === opts.season) return page;
      }
    } catch {
      // no season dir
    }
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
    const rel = `highlights/${season}/w${week}.json`;

    const base = vizStorageBase();
    if (base) {
      const remote = await tryFetchRemoteJson<HighlightsBoardJson>(`${base}/${rel}`);
      if (remote) return remote;
    }

    return tryReadLocalJson<HighlightsBoardJson>(
      path.join(ballnetDataRoot(), rel),
    );
  },
);

/** Search sort board (`leaderboards/{season}/w{week}/{group}.json`). */
export const loadLeaderboard = cache(
  async (
    positionGroup: PositionGroup | string,
    opts?: { season?: number; asOfWeek?: number },
  ): Promise<LeaderboardJson | null> => {
    let season = opts?.season;
    let asOfWeek = opts?.asOfWeek;
    if (season == null || asOfWeek == null) {
      const current = await resolveCurrentPointer();
      if (!current) return null;
      season = season ?? current.season;
      asOfWeek = asOfWeek ?? current.week;
    }
    const rel = `leaderboards/${season}/w${asOfWeek}/${positionGroup}.json`;

    const base = vizStorageBase();
    if (base) {
      const remote = await tryFetchRemoteJson<LeaderboardJson>(`${base}/${rel}`);
      if (remote) return remote;
    }

    return tryReadLocalJson<LeaderboardJson>(
      path.join(ballnetDataRoot(), rel),
    );
  },
);
