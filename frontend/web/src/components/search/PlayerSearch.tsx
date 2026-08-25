"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { PlayerBio } from "@/lib/payload";
import { searchPlayers } from "@/lib/player-index";

type PlayerSearchProps = {
  players: PlayerBio[];
};

export function PlayerSearch({ players }: PlayerSearchProps) {
  const [query, setQuery] = useState("");
  const results = useMemo(
    () => searchPlayers(players, query),
    [players, query],
  );

  return (
    <div className="space-y-2">
      <input
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search players, positions, teams"
        className="h-9 w-full rounded-none border border-zinc-200 bg-white px-2 text-sm text-zinc-900 outline-none placeholder:text-zinc-400 focus:border-zinc-400"
      />
      <ul className="space-y-1">
        {results.map((player) => (
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
      {results.length === 0 ? (
        <p className="text-sm text-zinc-500">No matching players.</p>
      ) : null}
    </div>
  );
}
