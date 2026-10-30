"use client";
import Link from "next/link";
import { formatStatValue } from "@/lib/catalog";
import { TeamAbbr } from "@/components/TeamAbbr";
import { PositionRankLabel } from "@/components/PositionRankLabel";
import type { useLeaderboardDiscovery } from "./useLeaderboardDiscovery";
export function PlayerDiscoveryResults({ model, addAction }: { model: ReturnType<typeof useLeaderboardDiscovery>; addAction?: (id: string, name: string) => React.ReactNode }) {
  const { season, hasVolumeData, boardStatus, showRanked, rankedRows, isFantasyRank, selectedStat, bioResults } = model;
  return <>      {showRanked ? (
        boardStatus === "loading" ? (
          <p className="text-sm text-muted-foreground">Loading rankings…</p>
        ) : boardStatus === "error" ? (
          <p className="text-sm text-muted-foreground">
            Rankings not published for this slice yet.
          </p>
        ) : rankedRows && rankedRows.length > 0 ? (
          <ul className="space-y-1">
            {rankedRows.map((row) => (
              <li key={row.playerId} className="flex items-stretch gap-1">
                <Link
                  href={`/players/?id=${encodeURIComponent(row.playerId)}&season=${season}`}
                  className="min-w-0 flex-1 flex items-center justify-between rounded-none border border-border bg-card px-3 py-2 hover:bg-muted"
                >
                  <div>
                    <p className="font-medium text-foreground">{row.name}</p>
                    <p className="flex flex-wrap items-center gap-x-1.5 text-sm text-muted-foreground">
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
                        <p className="text-sm font-medium tabular-nums text-foreground">
                          {row.fantasyPosRank ?? "—"}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {row.fantasyPosRankKind === "finish"
                            ? "PPR finish"
                            : row.fantasyPosRankKind === "consensus"
                              ? "consensus"
                              : "—"}
                        </p>
                      </>
                    ) : (
                      <>
                        <p className="text-sm font-medium text-foreground">
                          {row.value != null && selectedStat
                            ? formatStatValue(selectedStat.format, row.value)
                            : "—"}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {row.percentile != null
                            ? `${Math.round(row.percentile)}%`
                            : row.value != null ? "Unqualified · raw value" : "—"}
                        </p>
                      </>
                    )}
                  </div>
                </Link>
                {addAction?.(row.playerId, row.name)}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">
            {!isFantasyRank && !hasVolumeData && boardStatus === "ready"
              ? "No volume data for this stat yet."
              : "No matching players."}
          </p>
        )
      ) : (
        <>
          <ul className="space-y-1">
            {bioResults.map((player) => (
              <li key={player.id} className="flex items-stretch gap-1">
                <Link
                  href={`/players/?id=${encodeURIComponent(player.id)}&season=${season}`}
                  className="min-w-0 flex-1 flex items-center justify-between rounded-none border border-border bg-card px-3 py-2 hover:bg-muted"
                >
                  <div>
                    <p className="font-medium text-foreground">{player.name}</p>
                    <p className="flex flex-wrap items-center gap-x-1.5 text-sm text-muted-foreground">
                      <PositionRankLabel
                        position={player.position}
                        rank={player.fantasyPosRank}
                        kind={player.fantasyPosRankKind}
                      />
                      <span aria-hidden>·</span>
                      <TeamAbbr team={player.team} />
                    </p>
                  </div>
                  <span className="text-xs text-muted-foreground">{season}</span>
                </Link>
                {addAction?.(player.id, player.name)}
              </li>
            ))}
          </ul>
          {bioResults.length === 0 ? (
            <p className="text-sm text-muted-foreground">No matching players.</p>
          ) : null}
        </>
      )}
</>;
}
