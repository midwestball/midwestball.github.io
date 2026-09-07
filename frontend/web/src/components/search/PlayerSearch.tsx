"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  GROUP_LABEL,
  STATS_BY_GROUP,
  formatStatValue,
  volumeStatFor,
  type PositionGroup,
  type StatDefinition,
} from "@/lib/catalog";
import type { LeaderboardJson, LeaderboardRow, PlayerBio } from "@/lib/payload";
import {
  filterPlayersByGroup,
  searchPlayers,
} from "@/lib/player-index";
import { fetchLeaderboard } from "@/app/search/actions";

/** Publishable groups only — returner has no Stage G spine. */
const FILTER_GROUPS: PositionGroup[] = [
  "qb",
  "backfield",
  "pass_catcher",
  "ol",
  "def_front",
  "secondary",
  "kicker",
  "punter",
];

type SortMode = "best" | "worst";
type BoardStatus = "idle" | "loading" | "ready" | "error";

type PublishedSeason = {
  season: number;
  asOfWeek: number;
};

type PlayerSearchProps = {
  players: PlayerBio[];
  seasons: PublishedSeason[];
  initialSeason: number;
};

/** Mirror Ballnet ramp–hold: min_n = n_base × min(w, 5). */
function rampHoldMin(stat: StatDefinition, asOfWeek: number): number | null {
  if (stat.minNBase == null) return null;
  const week = Number(asOfWeek);
  if (!Number.isFinite(week) || week < 1) return null;
  return stat.minNBase * Math.min(week, 5);
}

function sortLeaderboardRows(
  rows: LeaderboardRow[],
  mode: SortMode,
): LeaderboardRow[] {
  const copy = [...rows];
  copy.sort((a, b) => {
    const aNull = a.percentile == null;
    const bNull = b.percentile == null;
    if (aNull !== bNull) return aNull ? 1 : -1;
    if (a.percentile == null || b.percentile == null) {
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

function matchesQuery(row: LeaderboardRow, needle: string): boolean {
  if (!needle) return true;
  return (
    row.name.toLowerCase().includes(needle) ||
    row.position.toLowerCase().includes(needle) ||
    row.team.toLowerCase().includes(needle)
  );
}

/** playerId → published counting-stat value for volumeStatId join. */
function volumeByPlayer(
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

function resolveVolume(
  row: LeaderboardRow,
  byPlayer: Map<string, number> | null,
): number | null {
  if (byPlayer) {
    const joined = byPlayer.get(row.playerId);
    if (joined != null) return joined;
  }
  return row.denomYtd ?? null;
}

function boardHasResolvedVolume(
  rows: LeaderboardRow[],
  byPlayer: Map<string, number> | null,
): boolean {
  return rows.some((row) => resolveVolume(row, byPlayer) != null);
}

const controlBase =
  "h-9 border border-zinc-200 bg-white px-2 text-sm outline-none rounded-none";
const controlEnabled = `${controlBase} text-zinc-900 focus:border-zinc-400`;
const controlDisabled = `${controlBase} cursor-not-allowed border-zinc-100 bg-zinc-50 text-zinc-400`;

export function PlayerSearch({
  players,
  seasons,
  initialSeason,
}: PlayerSearchProps) {
  const [query, setQuery] = useState("");
  const [season, setSeason] = useState(initialSeason);
  const [group, setGroup] = useState<PositionGroup | null>(null);
  const [statId, setStatId] = useState<string | null>(null);
  const [sortMode, setSortMode] = useState<SortMode>("best");
  const [minVolume, setMinVolume] = useState<number | null>(null);
  const [volumeDraft, setVolumeDraft] = useState("");
  const [board, setBoard] = useState<LeaderboardJson | null>(null);
  const [boardStatus, setBoardStatus] = useState<BoardStatus>("idle");

  const seasonOptions = useMemo(() => {
    if (seasons.some((s) => s.season === initialSeason)) return seasons;
    return [{ season: initialSeason, asOfWeek: 18 }, ...seasons].sort(
      (a, b) => b.season - a.season,
    );
  }, [seasons, initialSeason]);

  const asOfWeek = useMemo(() => {
    return (
      seasonOptions.find((s) => s.season === season)?.asOfWeek ??
      seasonOptions[0]?.asOfWeek ??
      18
    );
  }, [seasonOptions, season]);

  const statEnabled = group != null;
  const sortEnabled = group != null && statId != null;

  const statOptions = useMemo(() => {
    if (!group) return [];
    return STATS_BY_GROUP[group].filter((s) => !s.alwaysUnavailable);
  }, [group]);

  const selectedStat = useMemo(
    () => statOptions.find((s) => s.id === statId) ?? null,
    [statOptions, statId],
  );

  const volumeSibling = useMemo(() => {
    if (!group || !selectedStat) return null;
    return volumeStatFor(selectedStat, group);
  }, [group, selectedStat]);

  const floor = useMemo(() => {
    if (!selectedStat) return null;
    return rampHoldMin(selectedStat, asOfWeek);
  }, [selectedStat, asOfWeek]);

  const volumeMap = useMemo(
    () => volumeByPlayer(board, selectedStat?.volumeStatId),
    [board, selectedStat?.volumeStatId],
  );

  const statRows = useMemo(() => {
    if (!statId || !board) return [];
    return board.stats[statId] ?? [];
  }, [board, statId]);

  const hasVolumeData = useMemo(
    () => boardHasResolvedVolume(statRows, volumeMap),
    [statRows, volumeMap],
  );

  const volumeMax = useMemo(() => {
    if (!hasVolumeData) return 0;
    let max = 0;
    for (const row of statRows) {
      const vol = resolveVolume(row, volumeMap);
      if (vol != null && vol > max) max = vol;
    }
    return max;
  }, [statRows, hasVolumeData, volumeMap]);

  /** Interactive when any resolved volume exists (range is 0…max). */
  const volumeInteractive =
    sortEnabled &&
    floor != null &&
    boardStatus === "ready" &&
    hasVolumeData &&
    volumeMax > 0;

  const volumeVisible = sortEnabled && floor != null;

  useEffect(() => {
    if (!group || !statId) {
      setBoard(null);
      setBoardStatus("idle");
      return;
    }
    let cancelled = false;
    setBoard(null);
    setBoardStatus("loading");
    void fetchLeaderboard(group, season, asOfWeek)
      .then((payload) => {
        if (cancelled) return;
        setBoard(payload);
        setBoardStatus(payload ? "ready" : "error");
      })
      .catch(() => {
        if (cancelled) return;
        setBoard(null);
        setBoardStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [group, statId, season, asOfWeek]);

  useEffect(() => {
    if (floor == null) {
      setMinVolume(null);
      setVolumeDraft("");
      return;
    }
    // Default to ramp–hold baseline; user may drag/type down to 0.
    setMinVolume(floor);
    setVolumeDraft(String(floor));
  }, [floor, statId]);

  // Board max can arrive after the default; never leave the value above the track.
  useEffect(() => {
    if (minVolume == null || volumeMax <= 0) return;
    if (minVolume > volumeMax) {
      setMinVolume(volumeMax);
      setVolumeDraft(String(volumeMax));
    }
  }, [volumeMax, minVolume]);

  function clampVolume(n: number): number {
    const max = Math.max(volumeMax, 0);
    if (max <= 0) return Math.max(Math.round(n), 0);
    return Math.min(Math.max(Math.round(n), 0), max);
  }

  function setVolume(next: number) {
    const clamped = clampVolume(next);
    setMinVolume(clamped);
    setVolumeDraft(String(clamped));
  }

  function commitVolumeDraft() {
    const parsed = Number(volumeDraft.trim());
    if (!Number.isFinite(parsed)) {
      setVolumeDraft(String(minVolume ?? floor ?? 0));
      return;
    }
    setVolume(parsed);
  }

  function onSelectGroup(next: PositionGroup | "") {
    if (!next) {
      setGroup(null);
      setStatId(null);
      setSortMode("best");
      return;
    }
    setGroup(next);
    setStatId(null);
    setSortMode("best");
  }

  function onSelectStat(next: string) {
    if (!next) {
      setStatId(null);
      setSortMode("best");
      return;
    }
    setStatId(next);
    setSortMode("best");
  }

  const needle = query.trim().toLowerCase();
  const effectiveMin = minVolume ?? floor ?? 0;

  const bioResults = useMemo(() => {
    const inSeason = players.filter((player) => player.seasons.includes(season));
    const scoped = group ? filterPlayersByGroup(inSeason, group) : inSeason;
    return searchPlayers(scoped, query);
  }, [players, group, query, season]);

  const rankedRows = useMemo(() => {
    if (!statId || !board) return null;
    const rows = board.stats[statId] ?? [];
    const useVolume = boardHasResolvedVolume(rows, volumeMap);
    const filtered = rows.filter((row) => {
      if (!matchesQuery(row, needle)) return false;
      if (useVolume) {
        const vol = resolveVolume(row, volumeMap);
        // Missing resolved volume → drop (same as missing denomYtd before).
        if (vol == null || vol < effectiveMin) return false;
        return true;
      }
      // NGS / missing-source boards: fall back to Ballnet ramp–hold flag.
      return row.qualified;
    });
    return sortLeaderboardRows(filtered, sortMode);
  }, [board, statId, needle, sortMode, effectiveMin, volumeMap]);

  const showRanked = Boolean(group && statId);
  const volumeLabel =
    volumeSibling?.label ?? selectedStat?.denom ?? "volume";
  const sliderMax = Math.max(volumeMax, 1);
  const sliderValue = Math.min(
    Math.max(effectiveMin, 0),
    sliderMax,
  );

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5">
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search players, positions, teams"
          className="h-9 min-w-0 flex-1 rounded-none border border-zinc-200 bg-white px-2 text-sm text-zinc-900 outline-none placeholder:text-zinc-400 focus:border-zinc-400"
        />
        <select
          value={season}
          onChange={(event) => setSeason(Number(event.target.value))}
          aria-label="Season"
          className={`${controlEnabled} shrink-0`}
        >
          {seasonOptions.map((row) => (
            <option key={row.season} value={row.season}>
              {row.season}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-wrap items-center gap-x-1.5 gap-y-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="shrink-0 text-xs font-semibold tracking-[0.15em] text-zinc-500 uppercase">
            Filter
          </span>
          <select
            value={group ?? ""}
            onChange={(event) =>
              onSelectGroup(event.target.value as PositionGroup | "")
            }
            aria-label="Position group"
            className={controlEnabled}
          >
            <option value="">Position</option>
            {FILTER_GROUPS.map((g) => (
              <option key={g} value={g}>
                {GROUP_LABEL[g]}
              </option>
            ))}
          </select>
          <select
            value={statId ?? ""}
            onChange={(event) => onSelectStat(event.target.value)}
            aria-label="Stat"
            disabled={!statEnabled}
            className={`min-w-0 max-w-[9rem] truncate ${statEnabled ? controlEnabled : controlDisabled}`}
          >
            <option value="">Stat</option>
            {statOptions.map((stat) => (
              <option key={stat.id} value={stat.id}>
                {stat.label}
              </option>
            ))}
          </select>
          <div className="flex shrink-0">
            <button
              type="button"
              disabled={!sortEnabled}
              onClick={() => setSortMode("best")}
              className={`h-9 border px-2 text-sm rounded-none ${
                !sortEnabled
                  ? "cursor-not-allowed border-zinc-100 bg-zinc-50 text-zinc-400"
                  : sortMode === "best"
                    ? "border-zinc-900 bg-zinc-900 text-white"
                    : "border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50"
              }`}
            >
              Best
            </button>
            <button
              type="button"
              disabled={!sortEnabled}
              onClick={() => setSortMode("worst")}
              className={`h-9 border border-l-0 px-2 text-sm rounded-none ${
                !sortEnabled
                  ? "cursor-not-allowed border-zinc-100 bg-zinc-50 text-zinc-400"
                  : sortMode === "worst"
                    ? "border-zinc-900 bg-zinc-900 text-white"
                    : "border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50"
              }`}
            >
              Worst
            </button>
          </div>
        </div>

        <div
          className={`flex min-w-0 grow basis-[12rem] items-center gap-1 ${
            volumeInteractive ? "" : "opacity-40"
          }`}
          title={
            !volumeVisible
              ? undefined
              : !hasVolumeData && boardStatus === "ready"
                ? "Volume not available for this stat"
                : volumeMax <= 0
                  ? "No volume data for this stat yet"
                  : `Min ${volumeLabel} (default ${floor}; 0–${Math.round(volumeMax)})`
          }
        >
          <label
            htmlFor="min-volume"
            className="shrink-0 text-xs text-zinc-500 whitespace-nowrap"
          >
            Min Volume
          </label>
          <input
            id="min-volume"
            type="range"
            min={0}
            max={sliderMax}
            step={1}
            value={volumeVisible ? sliderValue : 0}
            disabled={!volumeInteractive}
            onChange={(event) => setVolume(Number(event.target.value))}
            className="h-9 min-w-0 flex-1 cursor-pointer accent-zinc-900 disabled:cursor-not-allowed"
            aria-label={`Minimum ${volumeLabel}`}
          />
          <input
            type="number"
            inputMode="numeric"
            min={0}
            max={sliderMax}
            step={1}
            value={volumeVisible ? volumeDraft : ""}
            disabled={!volumeInteractive}
            onChange={(event) => {
              const raw = event.target.value;
              setVolumeDraft(raw);
              if (raw.trim() === "") return;
              const parsed = Number(raw);
              if (Number.isFinite(parsed)) {
                setMinVolume(clampVolume(parsed));
              }
            }}
            onBlur={commitVolumeDraft}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.currentTarget.blur();
              }
            }}
            className={`h-9 w-11 shrink-0 rounded-none border px-0.5 text-right text-sm tabular-nums outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none ${
              volumeInteractive
                ? "border-zinc-200 bg-white text-zinc-900 focus:border-zinc-400"
                : "cursor-not-allowed border-zinc-100 bg-zinc-50 text-zinc-400"
            }`}
            aria-label={`Minimum ${volumeLabel} value`}
          />
        </div>
      </div>

      {showRanked ? (
        boardStatus === "loading" ? (
          <p className="text-sm text-zinc-500">Loading rankings…</p>
        ) : boardStatus === "error" ? (
          <p className="text-sm text-zinc-500">
            Rankings not published for this slice yet.
          </p>
        ) : rankedRows && rankedRows.length > 0 ? (
          <ul className="space-y-1">
            {rankedRows.map((row) => (
              <li key={row.playerId}>
                <Link
                  href={`/players/${row.playerId}?season=${season}`}
                  className="flex items-center justify-between rounded-none border border-zinc-200 bg-white px-3 py-2 hover:bg-zinc-50"
                >
                  <div>
                    <p className="font-medium text-zinc-900">{row.name}</p>
                    <p className="text-sm text-zinc-500">
                      {row.position} · {row.team}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium text-zinc-900">
                      {row.value != null && selectedStat
                        ? formatStatValue(selectedStat.format, row.value)
                        : "—"}
                    </p>
                    <p className="text-xs text-zinc-400">
                      {row.percentile != null
                        ? `${Math.round(row.percentile)}%`
                        : "—"}
                    </p>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-zinc-500">
            {!hasVolumeData && boardStatus === "ready"
              ? "No volume data for this stat yet."
              : "No matching players."}
          </p>
        )
      ) : (
        <>
          <ul className="space-y-1">
            {bioResults.map((player) => (
              <li key={player.id}>
                <Link
                  href={`/players/${player.id}?season=${season}`}
                  className="flex items-center justify-between rounded-none border border-zinc-200 bg-white px-3 py-2 hover:bg-zinc-50"
                >
                  <div>
                    <p className="font-medium text-zinc-900">{player.name}</p>
                    <p className="text-sm text-zinc-500">
                      {player.position} · {player.team}
                    </p>
                  </div>
                  <span className="text-xs text-zinc-400">{season}</span>
                </Link>
              </li>
            ))}
          </ul>
          {bioResults.length === 0 ? (
            <p className="text-sm text-zinc-500">No matching players.</p>
          ) : null}
        </>
      )}
    </div>
  );
}
