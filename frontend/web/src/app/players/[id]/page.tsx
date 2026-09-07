import { notFound } from "next/navigation";
import Link from "next/link";
import { GROUP_LABEL, positionGroupOf } from "@/lib/catalog";
import { hydratePlayerStats } from "@/lib/catalog/hydrate";
import {
  DEMO_PLAYER_INDEX,
  getPlayer,
  loadCurrentSeasonContext,
} from "@/data/players";
import { TremorVariant } from "@/components/stat-row/variants";
import { SeasonSelect } from "@/components/player/SeasonSelect";
import { loadHydratedPlayerSnapshots } from "@/lib/ballnet-store";

// Player pages are scalars; league curves load once per position group.
export const dynamicParams = true;
export const revalidate = 3600;

export function generateStaticParams() {
  return DEMO_PLAYER_INDEX.map((player) => ({ id: player.id }));
}

export default async function PlayerPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ season?: string }>;
}) {
  const { id } = await params;
  const { season: seasonParam } = await searchParams;
  const [player, { season: currentSeason }] = await Promise.all([
    getPlayer(id),
    loadCurrentSeasonContext(),
  ]);
  if (!player) notFound();

  const requested = Number(seasonParam);
  const season =
    player.seasons.includes(requested)
      ? requested
      : player.seasons.includes(currentSeason)
        ? currentSeason
        : (player.seasons[player.seasons.length - 1] ?? currentSeason);

  const positionGroup = positionGroupOf(player.position);
  const { page: pageJson, snapshots } = await loadHydratedPlayerSnapshots(
    id,
    positionGroup,
    { season },
  );

  const stats = hydratePlayerStats(player.position, snapshots);
  const groupLabel = GROUP_LABEL[positionGroup];
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
              {hasSnapshot
                ? " Showing Ballnet season-to-date snapshots."
                : " Snapshots are empty until Ballnet publishes JSON."}
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
            <p className="text-sm text-zinc-500">
              {displayPosition} · {displayTeam} · {season}
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
