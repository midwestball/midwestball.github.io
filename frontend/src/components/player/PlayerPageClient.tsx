"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { GROUP_LABEL, positionGroupOf } from "@/lib/catalog";
import { hydratePlayerStats } from "@/lib/catalog/hydrate";
import type { StatPayload } from "@/lib/distribution";
import type { PlayerBio, PlayerPageJson } from "@/lib/payload";
import { loadHydratedPlayerSnapshots } from "@/lib/ballnet-store";
import { TremorVariant } from "@/components/stat-row/variants";
import { SeasonSelect } from "@/components/player/SeasonSelect";
import { PositionRankLabel } from "@/components/PositionRankLabel";
import { TeamAbbr } from "@/components/TeamAbbr";

export function PlayerPageClient({
  player,
  currentSeason,
}: {
  player: PlayerBio;
  currentSeason: number;
}) {
  const searchParams = useSearchParams();
  const seasonParam = searchParams.get("season");
  const season = useMemo(() => {
    const requested = Number(seasonParam);
    if (player.seasons.includes(requested)) return requested;
    if (player.seasons.includes(currentSeason)) return currentSeason;
    return player.seasons[player.seasons.length - 1] ?? currentSeason;
  }, [player.seasons, seasonParam, currentSeason]);

  const positionGroup = positionGroupOf(player.position);
  const groupLabel = GROUP_LABEL[positionGroup];

  const [pageJson, setPageJson] = useState<PlayerPageJson | null>(null);
  const [stats, setStats] = useState<StatPayload[]>([]);
  const [status, setStatus] = useState<"loading" | "ready">("loading");

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    void loadHydratedPlayerSnapshots(player.id, positionGroup, { season }).then(
      ({ page, snapshots }) => {
        if (cancelled) return;
        setPageJson(page);
        setStats(hydratePlayerStats(player.position, snapshots));
        setStatus("ready");
      },
    );
    return () => {
      cancelled = true;
    };
  }, [player.id, player.position, positionGroup, season]);

  const hasSnapshot = Boolean(pageJson);
  const displayPosition = pageJson?.player.position ?? player.position;
  const displayTeam = pageJson?.player.team ?? player.team;

  return (
    <div>
      <div className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-3xl flex-col gap-3 px-4 py-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold tracking-[0.2em] text-zinc-500 uppercase">
              Player · {groupLabel}
            </p>
            <h1 className="mt-0.5 text-3xl font-semibold tracking-tight">
              {player.name}
            </h1>
            <p className="mt-1 max-w-xl text-sm leading-5 text-zinc-600">
              Every {player.position} row from the position catalog versus the
              league.
              {status === "ready" && hasSnapshot
                ? " Showing Ballnet season-to-date snapshots."
                : status === "ready"
                  ? " Snapshots are empty until Ballnet publishes JSON."
                  : " Loading snapshots…"}
            </p>
            {player.id === "demo-qb" ? (
              <p className="mt-2 text-sm text-zinc-500">
                <Link
                  href="/lab/qb"
                  className="font-medium text-zinc-900 underline"
                >
                  QB layout experiments
                </Link>
              </p>
            ) : null}
          </div>
          <div className="rounded-none border border-zinc-200 bg-zinc-50 px-3 py-2">
            <p className="text-lg font-semibold">{player.name}</p>
            <p className="flex flex-wrap items-center gap-x-1.5 text-sm text-zinc-500">
              <PositionRankLabel
                position={displayPosition}
                rank={pageJson?.player.fantasyPosRank}
                kind={pageJson?.player.fantasyPosRankKind}
              />
              <span aria-hidden>·</span>
              <TeamAbbr team={displayTeam} />
              <span aria-hidden>·</span>
              <span>{season}</span>
            </p>
            <p className="mt-1 text-xs text-zinc-400">
              {hasSnapshot && pageJson
                ? `As of week ${pageJson.asOfWeek}`
                : "Current season · no snapshot yet"}
            </p>
          </div>
        </div>
      </div>

      <main className="mx-auto max-w-3xl px-4 py-4">
        <TremorVariant stats={stats} />
        <div className="mt-4 rounded-none border border-zinc-200 bg-white px-3 py-2">
          <SeasonSelect
            playerId={player.id}
            season={season}
            seasons={player.seasons}
          />
        </div>
      </main>
    </div>
  );
}
