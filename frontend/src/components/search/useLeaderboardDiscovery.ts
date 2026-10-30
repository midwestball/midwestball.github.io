"use client";

import { decodeSearch } from "@/lib/share-state/search";
import { useEffect, useMemo, useRef, useState } from "react";
import { BOARD_GROUPS, type SearchPositionFilter, boardGroupOf, matchesPositionFilter, type SortMode, type BoardStatus, type PublishedSeason, rampHoldMin, FANTASY_RANK_STAT_ID, uniqueBoardPlayers, sortFantasyRankRows, sortLeaderboardRows, matchesQuery, volumeByPlayer, resolveVolume, boardHasResolvedVolume, type SeasonAffiliation, EMPTY_AFFILIATION, affiliationFromBoard } from "@/lib/search/leaderboards";
import {
  STATS_BY_GROUP,
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

type PlayerSearchProps = {
  players: PlayerBio[];
  seasons: PublishedSeason[];
  initialSeason: number;
  url?: string;
  navigate?: (updates: Record<string, string | null>, replace?: boolean) => void;
};


export function useLeaderboardDiscovery({
  players,
  seasons,
  initialSeason, url, navigate,
}: PlayerSearchProps) {
  const [livePlayers, setLivePlayers] = useState(() => players.filter(player => !player.id.startsWith("demo-")));
  const [liveSeasons, setLiveSeasons] = useState(seasons);
  const [currentSeason, setCurrentSeason] = useState(initialSeason);
  const [localQuery, setLocalQuery] = useState("");
  const [localSeason, setLocalSeason] = useState(initialSeason);
  const seasonTouched = useRef(false);
  const [localGroup, setGroup] = useState<SearchPositionFilter | null>(null);
  const [localStatId, setStatId] = useState<string | null>(null);
  const [localSortMode, setLocalSortMode] = useState<SortMode>("best");
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
        if (!seasonTouched.current) setLocalSeason(current.season);
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

  const parsed = url === undefined ? null : decodeSearch(new URLSearchParams(url), seasonOptions.map(s => s.season), currentSeason);
  const season = parsed?.season ?? localSeason;
  const query = parsed?.query ?? localQuery;
  const group = parsed ? parsed.pos : localGroup;
  const statId = parsed ? parsed.statId : localStatId;
  const sortMode = parsed?.sort ?? localSortMode;
  function setSeason(value: number) { seasonTouched.current = true; setLocalSeason(value); navigate?.({ season: String(value), min: null }); }
  function setQuery(value: string) { setLocalQuery(value); navigate?.({ q: value }, true); }
  function setSortMode(value: SortMode) { setLocalSortMode(value); navigate?.({ sort: value === "best" ? null : value }); }
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
  const selectedVolume = parsed ? parsed.minVolume ?? floor : volumeChoice.key === volumeKey ? volumeChoice.value : floor;
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
    navigate?.({ min: String(clamped) }, true);
  }

  function commitVolumeDraft() {
    const parsed = volumeDraft.trim() === "" ? NaN : Number(volumeDraft.trim());
    if (!Number.isFinite(parsed)) {
      setVolumeChoice({key: volumeKey, value: minVolume, draft: String(minVolume ?? floor ?? 0)});
      return;
    }
    setVolume(parsed);
  }

  function onSelectGroup(next: SearchPositionFilter | "") {
    if (navigate) { navigate({ pos: next || null, stat: null, min: null, sort: null }); return; }
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
    if (navigate) { navigate({ stat: next || null, min: null, sort: null }); return; }
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

  return { query, setQuery, season, setSeason, seasonOptions, group, onSelectGroup, statId, onSelectStat, statEnabled, sortEnabled, boardGroup, statOptions, sortMode, setSortMode, volumeInteractive, volumeVisible, hasVolumeData, boardStatus, volumeMax, floor, volumeLabel, sliderMax, sliderValue, effectiveMin, setVolume, volumeDraft, setVolumeChoice, volumeKey, clampVolume, minVolume, commitVolumeDraft, showRanked, rankedRows, isFantasyRank, selectedStat, bioResults, asOfWeek, livePlayers };
}
