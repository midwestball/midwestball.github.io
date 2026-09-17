"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";
import { GROUP_LABEL, positionGroupOf, isPositionCode } from "@/lib/catalog";
import type { PlayerBio } from "@/lib/payload";
import { searchPlayers } from "@/lib/player-index";
import { TeamAbbr } from "@/components/TeamAbbr";
import { cn } from "@/lib/utils";

const MAX_PLAYERS = 4;

export type ComparePickerProps = {
  players: PlayerBio[];
  selectedIds: string[];
  season: number;
  seasons: number[];
};

function compareHref(ids: string[], season: number): string {
  const params = new URLSearchParams();
  if (ids.length > 0) params.set("p", ids.join(","));
  params.set("season", String(season));
  const qs = params.toString();
  return qs ? `/compare?${qs}` : "/compare";
}

export function ComparePicker({
  players,
  selectedIds,
  season,
  seasons,
}: ComparePickerProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");

  const selected = useMemo(() => {
    const byId = new Map(players.map((p) => [p.id, p]));
    return selectedIds
      .map((id) => byId.get(id))
      .filter((p): p is PlayerBio => Boolean(p));
  }, [players, selectedIds]);

  const lockedGroup = useMemo(() => {
    const first = selected[0];
    if (!first || !isPositionCode(first.position)) return null;
    return positionGroupOf(first.position);
  }, [selected]);

  const suggestions = useMemo(() => {
    if (!query.trim()) return [];
    const pool = lockedGroup
      ? players.filter(
          (p) =>
            isPositionCode(p.position) &&
            positionGroupOf(p.position) === lockedGroup,
        )
      : players;
    return searchPlayers(pool, query)
      .filter((p) => !selectedIds.includes(p.id))
      .filter((p) => p.seasons.includes(season))
      .slice(0, 8);
  }, [players, query, lockedGroup, selectedIds, season]);

  function pushIds(ids: string[], nextSeason = season) {
    router.push(compareHref(ids, nextSeason));
  }

  function addPlayer(id: string) {
    if (selectedIds.length >= MAX_PLAYERS) return;
    if (selectedIds.includes(id)) return;
    setQuery("");
    pushIds([...selectedIds, id]);
  }

  function removePlayer(id: string) {
    pushIds(selectedIds.filter((x) => x !== id));
  }

  const atCap = selectedIds.length >= MAX_PLAYERS;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2">
        <label className="min-w-[12rem] flex-1">
          <span className="mb-1 block text-xs font-semibold tracking-[0.15em] text-zinc-500 uppercase">
            Add player
          </span>
          <input
            type="search"
            value={query}
            disabled={atCap}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={
              atCap
                ? "Maximum 4 players"
                : lockedGroup
                  ? `Search ${GROUP_LABEL[lockedGroup]}…`
                  : "Search by name, position, or team…"
            }
            className="h-9 w-full rounded-none border border-zinc-200 bg-white px-2 text-sm text-zinc-900 outline-none placeholder:text-zinc-400 focus:border-zinc-400 disabled:bg-zinc-50 disabled:text-zinc-400"
          />
        </label>
        <label>
          <span className="mb-1 block text-xs font-semibold tracking-[0.15em] text-zinc-500 uppercase">
            Season
          </span>
          <select
            value={season}
            onChange={(e) => pushIds(selectedIds, Number(e.target.value))}
            className="h-9 rounded-none border border-zinc-200 bg-white px-2 text-sm text-zinc-900 outline-none focus:border-zinc-400"
          >
            {seasons.map((year) => (
              <option key={year} value={year}>
                {year}
              </option>
            ))}
          </select>
        </label>
      </div>

      {query.trim() && !atCap ? (
        <ul className="border border-zinc-200 bg-white">
          {suggestions.length === 0 ? (
            <li className="px-3 py-2 text-sm text-zinc-500">
              No matching players
              {lockedGroup ? ` in ${GROUP_LABEL[lockedGroup]}` : ""} for{" "}
              {season}.
            </li>
          ) : (
            suggestions.map((player) => (
              <li key={player.id}>
                <button
                  type="button"
                  onClick={() => addPlayer(player.id)}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-zinc-50"
                >
                  <span className="font-medium text-zinc-900">
                    {player.name}
                  </span>
                  <span className="flex items-center gap-x-1.5 text-zinc-500">
                    <span>{player.position}</span>
                    <span aria-hidden>·</span>
                    <TeamAbbr team={player.team} />
                  </span>
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}

      {selected.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {selected.map((player) => (
            <div
              key={player.id}
              className="flex items-center gap-2 border border-zinc-200 bg-white px-2 py-1 text-sm"
            >
              <span className="font-medium text-zinc-900">{player.name}</span>
              <span className="flex items-center gap-x-1.5 text-zinc-500">
                <span>{player.position}</span>
                <span aria-hidden>·</span>
                <TeamAbbr team={player.team} />
              </span>
              <button
                type="button"
                aria-label={`Remove ${player.name}`}
                onClick={() => removePlayer(player.id)}
                className={cn(
                  "ml-1 text-zinc-400 hover:text-zinc-900",
                )}
              >
                <X className="size-3.5" />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-zinc-500">
          Add up to {MAX_PLAYERS} players from the same position group.
        </p>
      )}
    </div>
  );
}
