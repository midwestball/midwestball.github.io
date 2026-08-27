import Link from "next/link";
import {
  loadHighlightsBoard,
  loadLeagueWeeklyGroupJson,
  type LeagueGroupJson,
} from "@/lib/ballnet-store";
import { loadCurrentSeasonContext } from "@/data/players";
import { HighlightList } from "@/components/highlights/HighlightList";
import { GROUP_LABEL, type PositionGroup } from "@/lib/catalog";
import type { HighlightRow } from "@/lib/payload";

export const revalidate = 3600;

/** Offense first — most interest / denser box-score data. Kicker rides with scoring. */
const OFFENSE_GROUPS: PositionGroup[] = [
  "qb",
  "backfield",
  "pass_catcher",
  "kicker",
];

const DEFENSE_GROUPS: PositionGroup[] = ["def_front", "secondary"];

const SIDE_TOP_N = 25;

function sideTop(
  byGroup: Record<string, HighlightRow[]> | undefined,
  groups: PositionGroup[],
): HighlightRow[] {
  const rows = groups.flatMap((g) => byGroup?.[g] ?? []);
  rows.sort((a, b) => b.zScore - a.zScore);
  return rows.slice(0, SIDE_TOP_N).map((row, i) => ({ ...row, rank: i + 1 }));
}

function GroupSections({
  groups,
  byGroup,
  season,
  weeklyByGroup,
}: {
  groups: PositionGroup[];
  byGroup: Record<string, HighlightRow[]> | undefined;
  season: number;
  weeklyByGroup: Record<string, LeagueGroupJson | null>;
}) {
  return (
    <>
      {groups.map((group) => {
        const rows = byGroup?.[group] ?? [];
        if (rows.length === 0) return null;
        return (
          <section key={group} className="space-y-2">
            <h2 className="text-xs font-semibold tracking-[0.15em] text-zinc-500 uppercase">
              {GROUP_LABEL[group]}
            </h2>
            <HighlightList
              rows={rows}
              season={season}
              weeklyByGroup={weeklyByGroup}
            />
          </section>
        );
      })}
    </>
  );
}

export default async function Home() {
  const [{ season, asOfWeek }, board] = await Promise.all([
    loadCurrentSeasonContext(),
    loadHighlightsBoard(),
  ]);

  const week = board?.week ?? asOfWeek;
  const boardSeason = board?.season ?? season;
  const byGroup = board?.byGroup;
  const offenseTop = sideTop(byGroup, OFFENSE_GROUPS);
  const defenseTop = sideTop(byGroup, DEFENSE_GROUPS);
  const hasBoard = Boolean(
    board && (offenseTop.length > 0 || defenseTop.length > 0),
  );

  const groupsNeeded = new Set<string>();
  if (board) {
    for (const rows of Object.values(byGroup ?? {})) {
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
              ? "Best single-game performances this week, offense first. Ranked by z-score versus season single-game peers — expand a row for the league distribution."
              : "Weekly standouts will land here once Ballnet publishes a highlight board for this week."}
          </p>
        </div>
      </div>

      <main className="mx-auto max-w-3xl space-y-6 px-4 py-4">
        {hasBoard ? (
          <>
            <section className="space-y-2">
              <h2 className="text-xs font-semibold tracking-[0.15em] text-zinc-500 uppercase">
                Offense
              </h2>
              <HighlightList
                rows={offenseTop}
                season={boardSeason}
                weeklyByGroup={weeklyByGroup}
              />
            </section>

            <GroupSections
              groups={OFFENSE_GROUPS}
              byGroup={byGroup}
              season={boardSeason}
              weeklyByGroup={weeklyByGroup}
            />

            <section className="space-y-2">
              <h2 className="text-xs font-semibold tracking-[0.15em] text-zinc-500 uppercase">
                Defense
              </h2>
              <HighlightList
                rows={defenseTop}
                season={boardSeason}
                weeklyByGroup={weeklyByGroup}
              />
            </section>

            <GroupSections
              groups={DEFENSE_GROUPS}
              byGroup={byGroup}
              season={boardSeason}
              weeklyByGroup={weeklyByGroup}
            />
          </>
        ) : (
          <section className="space-y-2">
            <h2 className="text-xs font-semibold tracking-[0.15em] text-zinc-500 uppercase">
              Top games
            </h2>
            <HighlightList rows={[]} season={boardSeason} />
          </section>
        )}

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
