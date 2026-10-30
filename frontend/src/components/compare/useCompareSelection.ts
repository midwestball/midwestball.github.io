"use client";
import { useEffect, useMemo, useState } from "react";
import { isPositionCode, positionGroupOf, type PositionGroup } from "@/lib/catalog";
import { hydratePlayerStats } from "@/lib/catalog/hydrate";
import { loadHydratedPlayerSnapshots } from "@/lib/ballnet-store";
import type { PlayerBio } from "@/lib/payload";
import type { CompareColumn } from "./CompareBoard";
export function useCompareSelection(players: PlayerBio[], selectedIds: string[], season: number) {
  const selectedBios = useMemo(
    () =>
      selectedIds
        .map((id) => players.find((player) => player.id === id))
        .filter((player): player is PlayerBio => Boolean(player)),
    [selectedIds, players],
  );

  const groups = new Set(
    selectedBios
      .filter((player) => isPositionCode(player.position))
      .map((player) => positionGroupOf(player.position)),
  );
  const sameGroup = groups.size <= 1;
  const positionGroup = sameGroup
    ? ([...groups][0] as PositionGroup | undefined)
    : undefined;

  const [columns, setColumns] = useState<CompareColumn[]>([]);
  const [loadedKey, setLoadedKey] = useState("");
  const requestKey = `${season}:${positionGroup ?? ""}:${selectedBios.map(b => `${b.id}:${b.position}`).join(",")}`;
  const loading = sameGroup && Boolean(positionGroup) && selectedBios.length > 0 && loadedKey !== requestKey;
  const displayedColumns = loadedKey === requestKey && selectedBios.length > 0 ? columns : [];

  useEffect(() => {
    if (!sameGroup || !positionGroup || selectedIds.length === 0) {
      return;
    }
    const bios = selectedIds
      .map((id) => players.find((player) => player.id === id))
      .filter((player): player is PlayerBio => Boolean(player));
    if (bios.length === 0) {
      return;
    }
    let cancelled = false;
    void Promise.all(
      bios.map(async (bio) => {
        const { page, snapshots } = await loadHydratedPlayerSnapshots(
          bio.id,
          positionGroup,
          { season },
        );
        const position = page?.player.position ?? bio.position;
        const team = page?.player.team ?? bio.team;
        return {
          playerId: bio.id,
          name: bio.name,
          position,
          team,
          fantasyPosRank: page?.player.fantasyPosRank,
          fantasyPosRankKind: page?.player.fantasyPosRankKind,
          stats: hydratePlayerStats(position, snapshots),
        } satisfies CompareColumn;
      }),
    ).then((loaded) => {
      if (cancelled) return;
      setColumns(loaded);
      setLoadedKey(requestKey);
    }).catch(() => {
      if (cancelled) return;
      setColumns([]);
      setLoadedKey(requestKey);
    });
    return () => {
      cancelled = true;
    };
  }, [sameGroup, positionGroup, selectedIds, players, season, requestKey]);

  return { selectedBios, sameGroup, positionGroup, loading, displayedColumns };
}
