"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { GROUP_LABEL, positionGroupOf } from "@/lib/catalog";
import { hydratePlayerStats } from "@/lib/catalog/hydrate";
import type { StatPayload } from "@/lib/distribution";
import type { PlayerBio, PlayerPageJson } from "@/lib/payload";
import {
  fetchCurrentMeta,
  fetchPlayersIndex,
  loadHydratedPlayerSnapshots,
} from "@/lib/ballnet-store";
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
  const [livePlayer, setLivePlayer] = useState(player);
  const [latestSeason, setLatestSeason] = useState(currentSeason);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([fetchPlayersIndex(), fetchCurrentMeta()]).then(
      ([playerIndex, current]) => {
        if (cancelled) return;
        const currentBio = playerIndex?.players.find(
          (candidate) => candidate.id === player.id,
        );
        if (currentBio) setLivePlayer(currentBio);
        if (current) setLatestSeason(current.season);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [player]);

  const seasonParam = searchParams.get("season");
  const season = useMemo(() => {
    const requested = Number(seasonParam);
    if (livePlayer.seasons.includes(requested)) return requested;
    if (livePlayer.seasons.includes(latestSeason)) return latestSeason;
    return livePlayer.seasons[livePlayer.seasons.length - 1] ?? latestSeason;
  }, [livePlayer.seasons, seasonParam, latestSeason]);

  const positionGroup = positionGroupOf(livePlayer.position);

  const [pageJson, setPageJson] = useState<PlayerPageJson | null>(null);
  const [stats, setStats] = useState<StatPayload[]>([]);
  const [loadedKey, setLoadedKey] = useState("");
  const [loadError, setLoadError] = useState("");
  const [retry, setRetry] = useState(0);
  const requestKey = `${livePlayer.id}:${livePlayer.position}:${season}`;
  const status = loadedKey === requestKey ? "ready" : "loading";

  useEffect(() => {
    let cancelled = false;
    void loadHydratedPlayerSnapshots(livePlayer.id, positionGroup, { season }).then(
      ({ page, snapshots }) => {
        if (cancelled) return;
        setPageJson(page);
        setStats(hydratePlayerStats(page?.player.position ?? livePlayer.position, snapshots));
        setLoadError("");
        setLoadedKey(requestKey);
      },
    ).catch(() => {
      if (cancelled) return;
      setPageJson(null);
      setStats([]);
      setLoadError("Could not load this player’s statistics.");
      setLoadedKey(requestKey);
    });
    return () => {
      cancelled = true;
    };
  }, [livePlayer.id, livePlayer.position, positionGroup, season, requestKey, retry]);

  const displayedPage = loadedKey === requestKey ? pageJson : null;
  const hasSnapshot = Boolean(displayedPage);
  const displayPosition = displayedPage?.player.position ?? livePlayer.position;
  const displayTeam = displayedPage?.player.team ?? livePlayer.team;
  const groupLabel = GROUP_LABEL[positionGroupOf(displayPosition)];

  return (
    <div>
      <div className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-3xl flex-col gap-3 px-4 py-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold tracking-[0.2em] text-zinc-500 uppercase">
              Player · {groupLabel}
            </p>
            <h1 className="mt-0.5 text-3xl font-semibold tracking-tight">
              {livePlayer.name}
            </h1>
            <p className="mt-1 max-w-xl text-sm leading-5 text-zinc-600">
              Every {livePlayer.position} row from the position catalog versus the
              league.
              {status === "ready" && hasSnapshot
                ? " Showing Ballnet season-to-date snapshots."
                : status === "ready"
                  ? " Snapshots are empty until Ballnet publishes JSON."
                  : " Loading snapshots…"}
            </p>
            {livePlayer.id === "demo-qb" ? (
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
            <p className="text-lg font-semibold">{livePlayer.name}</p>
            <p className="flex flex-wrap items-center gap-x-1.5 text-sm text-zinc-500">
              <PositionRankLabel
                position={displayPosition}
                rank={displayedPage?.player.fantasyPosRank}
                kind={displayedPage?.player.fantasyPosRankKind}
              />
              <span aria-hidden>·</span>
              <TeamAbbr team={displayTeam} />
              <span aria-hidden>·</span>
              <span>{season}</span>
            </p>
            <p className="mt-1 text-xs text-zinc-400">
              {hasSnapshot && displayedPage
                ? `As of week ${displayedPage.asOfWeek}`
                : "Current season · no snapshot yet"}
            </p>
          </div>
        </div>
      </div>

      <main className="mx-auto max-w-3xl px-4 py-4">
        {loadError && loadedKey === requestKey && <p role="alert" className="mb-3 text-sm text-red-700">{loadError} <button className="underline" onClick={() => { setLoadedKey(""); setRetry(n => n + 1); }}>Retry</button></p>}
        <TremorVariant stats={displayedPage ? stats : []} />
        <div className="mt-4 rounded-none border border-zinc-200 bg-white px-3 py-2">
          <SeasonSelect
            playerId={livePlayer.id}
            season={season}
            seasons={livePlayer.seasons}
          />
        </div>
      </main>
    </div>
  );
}
