"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { writeBrowserQuery } from "@/components/share/browser-query";
import { patchQuery } from "@/lib/share-state/common";
import {
  fetchCurrentMeta,
  fetchPlayHighlightsBoard,
  fetchPlayLeagueShapes,
  type PlayLeagueShapesJson,
} from "@/lib/ballnet-store";
import type { PlayHighlightsBoardJson, PlayMetricMode } from "@/lib/payload";
import { PlayHighlightsSections } from "@/components/highlights/PlayHighlightList";
import { cn } from "@/lib/utils";

function regWeeksInSeason(season: number): number {
  return season >= 2021 ? 18 : 17;
}

type Props = {
  startSeason: number;
  currentSeason: number;
  currentWeek: number;
  initialSeason: number;
  initialWeek: number;
};

export function PlayHighlightsLabClient({
  startSeason,
  currentSeason,
  currentWeek,
  initialSeason,
  initialWeek,
}: Props) {
  const searchParams = useSearchParams();
  const initialQuery = useRef({
    season: searchParams.get("season"),
    week: searchParams.get("week"),
  });
  const selectionTouched = useRef(false);

  const [latestSeason, setLatestSeason] = useState(currentSeason);
  const [latestWeek, setLatestWeek] = useState(Math.max(1, currentWeek));

  const maxWeekFor = useCallback(
    (season: number) => {
      if (season === latestSeason) return Math.max(1, latestWeek);
      return regWeeksInSeason(season);
    },
    [latestSeason, latestWeek],
  );

  const parseSeason = useCallback(
    (raw: string | null): number => {
      const n = Number(raw);
      if (!Number.isInteger(n) || n < startSeason || n > latestSeason) {
        return initialSeason;
      }
      return n;
    },
    [startSeason, latestSeason, initialSeason],
  );

  const parseWeek = useCallback(
    (raw: string | null, season: number): number => {
      const max = maxWeekFor(season);
      const n = Number(raw);
      if (!Number.isInteger(n) || n < 1 || n > max) {
        return Math.min(initialWeek, max);
      }
      return n;
    },
    [maxWeekFor, initialWeek],
  );

  const [season, setSeason] = useState(() =>
    parseSeason(searchParams.get("season")),
  );
  const [week, setWeek] = useState(() =>
    parseWeek(
      searchParams.get("week"),
      parseSeason(searchParams.get("season")),
    ),
  );
  const [metricMode, setMetricMode] = useState<PlayMetricMode>(() => {
    const raw = searchParams.get("metric");
    return raw === "epa" ? "epa" : "raw";
  });
  const [board, setBoard] = useState<PlayHighlightsBoardJson | null>(null);
  const [shapes, setShapes] = useState<PlayLeagueShapesJson | null>(null);
  const [loading, setLoading] = useState(true);

  const seasons = useMemo(() => {
    const out: number[] = [];
    for (let y = latestSeason; y >= startSeason; y -= 1) out.push(y);
    return out;
  }, [latestSeason, startSeason]);

  const weeks = useMemo(() => {
    const max = maxWeekFor(season);
    return Array.from({ length: max }, (_, i) => i + 1);
  }, [season, maxWeekFor]);

  const syncUrl = useCallback(
    (nextSeason: number, nextWeek: number, nextMode: PlayMetricMode) => {
      writeBrowserQuery(
        patchQuery(searchParams, {
          season: String(nextSeason),
          week: String(nextWeek),
          metric: nextMode === "epa" ? "epa" : null,
        }),
      );
    },
    [searchParams],
  );

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const current = await fetchCurrentMeta();
      if (cancelled || !current) return;

      const liveWeek = Math.max(1, current.asOfWeek);
      setLatestSeason(current.season);
      setLatestWeek(liveWeek);

      const requestedSeason = Number(initialQuery.current.season);
      const hasRequestedSeason =
        initialQuery.current.season !== null &&
        Number.isInteger(requestedSeason) &&
        requestedSeason >= startSeason &&
        requestedSeason <= current.season;
      const selectedSeason = hasRequestedSeason
        ? requestedSeason
        : current.season;
      const maxWeek =
        selectedSeason === current.season
          ? liveWeek
          : regWeeksInSeason(selectedSeason);
      const requestedWeek = Number(initialQuery.current.week);
      const hasRequestedWeek =
        initialQuery.current.week !== null &&
        Number.isInteger(requestedWeek) &&
        requestedWeek >= 1 &&
        requestedWeek <= maxWeek;

      if (!selectionTouched.current) {
        const nextWeek = hasRequestedWeek ? requestedWeek : maxWeek;
        setSeason(selectedSeason);
        setWeek(nextWeek);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [startSeason]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void (async () => {
      const [nextBoard, nextShapes] = await Promise.all([
        fetchPlayHighlightsBoard(season, week, metricMode),
        fetchPlayLeagueShapes(season, week, metricMode),
      ]);
      if (cancelled) return;
      setBoard(nextBoard);
      setShapes(nextShapes);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [season, week, metricMode]);

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-8">
      <header className="space-y-2">
        <p className="text-[11px] font-semibold tracking-[0.14em] text-muted-foreground uppercase">
          Lab · not in nav
        </p>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Play rarity
        </h1>
        <p className="text-sm text-muted-foreground">
          Individual plays ranked within type (and position when available).
          Now also on{" "}
          <Link href="/" className="underline-offset-2 hover:underline">
            home Highlights
          </Link>{" "}
          under Top Plays.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          Season
          <select
            className="rounded-none border border-border bg-card px-2 py-1 text-foreground"
            value={season}
            onChange={(e) => {
              selectionTouched.current = true;
              const nextSeason = Number(e.target.value);
              const nextWeek = Math.min(week, maxWeekFor(nextSeason));
              setSeason(nextSeason);
              setWeek(nextWeek);
              syncUrl(nextSeason, nextWeek, metricMode);
            }}
          >
            {seasons.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          Week
          <select
            className="rounded-none border border-border bg-card px-2 py-1 text-foreground"
            value={week}
            onChange={(e) => {
              selectionTouched.current = true;
              const nextWeek = Number(e.target.value);
              setWeek(nextWeek);
              syncUrl(season, nextWeek, metricMode);
            }}
          >
            {weeks.map((w) => (
              <option key={w} value={w}>
                {w}
              </option>
            ))}
          </select>
        </label>
        <div
          className="flex items-center rounded-none border border-border"
          role="group"
          aria-label="Metric mode"
        >
          {(
            [
              ["raw", "Raw Stat"],
              ["epa", "EPA"],
            ] as const
          ).map(([mode, label]) => (
            <button
              key={mode}
              type="button"
              className={cn(
                "px-2 py-1 text-sm",
                metricMode === mode
                  ? "bg-foreground text-background"
                  : "bg-card text-muted-foreground hover:text-foreground",
              )}
              onClick={() => {
                selectionTouched.current = true;
                setMetricMode(mode);
                syncUrl(season, week, mode);
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {board?.missingPeerSeasons?.length ? (
        <p className="text-xs text-muted-foreground">
          Peer window missing seasons: {board.missingPeerSeasons.join(", ")}{" "}
          (build older play panels to widen rarity).
        </p>
      ) : null}

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading play board…</p>
      ) : !board ? (
        <p className="text-sm text-muted-foreground">
          No play highlights published for {season} week {week} yet.
          {season === latestSeason ? (
            <>
              {" "}
              Try{" "}
              <Link
                href={`/lab/plays/?season=${latestSeason}&week=${latestWeek}`}
                className="underline-offset-2 hover:underline"
              >
                week {latestWeek}
              </Link>
              .
            </>
          ) : null}
        </p>
      ) : (
        <PlayHighlightsSections
          board={board}
          season={season}
          shapes={shapes}
          resetKey={`${season}-${week}-${metricMode}`}
        />
      )}
    </main>
  );
}
