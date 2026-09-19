import { Suspense } from "react";
import { notFound } from "next/navigation";
import {
  getPlayer,
  loadCurrentSeasonContext,
  loadPlayerIndex,
} from "@/data/players";
import { PlayerPageClient } from "@/components/player/PlayerPageClient";

export async function generateStaticParams() {
  const players = await loadPlayerIndex();
  return players.map((player) => ({ id: player.id }));
}

export default async function PlayerPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [player, { season: currentSeason }] = await Promise.all([
    getPlayer(id),
    loadCurrentSeasonContext(),
  ]);
  if (!player) notFound();

  return (
    <Suspense
      fallback={<div className="px-4 py-8 text-sm text-zinc-500">Loading…</div>}
    >
      <PlayerPageClient player={player} currentSeason={currentSeason} />
    </Suspense>
  );
}
