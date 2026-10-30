"use client";
import { formatStatValue } from "@/lib/catalog";
import { TeamAbbr } from "@/components/TeamAbbr";
import { PositionRankLabel } from "@/components/PositionRankLabel";
import type { useLeaderboardDiscovery } from "./useLeaderboardDiscovery";
type SelectionProps = { onSelect: (id: string) => void; selectionReason: (id: string) => string | null };
function ResultRow({ id, name, onSelect, selectionReason, children }: SelectionProps & { id: string; name: string; children: React.ReactNode }) {
  const reason = selectionReason(id);
  return <li className="relative">
    <button type="button" aria-label={`Compare ${name}`} title={reason ?? `Compare ${name}`} disabled={!!reason}
      onClick={() => onSelect(id)} className="peer absolute inset-0 z-10 w-full cursor-pointer disabled:cursor-default" />
    <div className="pointer-events-none flex items-center justify-between gap-3 border border-border bg-card px-3 py-2 peer-hover:bg-muted">
      {children}
      {reason && <span className="text-xs text-muted-foreground">{reason}</span>}
    </div>
  </li>;
}
export function PlayerDiscoveryResults({ model, onSelect, selectionReason }: { model: ReturnType<typeof useLeaderboardDiscovery> } & SelectionProps) {
  const { season, hasVolumeData, boardStatus, showRanked, rankedRows, isFantasyRank, selectedStat, bioResults } = model;
  return <>      {showRanked ? (
        boardStatus === "loading" ? (
          <p role="status" className="min-h-24 text-sm text-muted-foreground">Loading rankings…</p>
        ) : boardStatus === "error" ? (
          <p role="status" className="min-h-24 text-sm text-muted-foreground">
            Rankings not published for this slice yet.
          </p>
        ) : rankedRows && rankedRows.length > 0 ? (
          <ul className="space-y-1">
            {rankedRows.map((row) => (
              <ResultRow key={row.playerId} id={row.playerId} name={row.name} onSelect={onSelect} selectionReason={selectionReason}>
                  <div>
                    <p className="font-medium text-foreground">{row.name}</p>
                    <p className="flex flex-wrap items-center gap-x-1.5 text-sm text-muted-foreground">
                      <span className="pointer-events-auto relative z-20"><PositionRankLabel
                        position={row.position}
                        rank={row.fantasyPosRank}
                        kind={row.fantasyPosRankKind}
                      /></span>
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
              </ResultRow>
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
              <ResultRow key={player.id} id={player.id} name={player.name} onSelect={onSelect} selectionReason={selectionReason}>
                  <div>
                    <p className="font-medium text-foreground">{player.name}</p>
                    <p className="flex flex-wrap items-center gap-x-1.5 text-sm text-muted-foreground">
                      <span className="pointer-events-auto relative z-20"><PositionRankLabel
                        position={player.position}
                        rank={player.fantasyPosRank}
                        kind={player.fantasyPosRankKind}
                      /></span>
                      <span aria-hidden>·</span>
                      <TeamAbbr team={player.team} />
                    </p>
                  </div>
                  <span className="text-xs text-muted-foreground">{season}</span>
              </ResultRow>
            ))}
          </ul>
          {bioResults.length === 0 ? (
            <p className="text-sm text-muted-foreground">No matching players.</p>
          ) : null}
        </>
      )}
</>;
}
