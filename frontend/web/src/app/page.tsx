import Link from "next/link";
import { loadPlayerIndex } from "@/data/players";

export const revalidate = 3600;

export default async function Home() {
  const index = await loadPlayerIndex();
  const featured = index.slice(0, 4);

  return (
    <div>
      <div className="border-b border-zinc-200 bg-white">
        <div className="mx-auto max-w-3xl px-4 py-5">
          <p className="text-xs font-semibold tracking-[0.2em] text-zinc-500 uppercase">
            This week
          </p>
          <h1 className="mt-0.5 text-3xl font-semibold tracking-tight">
            Highlights
          </h1>
          <p className="mt-1 max-w-xl text-sm leading-5 text-zinc-600">
            Weekly standouts will land here once Ballnet publishes snapshots.
            Until then this is a placeholder for the current week.
          </p>
        </div>
      </div>

      <main className="mx-auto max-w-3xl space-y-1 px-4 py-4">
        {featured.map((player) => (
          <Link
            key={player.id}
            href={`/players/${player.id}`}
            className="flex items-center justify-between rounded-none border border-zinc-200 bg-white px-3 py-2 hover:bg-zinc-50"
          >
            <div>
              <p className="text-lg font-semibold">{player.name}</p>
              <p className="text-sm text-zinc-500">
                {player.position} · {player.team}
              </p>
            </div>
            <span className="text-xs text-zinc-400">Stats skeleton</span>
          </Link>
        ))}
        <p className="pt-1 text-sm text-zinc-500">
          Looking for someone else?{" "}
          <Link href="/search" className="font-medium text-zinc-900 underline">
            Search every player
          </Link>
          .
        </p>
      </main>
    </div>
  );
}
