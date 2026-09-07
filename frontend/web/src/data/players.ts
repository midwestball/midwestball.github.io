import "server-only";

import { cache } from "react";
import type { PlayerBio } from "@/lib/payload";
import { DEMO_PLAYERS } from "@/lib/player-index";
import {
  loadCurrentMeta,
  loadPlayersIndex,
  loadSeasonsMeta,
} from "@/lib/ballnet-store";

/** Ballnet `index/players.json` from Storage (+ lab demos). Cached per request. */
export const loadPlayerIndex = cache(async (): Promise<PlayerBio[]> => {
  const envelope = await loadPlayersIndex();
  return [...(envelope?.players ?? []), ...DEMO_PLAYERS];
});

/** Latest published viz season (from Ballnet `index/current.json`). */
export const loadCurrentSeasonContext = cache(async (): Promise<{
  season: number;
  asOfWeek: number;
}> => {
  const current = await loadCurrentMeta();
  if (current) {
    return { season: current.season, asOfWeek: current.asOfWeek };
  }
  return { season: 2025, asOfWeek: 18 };
});

/** Published seasons for search year filter (newest first). */
export const loadPublishedSeasons = cache(async (): Promise<
  Array<{ season: number; asOfWeek: number }>
> => {
  const [meta, current] = await Promise.all([
    loadSeasonsMeta(),
    loadCurrentSeasonContext(),
  ]);
  const bySeason = new Map<number, number>();
  for (const row of meta?.seasons ?? []) {
    bySeason.set(row.season, row.asOfWeek);
  }
  bySeason.set(current.season, current.asOfWeek);
  return [...bySeason.entries()]
    .map(([season, asOfWeek]) => ({ season, asOfWeek }))
    .sort((a, b) => b.season - a.season);
});

export async function getPlayer(id: string): Promise<PlayerBio | undefined> {
  const index = await loadPlayerIndex();
  return index.find((player) => player.id === id);
}

export { DEMO_PLAYERS as DEMO_PLAYER_INDEX } from "@/lib/player-index";
