import { Suspense } from "react";
import {
  loadCurrentSeasonContext,
  loadPlayerIndex,
  loadPublishedSeasons,
} from "@/data/players";
import { ComparePageClient } from "@/components/compare/ComparePageClient";

export default async function ComparePage() {
  const [index, { season: currentSeason }, publishedSeasons] =
    await Promise.all([
      loadPlayerIndex(),
      loadCurrentSeasonContext(),
      loadPublishedSeasons(),
    ]);

  const seasonOptions = publishedSeasons.map((row) => row.season);

  return (
    <Suspense
      fallback={
        <div className="px-4 py-8 text-sm text-zinc-500">Loading compare…</div>
      }
    >
      <ComparePageClient
        players={index}
        seasonOptions={seasonOptions}
        currentSeason={currentSeason}
      />
    </Suspense>
  );
}
