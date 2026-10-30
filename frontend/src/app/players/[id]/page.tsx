import { Suspense } from "react";
import { loadPlayerIndex } from "@/data/players";
import { LegacyPlayerRedirect } from "@/components/player/LegacyPlayerRedirect";

/** Keep old exported links usable; all player analysis now lives in Search. */
export async function generateStaticParams() {
  const players = await loadPlayerIndex();
  return players.map(player => ({ id: player.id }));
}

export default async function LegacyPlayerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <Suspense fallback={<main className="p-4">Opening comparison...</main>}>
    <LegacyPlayerRedirect playerId={id} />
  </Suspense>;
}
