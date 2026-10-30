"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  fetchCurrentMeta,
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

/** Defense boards still publish; UI hidden until distribution issues are fixed. */
const SIDE_TOP_N = 25;
const OFFENSE_PREVIEW_N = 8;
const GROUP_PREVIEW_N = 3;

/** REG week count: 17 through 2020, 18 from 2021. */
export function regWeeksInSeason(season: number): number {
  return season >= 2021 ? 18 : 17;
}

function sideTop(
  byGroup: Record<string, HighlightRow[]> | undefined,
  groups: PositionGroup[],
): HighlightRow[] {
  const rows = groups.flatMap((g) => byGroup?.[g] ?? []);
  rows.sort((a, b) => (b.rarityScore ?? b.zScore) - (a.rarityScore ?? a.zScore));
  return rows.slice(0, SIDE_TOP_N).map((row, i) => ({ ...row, rank: i + 1 }));
}

function HighlightListPreview({
  rows,
  season,
  weeklyByGroup,
  initialVisible,
  resetKey,
}: {
  rows: HighlightRow[];
  season: number;
  weeklyByGroup: Record<string, LeagueGroupJson | null>;
  initialVisible: number;
  /** Change when season/week changes so “see more” collapses again. */
  resetKey: string;
}) {
  const [expansion, setExpansion] = useState({ key: resetKey, expanded: false });
  const expanded = expansion.key === resetKey && expansion.expanded;

  const visible =
    expanded || rows.length <= initialVisible
      ? rows
      : rows.slice(0, initialVisible);
  const hiddenCount = rows.length - initialVisible;

  return (
    <div className="space-y-1">
      <HighlightList
        rows={visible}
        season={season}
        weeklyByGroup={weeklyByGroup}
      />
      {hiddenCount > 0 ? (
        <button
          type="button"
          onClick={() => setExpansion({ key: resetKey, expanded: !expanded })}
          className="text-xs text-muted-foreground hover:text-text-secondary"
        >
          {expanded ? "See less" : "See more"}
        </button>
      ) : null}
    </div>
  );
}

function GroupSections({
  groups,
  byGroup,
  season,
  weeklyByGroup,
  resetKey,
}: {
  groups: PositionGroup[];
  byGroup: Record<string, HighlightRow[]> | undefined;
  season: number;
  weeklyByGroup: Record<string, LeagueGroupJson | null>;
  resetKey: string;
}) {
  return (
    <>
      {groups.map((group) => {
        const rows = byGroup?.[group] ?? [];
        if (rows.length === 0) return null;
        return (
          <section key={group} className="space-y-2">
            <h2 className="text-xs font-semibold tracking-[0.15em] text-muted-foreground uppercase">
              {GROUP_LABEL[group]}
            </h2>
            <HighlightListPreview
              rows={rows}
              season={season}
              weeklyByGroup={weeklyByGroup}
              initialVisible={GROUP_PREVIEW_N}
              resetKey={`${resetKey}-${group}`}
            />
          </section>
        );
      })}
    </>
  );
}

const selectClass =
  "h-9 rounded-none border border-border bg-card px-2 text-sm text-foreground outline-none focus:border-ring";

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
  const initialQuery = useRef({
    season: searchParams.get("season"),
    week: searchParams.get("week"),
  });
  const selectionTouched = useRef(false);
  const [latestSeason, setLatestSeason] = useState(currentSeason);
  const [latestWeek, setLatestWeek] = useState(currentWeek);

  const seasonOptions = useMemo(() => {
    const out: number[] = [];
    for (let y = latestSeason; y >= startSeason; y -= 1) out.push(y);
    return out;
  }, [latestSeason, startSeason]);

  const parseSeason = (raw: string | null): number => {
    const n = Number(raw);
    if (!Number.isFinite(n) || n < startSeason || n > latestSeason) {
      return initialSeason;
    }
    return n;
  };

  const maxWeekFor = useCallback(
    (season: number) => {
      if (season === latestSeason) return Math.max(1, latestWeek);
      return regWeeksInSeason(season);
    },
    [latestSeason, latestWeek],
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
  const [responseStatus, setStatus] = useState<"loading" | "ready" | "empty" | "error">(
    "loading",
  );
  const [responseKey, setResponseKey] = useState("");
  const sliceKey = `${season}-${week}`;
  const status = responseKey === sliceKey ? responseStatus : "loading";

  const weekOptions = useMemo(() => {
    const max = maxWeekFor(season);
    return Array.from({ length: max }, (_, i) => i + 1);
  }, [season, maxWeekFor]);

  // The page is statically exported, so its props reflect the last site build.
  // Refresh the current pointer from Storage in the browser after every page load.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const current = await fetchCurrentMeta();
      if (cancelled || !current) return;

      const currentWeek = Math.max(1, current.asOfWeek);
      setLatestSeason(current.season);
      setLatestWeek(currentWeek);

      const requestedSeason = Number(initialQuery.current.season);
      const hasRequestedSeason =
        initialQuery.current.season !== null &&
        Number.isFinite(requestedSeason) &&
        requestedSeason >= startSeason &&
        requestedSeason <= current.season;
      const selectedSeason = hasRequestedSeason
        ? requestedSeason
        : current.season;
      const maxWeek =
        selectedSeason === current.season
          ? currentWeek
          : regWeeksInSeason(selectedSeason);
      const requestedWeek = Number(initialQuery.current.week);
      const hasRequestedWeek =
        initialQuery.current.week !== null &&
        Number.isFinite(requestedWeek) &&
        requestedWeek >= 1 &&
        requestedWeek <= maxWeek;

      if (!selectionTouched.current) {
        setSeason(selectedSeason);
        setWeek(hasRequestedWeek ? requestedWeek : maxWeek);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [startSeason]);

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

    void (async () => {
      try {
        const nextBoard = await fetchHighlightsBoard(season, week);
        if (cancelled) return;
        if (!nextBoard) {
          setBoard(null);
          setWeeklyByGroup({});
          setStatus("empty");
          setResponseKey(sliceKey);
          return;
        }
        const entries = await Promise.all(
          OFFENSE_GROUPS.map(async (group) => {
            const json = await fetchLeagueWeeklyGroup(group, season, week);
            return [group, json] as const;
          }),
        );
        if (cancelled) return;
        setBoard(nextBoard);
        setWeeklyByGroup(Object.fromEntries(entries));
        const hasRows = OFFENSE_GROUPS.some(
          (g) => (nextBoard.byGroup?.[g]?.length ?? 0) > 0,
        );
        setStatus(hasRows ? "ready" : "empty");
        setResponseKey(sliceKey);
      } catch {
        if (!cancelled) { setStatus("error"); setResponseKey(sliceKey); }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [season, week, sliceKey]);

  const byGroup = board?.byGroup;
  const offenseTop = sideTop(byGroup, OFFENSE_GROUPS);
  const hasBoard = status === "ready";

  return (
    <div>
      <div className="border-b border-border bg-card">
        <div className="mx-auto max-w-3xl px-4 py-5">
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-1.5 text-xs font-semibold tracking-[0.15em] text-muted-foreground uppercase">
              Season
              <select
                value={season}
                onChange={(e) => {
                  selectionTouched.current = true;
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
            <label className="flex items-center gap-1.5 text-xs font-semibold tracking-[0.15em] text-muted-foreground uppercase">
              Week
              <select
                value={week}
                onChange={(e) => { selectionTouched.current = true; setWeek(Number(e.target.value)); }}
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
          <p className="mt-1 max-w-xl text-sm leading-5 text-text-secondary">
            Best single-game offensive performances. {board?.schemaVersion === 2
              ? "Ranked by observed rarity among qualifying games since 2016."
              : "Legacy boards are ranked by standardized scores among qualifying games since 2016."}
            {" "}Expand a row for the peer distribution and other standout stats.
          </p>
        </div>
      </div>

      <main className="mx-auto max-w-3xl space-y-6 px-4 py-4">
        {status === "loading" ? (
          <p className="text-sm text-muted-foreground">Loading highlights…</p>
        ) : null}
        {status === "error" ? (
          <p className="text-sm text-muted-foreground">
            Could not load highlights for {season} week {week}.
          </p>
        ) : null}
        {status === "empty" ? (
          <p className="text-sm text-muted-foreground">
            No highlight board published for {season} week {week} yet.
          </p>
        ) : null}

        {hasBoard ? (
          <>
            <section className="space-y-2">
              <h2 className="text-xs font-semibold tracking-[0.15em] text-muted-foreground uppercase">
                Offense
              </h2>
              <HighlightListPreview
                rows={offenseTop}
                season={season}
                weeklyByGroup={weeklyByGroup}
                initialVisible={OFFENSE_PREVIEW_N}
                resetKey={`${sliceKey}-offense`}
              />
            </section>

            <GroupSections
              groups={OFFENSE_GROUPS}
              byGroup={byGroup}
              season={season}
              weeklyByGroup={weeklyByGroup}
              resetKey={sliceKey}
            />
          </>
        ) : null}

        <p className="pt-1 text-sm text-muted-foreground">
          Looking for someone else?{" "}
          <Link href="/search" className="font-medium text-foreground underline">
            Search every player
          </Link>
          .
        </p>
      </main>
    </div>
  );
}
