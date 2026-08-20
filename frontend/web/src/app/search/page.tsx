import { PlayerSearch } from "@/components/search/PlayerSearch";

export default function SearchPage() {
  return (
    <div>
      <div className="border-b border-zinc-200 bg-white">
        <div className="mx-auto max-w-3xl px-4 py-5">
          <p className="text-xs font-semibold tracking-[0.2em] text-zinc-500 uppercase">
            Roster
          </p>
          <h1 className="mt-0.5 text-3xl font-semibold tracking-tight">Search</h1>
          <p className="mt-1 max-w-xl text-sm leading-5 text-zinc-600">
            Default context is the current season. These names are routing
            fixtures until Ballnet publishes a player index.
          </p>
        </div>
      </div>
      <main className="mx-auto max-w-3xl px-4 py-4">
        <PlayerSearch />
      </main>
    </div>
  );
}
