import Link from "next/link";
import {
  loadHighlightsBoard,
  loadLeagueWeeklyGroupJson,
  type LeagueGroupJson,
} from "@/lib/ballnet-store";
import { loadCurrentSeasonContext } from "@/data/players";
import { HighlightList } from "@/components/highlights/HighlightList";
import { GROUP_LABEL, type PositionGroup } from "@/lib/catalog";

export const revalidate = 3600;

const GROUP_ORDER: PositionGroup[] = [
  "qb",
  "backfield",
  "pass_catcher",
  "def_front",
  "secondary",
  "kicker",
];

export default async function Home() {
  const [{ season, asOfWeek }, board] = await Promise.all([
    loadCurrentSeasonContext(),
    loadHighlightsBoard(),
  ]);

  const week = board?.week ?? asOfWeek;
  const boardSeason = board?.season ?? season;
  const top = board?.top ?? [];
  const hasBoard = Boolean(board && top.length > 0);

  const groupsNeeded = new Set<string>();
  if (board) {
    for (const row of board.top) groupsNeeded.add(row.positionGroup);
    for (const rows of Object.values(board.byGroup ?? {})) {
      for (const row of rows) groupsNeeded.add(row.positionGroup);
    }
  }

  const weeklyEntries = await Promise.all(
    [...groupsNeeded].map(async (group) => {
      const json = await loadLeagueWeeklyGroupJson(group, {
        season: boardSeason,
        asOfWeek: week,
      });
      return [group, json] as const;
    }),
  );
  const weeklyByGroup: Record<string, LeagueGroupJson | null> =
    Object.fromEntries(weeklyEntries);

  return (
    <div>
      <div className="border-b border-zinc-200 bg-white">
        <div className="mx-auto max-w-3xl px-4 py-5">
          <p className="text-xs font-semibold tracking-[0.2em] text-zinc-500 uppercase">
            {boardSeason} · Week {week}
          </p>
          <h1 className="mt-0.5 text-3xl font-semibold tracking-tight">
            Highlights
          </h1>
          <p className="mt-1 max-w-xl text-sm leading-5 text-zinc-600">
            {hasBoard
              ? "Best single-game stat performances this week, ranked by z-score versus season single-game peers. Expand a row for the league distribution."
              : "Weekly standouts will land here once Ballnet publishes a highlight board for this week."}
          </p>
        </div>
      </div>

      <main className="mx-auto max-w-3xl space-y-6 px-4 py-4">
        <section className="space-y-2">
          <h2 className="text-xs font-semibold tracking-[0.15em] text-zinc-500 uppercase">
            Top games
          </h2>
          <HighlightList
            rows={top}
            season={boardSeason}
            weeklyByGroup={weeklyByGroup}
          />
        </section>

        {hasBoard
          ? GROUP_ORDER.map((group) => {
              const rows = board?.byGroup?.[group] ?? [];
              if (rows.length === 0) return null;
              return (
                <section key={group} className="space-y-2">
                  <h2 className="text-xs font-semibold tracking-[0.15em] text-zinc-500 uppercase">
                    {GROUP_LABEL[group]}
                  </h2>
                  <HighlightList
                    rows={rows}
                    season={boardSeason}
                    weeklyByGroup={weeklyByGroup}
                  />
                </section>
              );
            })
          : null}

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
