"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  GROUP_LABEL,
  isPositionCode,
  positionGroupOf,
  type PositionGroup,
} from "@/lib/catalog";
import { hydratePlayerStats } from "@/lib/catalog/hydrate";
import type { PlayerBio } from "@/lib/payload";
import { loadHydratedPlayerSnapshots } from "@/lib/ballnet-store";
import {
  CompareBoard,
  type CompareColumn,
} from "@/components/compare/CompareBoard";
import { ComparePicker } from "@/components/compare/ComparePicker";

const MAX_PLAYERS = 4;

function parsePlayerIds(raw: string | null): string[] {
  if (!raw) return [];
  const seen = new Set<string>();
  const ids: string[] = [];
  for (const part of raw.split(",")) {
    const id = part.trim();
    if (!id || seen.has(id)) continue;
    seen.add(id);
    ids.push(id);
    if (ids.length >= MAX_PLAYERS) break;
  }
  return ids;
}

export function ComparePageClient({
  players,
  seasonOptions,
  currentSeason,
}: {
  players: PlayerBio[];
  seasonOptions: number[];
  currentSeason: number;
}) {
  const searchParams = useSearchParams();
  const selectedIds = useMemo(
    () => parsePlayerIds(searchParams.get("p")),
    [searchParams],
  );
  const season = useMemo(() => {
    const requested = Number(searchParams.get("season"));
    return seasonOptions.includes(requested) ? requested : currentSeason;
  }, [searchParams, seasonOptions, currentSeason]);

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
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!sameGroup || !positionGroup || selectedIds.length === 0) {
      setColumns([]);
      setLoading(false);
      return;
    }
    const bios = selectedIds
      .map((id) => players.find((player) => player.id === id))
      .filter((player): player is PlayerBio => Boolean(player));
    if (bios.length === 0) {
      setColumns([]);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
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
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [sameGroup, positionGroup, selectedIds, players, season]);

  const groupLabel =
    positionGroup != null ? GROUP_LABEL[positionGroup] : null;

  return (
    <div>
      <div className="border-b border-zinc-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-5">
          <p className="text-xs font-semibold tracking-[0.2em] text-zinc-500 uppercase">
            Players
          </p>
          <h1 className="mt-0.5 text-3xl font-semibold tracking-tight">
            Compare
          </h1>
          <p className="mt-1 max-w-xl text-sm leading-5 text-zinc-600">
            Place up to four players side by side. Expand a row for one shared
            league plot with team-colored markers
            {groupLabel ? ` · ${groupLabel}` : ""}.
          </p>
        </div>
      </div>

      <main className="mx-auto max-w-6xl space-y-4 px-4 py-4">
        <div className="rounded-none border border-zinc-200 bg-white px-3 py-3">
          <ComparePicker
            players={players}
            selectedIds={selectedBios.map((p) => p.id)}
            season={season}
            seasons={seasonOptions}
          />
        </div>

        {!sameGroup ? (
          <div className="rounded-none border border-zinc-200 bg-white px-3 py-4 text-sm leading-5 text-zinc-600">
            Compare requires players from the same position group. Remove a
            player or pick a matching group.
          </div>
        ) : loading ? (
          <div className="rounded-none border border-zinc-200 bg-white px-3 py-4 text-sm leading-5 text-zinc-600">
            Loading comparison…
          </div>
        ) : columns.length === 0 ? (
          <div className="rounded-none border border-zinc-200 bg-white px-3 py-4 text-sm leading-5 text-zinc-600">
            Select players above to align their percentile sliders and league
            distributions.
          </div>
        ) : (
          <div className="rounded-none border border-zinc-200 bg-white max-md:-mx-4 max-md:border-x-0">
            <CompareBoard columns={columns} />
          </div>
        )}
      </main>
    </div>
  );
}
