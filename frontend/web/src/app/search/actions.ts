"use server";

import { loadLeaderboard } from "@/lib/ballnet-store";
import type { LeaderboardJson } from "@/lib/payload";
import type { PositionGroup } from "@/lib/catalog/types";

/** Client-callable load of one group leaderboard for search sort. */
export async function fetchLeaderboard(
  positionGroup: PositionGroup,
  season: number,
  asOfWeek: number,
): Promise<LeaderboardJson | null> {
  return loadLeaderboard(positionGroup, { season, asOfWeek });
}
