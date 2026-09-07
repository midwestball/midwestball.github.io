import { PlayerSearch } from "@/components/search/PlayerSearch";
import {
  loadCurrentSeasonContext,
  loadPlayerIndex,
  loadPublishedSeasons,
} from "@/data/players";

export const revalidate = 3600;

export default async function SearchPage() {
  const [players, current, seasons] = await Promise.all([
    loadPlayerIndex(),
    loadCurrentSeasonContext(),
    loadPublishedSeasons(),
  ]);

  return (
    <div>
      <div className="border-b border-zinc-200 bg-white">
        <div className="mx-auto max-w-3xl px-4 py-5">
          <p className="text-xs font-semibold tracking-[0.2em] text-zinc-500 uppercase">
            Roster
          </p>
          <h1 className="mt-0.5 text-3xl font-semibold tracking-tight">Search</h1>
          <p className="mt-1 max-w-xl text-sm leading-5 text-zinc-600">
            Default context is the current published season. Names come from
            Ballnet&apos;s player index.
          </p>
        </div>
      </div>
      <main className="mx-auto max-w-3xl px-4 py-4">
        <PlayerSearch
          players={players}
          seasons={seasons}
          initialSeason={current.season}
        />
      </main>
    </div>
  );
}
