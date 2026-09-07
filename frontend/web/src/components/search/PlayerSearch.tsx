"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import Link from "next/link";
import {
  GROUP_LABEL,
  STATS_BY_GROUP,
  formatStatValue,
  type PositionGroup,
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

type PlayerSearchProps = {
  players: PlayerBio[];
  season: number;
  asOfWeek: number;
};

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

export function PlayerSearch({
  players,
  season,
  asOfWeek,
}: PlayerSearchProps) {
  const [query, setQuery] = useState("");
  const [filterOpen, setFilterOpen] = useState(false);
  const [group, setGroup] = useState<PositionGroup | null>(null);
  const [statId, setStatId] = useState<string | null>(null);
  const [sortMode, setSortMode] = useState<SortMode>("best");
  const [board, setBoard] = useState<LeaderboardJson | null>(null);
  const [boardError, setBoardError] = useState(false);
  const [pending, startTransition] = useTransition();

  const statOptions = useMemo(() => {
    if (!group) return [];
    return STATS_BY_GROUP[group].filter((s) => !s.alwaysUnavailable);
  }, [group]);

  const selectedStat = useMemo(
    () => statOptions.find((s) => s.id === statId) ?? null,
    [statOptions, statId],
  );

  useEffect(() => {
    if (!group || !statId) {
      setBoard(null);
      setBoardError(false);
      return;
    }
    let cancelled = false;
    startTransition(() => {
      void fetchLeaderboard(group, season, asOfWeek).then((payload) => {
        if (cancelled) return;
        setBoard(payload);
        setBoardError(!payload);
      });
    });
    return () => {
      cancelled = true;
    };
  }, [group, statId, season, asOfWeek]);

  function clearFilter() {
    setFilterOpen(false);
    setGroup(null);
    setStatId(null);
    setSortMode("best");
    setBoard(null);
    setBoardError(false);
  }

  function onToggleFilter() {
    if (filterOpen) {
      clearFilter();
      return;
    }
    setFilterOpen(true);
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

  const bioResults = useMemo(() => {
    const scoped = group ? filterPlayersByGroup(players, group) : players;
    return searchPlayers(scoped, query);
  }, [players, group, query]);

  const rankedRows = useMemo(() => {
    if (!statId || !board) return null;
    const rows = board.stats[statId] ?? [];
    const filtered = rows.filter((row) => matchesQuery(row, needle));
    return sortLeaderboardRows(filtered, sortMode);
  }, [board, statId, needle, sortMode]);

  const showRanked = Boolean(group && statId);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-stretch gap-0 border border-zinc-200 bg-white">
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search players, positions, teams"
          className="h-9 min-w-[12rem] flex-1 border-0 border-r border-zinc-200 bg-transparent px-2 text-sm text-zinc-900 outline-none placeholder:text-zinc-400 focus:bg-zinc-50"
        />
        <button
          type="button"
          onClick={onToggleFilter}
          aria-expanded={filterOpen}
          className={`h-9 shrink-0 border-0 px-3 text-sm ${
            filterOpen
              ? "bg-zinc-900 text-white"
              : "bg-white text-zinc-700 hover:bg-zinc-50"
          }`}
        >
          Filter
        </button>
        {filterOpen ? (
          <>
            <select
              value={group ?? ""}
              onChange={(event) =>
                onSelectGroup(event.target.value as PositionGroup | "")
              }
              aria-label="Position group"
              className="h-9 max-w-[11rem] border-0 border-l border-zinc-200 bg-white px-2 text-sm text-zinc-900 outline-none focus:bg-zinc-50"
            >
              <option value="">Position</option>
              {FILTER_GROUPS.map((g) => (
                <option key={g} value={g}>
                  {GROUP_LABEL[g]}
                </option>
              ))}
            </select>
            {group ? (
              <select
                value={statId ?? ""}
                onChange={(event) => onSelectStat(event.target.value)}
                aria-label="Stat"
                className="h-9 max-w-[14rem] border-0 border-l border-zinc-200 bg-white px-2 text-sm text-zinc-900 outline-none focus:bg-zinc-50"
              >
                <option value="">Stat</option>
                {statOptions.map((stat) => (
                  <option key={stat.id} value={stat.id}>
                    {stat.label}
                  </option>
                ))}
              </select>
            ) : null}
            {group && statId ? (
              <div className="flex h-9 border-l border-zinc-200">
                <button
                  type="button"
                  onClick={() => setSortMode("best")}
                  className={`h-9 px-3 text-sm ${
                    sortMode === "best"
                      ? "bg-zinc-900 text-white"
                      : "bg-white text-zinc-700 hover:bg-zinc-50"
                  }`}
                >
                  Best
                </button>
                <button
                  type="button"
                  onClick={() => setSortMode("worst")}
                  className={`h-9 border-l border-zinc-200 px-3 text-sm ${
                    sortMode === "worst"
                      ? "bg-zinc-900 text-white"
                      : "bg-white text-zinc-700 hover:bg-zinc-50"
                  }`}
                >
                  Worst
                </button>
              </div>
            ) : null}
          </>
        ) : null}
      </div>

      {showRanked ? (
        pending && !board ? (
          <p className="text-sm text-zinc-500">Loading rankings…</p>
        ) : boardError ? (
          <p className="text-sm text-zinc-500">
            Rankings not published for this slice yet.
          </p>
        ) : rankedRows && rankedRows.length > 0 ? (
          <ul className="space-y-1">
            {rankedRows.map((row) => (
              <li key={row.playerId}>
                <Link
                  href={`/players/${row.playerId}`}
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
          <p className="text-sm text-zinc-500">No matching players.</p>
        )
      ) : (
        <>
          <ul className="space-y-1">
            {bioResults.map((player) => (
              <li key={player.id}>
                <Link
                  href={`/players/${player.id}`}
                  className="flex items-center justify-between rounded-none border border-zinc-200 bg-white px-3 py-2 hover:bg-zinc-50"
                >
                  <div>
                    <p className="font-medium text-zinc-900">{player.name}</p>
                    <p className="text-sm text-zinc-500">
                      {player.position} · {player.team}
                    </p>
                  </div>
                  <span className="text-xs text-zinc-400">
                    {player.seasons[player.seasons.length - 1]}
                  </span>
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
