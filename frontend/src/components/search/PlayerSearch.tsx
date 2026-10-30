"use client";
import { useLeaderboardDiscovery } from "./useLeaderboardDiscovery";
import { PlayerLeaderboardFilters } from "./PlayerLeaderboardFilters";
import { PlayerDiscoveryResults } from "./PlayerDiscoveryResults";
export function PlayerSearch(props: Parameters<typeof useLeaderboardDiscovery>[0]) {
  const model = useLeaderboardDiscovery(props);
  return <div className="space-y-2"><PlayerLeaderboardFilters model={model} /><PlayerDiscoveryResults model={model} /></div>;
}
