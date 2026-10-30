import { Suspense } from "react";
import { SearchPageClient } from "@/components/search/SearchPageClient";
import {
  loadCurrentSeasonContext,
  loadPlayerIndex,
  loadPublishedSeasons,
} from "@/data/players";

export default async function SearchPage() {
  const [players, current, seasons] = await Promise.all([
    loadPlayerIndex(),
    loadCurrentSeasonContext(),
    loadPublishedSeasons(),
  ]);

  return <Suspense fallback={<main className="p-4">Loading Search...</main>}>
    <SearchPageClient players={players} seasons={seasons} initialSeason={current.season} />
  </Suspense>;
}
