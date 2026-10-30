"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { BOARD_GROUPS, type SearchPositionFilter, FILTER_OPTIONS, boardGroupOf, matchesPositionFilter, type SortMode, type BoardStatus, type PublishedSeason, rampHoldMin, FANTASY_RANK_STAT_ID, FANTASY_RANK_BOARD_GROUPS, uniqueBoardPlayers, sortFantasyRankRows, sortLeaderboardRows, matchesQuery, volumeByPlayer, resolveVolume, boardHasResolvedVolume, type SeasonAffiliation, EMPTY_AFFILIATION, affiliationFromBoard } from "@/lib/search/leaderboards";
import {
  STATS_BY_GROUP,
  formatStatValue,
  volumeStatFor,
} from "@/lib/catalog";
import type { LeaderboardJson, PlayerBio } from "@/lib/payload";
import { searchPlayers } from "@/lib/player-index";
import {
  fetchCurrentMeta,
  fetchLeaderboard,
  fetchPlayersIndex,
  fetchSeasonsMeta,
} from "@/lib/ballnet-store";
import { TeamAbbr } from "@/components/TeamAbbr";
import { PositionRankLabel } from "@/components/PositionRankLabel";

type PlayerSearchProps = {
  players: PlayerBio[];
  seasons: PublishedSeason[];
  initialSeason: number;
};

const controlBase =
  "h-9 border border-zinc-200 bg-white px-2 text-sm outline-none rounded-none";
const controlEnabled = `${controlBase} text-zinc-900 focus:border-zinc-400`;
const controlDisabled = `${controlBase} cursor-not-allowed border-zinc-100 bg-zinc-50 text-zinc-400`;

export function PlayerSearch({
  players,
  seasons,
  initialSeason,
}: PlayerSearchProps) {
  const [livePlayers, setLivePlayers] = useState(() => players.filter(player => !player.id.startsWith("demo-")));
  const [liveSeasons, setLiveSeasons] = useState(seasons);
  const [currentSeason, setCurrentSeason] = useState(initialSeason);
  const [query, setQuery] = useState("");
  const [season, setSeason] = useState(initialSeason);
  const seasonTouched = useRef(false);
  const [group, setGroup] = useState<SearchPositionFilter | null>(null);
  const [statId, setStatId] = useState<string | null>(null);
  const [sortMode, setSortMode] = useState<SortMode>("best");
  const [volumeChoice, setVolumeChoice] = useState<{key: string; value: number | null; draft: string}>({key: "", value: null, draft: ""});
  const [boardResult, setBoardResult] = useState<{key: string; board: LeaderboardJson | null; status: BoardStatus}>({key: "", board: null, status: "idle"});
  const [affiliationResult, setAffiliationResult] = useState<{key: string; map: Map<string, SeasonAffiliation>}>({key: "", map: EMPTY_AFFILIATION});

  // Search is statically exported, but its roster and current slice change weekly.
  // Refresh both from Storage so a data upload does not require a site rebuild.
  useEffect(() => {
    let cancelled = false;
    void Promise.all([
      fetchPlayersIndex(),
      fetchSeasonsMeta(),
      fetchCurrentMeta(),
    ]).then(([playerIndex, seasonMeta, current]) => {
      if (cancelled) return;
      if (playerIndex) {
        setLivePlayers(playerIndex.players.filter(player => !player.id.startsWith("demo-")));
      }
      if (seasonMeta) {
        const nextSeasons = seasonMeta.seasons.map((row) => ({
          season: row.season,
          asOfWeek: row.asOfWeek,
          completedWeek: row.completedWeek ?? row.asOfWeek,
        }));
        if (current && !nextSeasons.some((row) => row.season === current.season)) {
          nextSeasons.push({
            season: current.season,
            asOfWeek: current.asOfWeek,
            completedWeek: current.completedWeek ?? current.asOfWeek,
          });
        }
        nextSeasons.sort((a, b) => b.season - a.season);
        setLiveSeasons(nextSeasons);
      }
      if (current) {
        setCurrentSeason(current.season);
        if (!seasonTouched.current) setSeason(current.season);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [players]);

  const seasonOptions = useMemo(() => {
    if (liveSeasons.some((s) => s.season === currentSeason)) return liveSeasons;
    return [
      { season: currentSeason, asOfWeek: 18, completedWeek: 18 },
      ...liveSeasons,
    ].sort((a, b) => b.season - a.season);
  }, [liveSeasons, currentSeason]);

  const asOfWeek = useMemo(() => {
    return (
      seasonOptions.find((s) => s.season === season)?.asOfWeek ??
      seasonOptions[0]?.asOfWeek ??
      18
    );
  }, [seasonOptions, season]);

  const completedWeek = useMemo(() => {
    const row = seasonOptions.find((s) => s.season === season);
    return row?.completedWeek ?? row?.asOfWeek ?? asOfWeek;
  }, [seasonOptions, season, asOfWeek]);

  const boardGroup = group ? boardGroupOf(group) : null;
  const boardKey = `${season}:${asOfWeek}:${boardGroup ?? ""}`;
  const board = statId && boardResult.key === boardKey ? boardResult.board : null;
  const boardStatus: BoardStatus = !boardGroup || !statId ? "idle" : boardResult.key === boardKey ? boardResult.status : "loading";
  const affiliationKey = `${season}:${asOfWeek}:${boardGroup ?? "all"}`;
  const seasonAffiliation = !statId && affiliationResult.key === affiliationKey ? affiliationResult.map : EMPTY_AFFILIATION;
  const statEnabled = group != null;
  const sortEnabled = group != null && statId != null;
  const isFantasyRank = statId === FANTASY_RANK_STAT_ID;

  const statOptions = useMemo(() => {
    if (!boardGroup) return [];
    return STATS_BY_GROUP[boardGroup].filter((s) => !s.alwaysUnavailable);
  }, [boardGroup]);

  const selectedStat = useMemo(
    () => (isFantasyRank ? null : statOptions.find((s) => s.id === statId) ?? null),
    [statOptions, statId, isFantasyRank],
  );

  const volumeSibling = useMemo(() => {
    if (!boardGroup || !selectedStat) return null;
    return volumeStatFor(selectedStat, boardGroup);
  }, [boardGroup, selectedStat]);

  const floor = useMemo(() => {
    if (!selectedStat) return null;
    const week = board?.completedWeek ?? completedWeek;
    return rampHoldMin(selectedStat, week);
  }, [selectedStat, board, completedWeek]);

  const volumeMap = useMemo(
    () => volumeByPlayer(board, selectedStat?.volumeStatId),
    [board, selectedStat?.volumeStatId],
  );

  const statRows = useMemo(() => {
    if (!statId || !board || isFantasyRank) return [];
    const rows = board.stats[statId] ?? [];
    if (!group) return rows;
    return rows.filter((row) => matchesPositionFilter(row.position, group));
  }, [board, statId, isFantasyRank, group]);

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
  const volumeKey = `${statId ?? ""}:${floor ?? ""}`;
  const selectedVolume = volumeChoice.key === volumeKey ? volumeChoice.value : floor;
  const minVolume = selectedVolume == null ? null : volumeMax > 0 ? Math.min(selectedVolume, volumeMax) : selectedVolume;
  const volumeDraft = volumeChoice.key === volumeKey && (selectedVolume == null || volumeMax <= 0 || selectedVolume <= volumeMax)
    ? volumeChoice.draft : minVolume == null ? "" : String(minVolume);

  /** Interactive when any resolved volume exists (range is 0…max). */
  const volumeInteractive =
    sortEnabled &&
    floor != null &&
    boardStatus === "ready" &&
    hasVolumeData &&
    volumeMax > 0;

  const volumeVisible = sortEnabled && floor != null;

  useEffect(() => {
    if (!boardGroup || !statId) {
      return;
    }
    if (boardResult.key === boardKey) return;
    let cancelled = false;
    void fetchLeaderboard(boardGroup, season, asOfWeek)
      .then((payload) => {
        if (cancelled) return;
        setBoardResult({key: boardKey, board: payload, status: payload ? "ready" : "error"});
      })
      .catch(() => {
        if (cancelled) return;
        setBoardResult({key: boardKey, board: null, status: "error"});
      });
    return () => {
      cancelled = true;
    };
  }, [boardGroup, statId, season, asOfWeek, boardKey, boardResult.key]);

  // Bio list has no ranked board; overlay team/position from season leaderboards.
  useEffect(() => {
    if (statId) {
      return;
    }
    let cancelled = false;
    const groups = boardGroup ? [boardGroup] : BOARD_GROUPS;
    void Promise.all(
      groups.map((g) => fetchLeaderboard(g, season, asOfWeek)),
    )
      .then((boards) => {
        if (cancelled) return;
        const map = new Map<string, SeasonAffiliation>();
        for (const payload of boards) {
          if (!payload) continue;
          for (const [id, aff] of affiliationFromBoard(payload)) {
            map.set(id, aff);
          }
        }
        setAffiliationResult({key: affiliationKey, map});
      })
      .catch(() => {
        if (cancelled) return;
        setAffiliationResult({key: affiliationKey, map: EMPTY_AFFILIATION});
      });
    return () => {
      cancelled = true;
    };
  }, [boardGroup, statId, season, asOfWeek, affiliationKey]);

  function clampVolume(n: number): number {
    const max = Math.max(volumeMax, 0);
    if (max <= 0) return Math.max(Math.round(n), 0);
    return Math.min(Math.max(Math.round(n), 0), max);
  }

  function setVolume(next: number) {
    const clamped = clampVolume(next);
    setVolumeChoice({key: volumeKey, value: clamped, draft: String(clamped)});
  }

  function commitVolumeDraft() {
    const parsed = Number(volumeDraft.trim());
    if (!Number.isFinite(parsed)) {
      setVolumeChoice({key: volumeKey, value: minVolume, draft: String(minVolume ?? floor ?? 0)});
      return;
    }
    setVolume(parsed);
  }

  function onSelectGroup(next: SearchPositionFilter | "") {
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
    const inSeason = livePlayers.filter((player) => player.seasons.includes(season));
    const forSeason = inSeason.map((player) => {
      const aff = seasonAffiliation.get(player.id);
      if (!aff) return player;
      return {
        ...player,
        team: aff.team,
        position: aff.position,
        fantasyPosRank: aff.fantasyPosRank,
        fantasyPosRankKind: aff.fantasyPosRankKind,
      };
    });
    const scoped = group
      ? forSeason.filter((player) => matchesPositionFilter(player.position, group))
      : forSeason;
    return searchPlayers(scoped, query);
  }, [livePlayers, group, query, season, seasonAffiliation]);

  const rankedRows = useMemo(() => {
    if (!statId || !board) return null;
    if (isFantasyRank) {
      const rows = uniqueBoardPlayers(board).filter((row) => {
        if (group && !matchesPositionFilter(row.position, group)) return false;
        if (!matchesQuery(row, needle)) return false;
        return row.fantasyPosRank != null && row.fantasyPosRank >= 1;
      });
      return sortFantasyRankRows(rows, sortMode);
    }
    const useVolume = boardHasResolvedVolume(statRows, volumeMap);
    const filtered = statRows.filter((row) => {
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
    return sortLeaderboardRows(filtered, sortMode, selectedStat?.higherIsBetter ?? true);
  }, [
    board,
    statId,
    isFantasyRank,
    group,
    needle,
    sortMode,
    effectiveMin,
    volumeMap,
    statRows,
    selectedStat,
  ]);

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
          onChange={(event) => { seasonTouched.current = true; setSeason(Number(event.target.value)); }}
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
              onSelectGroup(event.target.value as SearchPositionFilter | "")
            }
            aria-label="Position"
            className={controlEnabled}
          >
            <option value="">Position</option>
            {FILTER_OPTIONS.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.label}
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
            {boardGroup && FANTASY_RANK_BOARD_GROUPS.includes(boardGroup) ? (
              <option value={FANTASY_RANK_STAT_ID}>Fantasy Rank</option>
            ) : null}
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
              const parsed = Number(raw);
              setVolumeChoice({key: volumeKey, value: raw.trim() !== "" && Number.isFinite(parsed) ? clampVolume(parsed) : minVolume, draft: raw});
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
                  href={`/players/?id=${encodeURIComponent(row.playerId)}&season=${season}`}
                  className="flex items-center justify-between rounded-none border border-zinc-200 bg-white px-3 py-2 hover:bg-zinc-50"
                >
                  <div>
                    <p className="font-medium text-zinc-900">{row.name}</p>
                    <p className="flex flex-wrap items-center gap-x-1.5 text-sm text-zinc-500">
                      <PositionRankLabel
                        position={row.position}
                        rank={row.fantasyPosRank}
                        kind={row.fantasyPosRankKind}
                      />
                      <span aria-hidden>·</span>
                      <TeamAbbr team={row.team} />
                    </p>
                  </div>
                  <div className="text-right">
                    {isFantasyRank ? (
                      <>
                        <p className="text-sm font-medium tabular-nums text-zinc-900">
                          {row.fantasyPosRank ?? "—"}
                        </p>
                        <p className="text-xs text-zinc-400">
                          {row.fantasyPosRankKind === "finish"
                            ? "PPR finish"
                            : row.fantasyPosRankKind === "consensus"
                              ? "consensus"
                              : "—"}
                        </p>
                      </>
                    ) : (
                      <>
                        <p className="text-sm font-medium text-zinc-900">
                          {row.value != null && selectedStat
                            ? formatStatValue(selectedStat.format, row.value)
                            : "—"}
                        </p>
                        <p className="text-xs text-zinc-400">
                          {row.percentile != null
                            ? `${Math.round(row.percentile)}%`
                            : row.value != null ? "Unqualified · raw value" : "—"}
                        </p>
                      </>
                    )}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-zinc-500">
            {!isFantasyRank && !hasVolumeData && boardStatus === "ready"
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
                  href={`/players/?id=${encodeURIComponent(player.id)}&season=${season}`}
                  className="flex items-center justify-between rounded-none border border-zinc-200 bg-white px-3 py-2 hover:bg-zinc-50"
                >
                  <div>
                    <p className="font-medium text-zinc-900">{player.name}</p>
                    <p className="flex flex-wrap items-center gap-x-1.5 text-sm text-zinc-500">
                      <PositionRankLabel
                        position={player.position}
                        rank={player.fantasyPosRank}
                        kind={player.fantasyPosRankKind}
                      />
                      <span aria-hidden>·</span>
                      <TeamAbbr team={player.team} />
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
