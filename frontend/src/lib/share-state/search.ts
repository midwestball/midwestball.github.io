import { STATS_BY_GROUP } from "@/lib/catalog";
import { boardGroupOf, FILTER_OPTIONS, FANTASY_RANK_BOARD_GROUPS, FANTASY_RANK_STAT_ID, type SearchPositionFilter } from "@/lib/search/leaderboards";
import { finiteParam, parseIdList } from "./common";
export type SearchState = { season: number; selectedIds: string[]; pos: SearchPositionFilter | null; statId: string | null; sort: "best" | "worst"; minVolume: number | null; query: string };
export function decodeSearch(params: URLSearchParams, seasons: number[], fallback: number): SearchState {
  const requested = Number(params.get("season"));
  const pos = FILTER_OPTIONS.find(p => p.id === params.get("pos"))?.id ?? null;
  const group = pos ? boardGroupOf(pos) : null;
  const stat = params.get("stat");
  const statId = group && (STATS_BY_GROUP[group].some(s => s.id === stat && !s.alwaysUnavailable) ||
    (stat === FANTASY_RANK_STAT_ID && FANTASY_RANK_BOARD_GROUPS.includes(group))) ? stat : null;
  const min = finiteParam(params.get("min"));
  return { season: seasons.includes(requested) ? requested : fallback, selectedIds: parseIdList(params.get("p")), pos, statId,
    sort: params.get("sort") === "worst" ? "worst" : "best", minVolume: statId && min !== null && min >= 0 ? min : null,
    query: (params.get("q") ?? "").slice(0, 200) };
}
export function encodeSearch(s: SearchState): Record<string, string | null> {
  return { season: String(s.season), p: s.selectedIds.join(","), pos: s.pos, stat: s.statId,
    sort: s.sort === "worst" ? "worst" : null, min: s.minVolume === null ? null : String(s.minVolume), q: s.query };
}
