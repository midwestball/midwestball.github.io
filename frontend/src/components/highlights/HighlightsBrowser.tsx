"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  fetchHighlightsBoard,
  fetchLeagueWeeklyGroup,
  type LeagueGroupJson,
} from "@/lib/ballnet-store";
import { HighlightList } from "@/components/highlights/HighlightList";
import { GROUP_LABEL, type PositionGroup } from "@/lib/catalog";
import type { HighlightRow, HighlightsBoardJson } from "@/lib/payload";

const OFFENSE_GROUPS: PositionGroup[] = [
  "qb",
  "backfield",
  "pass_catcher",
  "kicker",
];

const DEFENSE_GROUPS: PositionGroup[] = ["def_front", "secondary"];

const ALL_GROUPS: PositionGroup[] = [...OFFENSE_GROUPS, ...DEFENSE_GROUPS];

const SIDE_TOP_N = 25;

/** REG week count: 17 through 2020, 18 from 2021. */
export function regWeeksInSeason(season: number): number {
  return season >= 2021 ? 18 : 17;
}

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

const selectClass =
  "h-9 rounded-none border border-zinc-200 bg-white px-2 text-sm text-zinc-900 outline-none focus:border-zinc-400";

export type HighlightsBrowserProps = {
  /** Earliest season with spine coverage (NGS era). */
  startSeason: number;
  currentSeason: number;
  currentWeek: number;
  initialSeason: number;
  initialWeek: number;
};

export function HighlightsBrowser({
  startSeason,
  currentSeason,
  currentWeek,
  initialSeason,
  initialWeek,
}: HighlightsBrowserProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const seasonOptions = useMemo(() => {
    const out: number[] = [];
    for (let y = currentSeason; y >= startSeason; y -= 1) out.push(y);
    return out;
  }, [currentSeason, startSeason]);

  const parseSeason = (raw: string | null): number => {
    const n = Number(raw);
    if (!Number.isFinite(n) || n < startSeason || n > currentSeason) {
      return initialSeason;
    }
    return n;
  };

  const maxWeekFor = useCallback(
    (season: number) => {
      if (season === currentSeason) return Math.max(1, currentWeek);
      return regWeeksInSeason(season);
    },
    [currentSeason, currentWeek],
  );

  const parseWeek = (raw: string | null, season: number): number => {
    const max = maxWeekFor(season);
    const n = Number(raw);
    if (!Number.isFinite(n) || n < 1 || n > max) return Math.min(initialWeek, max);
    return n;
  };

  const [season, setSeason] = useState(() =>
    parseSeason(searchParams.get("season")),
  );
  const [week, setWeek] = useState(() =>
    parseWeek(searchParams.get("week"), parseSeason(searchParams.get("season"))),
  );
  const [board, setBoard] = useState<HighlightsBoardJson | null>(null);
  const [weeklyByGroup, setWeeklyByGroup] = useState<
    Record<string, LeagueGroupJson | null>
  >({});
  const [status, setStatus] = useState<"loading" | "ready" | "empty" | "error">(
    "loading",
  );

  const weekOptions = useMemo(() => {
    const max = maxWeekFor(season);
    return Array.from({ length: max }, (_, i) => i + 1);
  }, [season, maxWeekFor]);

  // Keep URL in sync for shareable links (static export).
  useEffect(() => {
    const params = new URLSearchParams();
    params.set("season", String(season));
    params.set("week", String(week));
    const next = `${pathname}?${params.toString()}`;
    const current = `${pathname}?${searchParams.toString()}`;
    if (next !== current) {
      router.replace(next, { scroll: false });
    }
    // Intentionally omit searchParams from deps — we only push when season/week change.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- URL mirror
  }, [season, week, pathname, router]);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    setBoard(null);
    setWeeklyByGroup({});

    void (async () => {
      try {
        const nextBoard = await fetchHighlightsBoard(season, week);
        if (cancelled) return;
        if (!nextBoard) {
          setBoard(null);
          setWeeklyByGroup({});
          setStatus("empty");
          return;
        }
        const entries = await Promise.all(
          ALL_GROUPS.map(async (group) => {
            const json = await fetchLeagueWeeklyGroup(group, season, week);
            return [group, json] as const;
          }),
        );
        if (cancelled) return;
        setBoard(nextBoard);
        setWeeklyByGroup(Object.fromEntries(entries));
        const hasRows = Object.values(nextBoard.byGroup ?? {}).some(
          (rows) => (rows?.length ?? 0) > 0,
        );
        setStatus(hasRows ? "ready" : "empty");
      } catch {
        if (!cancelled) setStatus("error");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [season, week]);

  const byGroup = board?.byGroup;
  const offenseTop = sideTop(byGroup, OFFENSE_GROUPS);
  const defenseTop = sideTop(byGroup, DEFENSE_GROUPS);
  const hasBoard = status === "ready";

  return (
    <div>
      <div className="border-b border-zinc-200 bg-white">
        <div className="mx-auto max-w-3xl px-4 py-5">
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-1.5 text-xs font-semibold tracking-[0.15em] text-zinc-500 uppercase">
              Season
              <select
                value={season}
                onChange={(e) => {
                  const next = Number(e.target.value);
                  setSeason(next);
                  setWeek((w) => Math.min(w, maxWeekFor(next)));
                }}
                className={selectClass}
              >
                {seasonOptions.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex items-center gap-1.5 text-xs font-semibold tracking-[0.15em] text-zinc-500 uppercase">
              Week
              <select
                value={week}
                onChange={(e) => setWeek(Number(e.target.value))}
                className={selectClass}
              >
                {weekOptions.map((w) => (
                  <option key={w} value={w}>
                    {w}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">
            Highlights
          </h1>
          <p className="mt-1 max-w-xl text-sm leading-5 text-zinc-600">
            Best single-game performances, offense first. Ranked by z-score
            versus all-time single-game peers — expand a row for the league
            distribution and any other standout stats from the same player.
          </p>
        </div>
      </div>

      <main className="mx-auto max-w-3xl space-y-6 px-4 py-4">
        {status === "loading" ? (
          <p className="text-sm text-zinc-500">Loading highlights…</p>
        ) : null}
        {status === "error" ? (
          <p className="text-sm text-zinc-500">
            Could not load highlights for {season} week {week}.
          </p>
        ) : null}
        {status === "empty" ? (
          <p className="text-sm text-zinc-500">
            No highlight board published for {season} week {week} yet.
          </p>
        ) : null}

        {hasBoard ? (
          <>
            <section className="space-y-2">
              <h2 className="text-xs font-semibold tracking-[0.15em] text-zinc-500 uppercase">
                Offense
              </h2>
              <HighlightList
                rows={offenseTop}
                season={season}
                weeklyByGroup={weeklyByGroup}
              />
            </section>

            <GroupSections
              groups={OFFENSE_GROUPS}
              byGroup={byGroup}
              season={season}
              weeklyByGroup={weeklyByGroup}
            />

            <section className="space-y-2">
              <h2 className="text-xs font-semibold tracking-[0.15em] text-zinc-500 uppercase">
                Defense
              </h2>
              <HighlightList
                rows={defenseTop}
                season={season}
                weeklyByGroup={weeklyByGroup}
              />
            </section>

            <GroupSections
              groups={DEFENSE_GROUPS}
              byGroup={byGroup}
              season={season}
              weeklyByGroup={weeklyByGroup}
            />
          </>
        ) : null}

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
