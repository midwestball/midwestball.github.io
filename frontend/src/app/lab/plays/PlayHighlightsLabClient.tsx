"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { writeBrowserQuery } from "@/components/share/browser-query";
import { patchQuery } from "@/lib/share-state/common";
import {
  fetchCurrentMeta,
  fetchPlayHighlightsBoard,
} from "@/lib/ballnet-store";
import type { PlayHighlightRow, PlayHighlightsBoardJson } from "@/lib/payload";
import {
  formatOneInN,
  rarityTierColor,
  rarityTierContrastText,
  rarityTierShimmer,
  resolveRarityTier,
} from "@/lib/distribution";
import { PlayerComparisonLink } from "@/components/PlayerComparisonLink";
import { TeamAbbr } from "@/components/TeamAbbr";
import { cn } from "@/lib/utils";

const PLAY_CLASSES = [
  "reception",
  "rush",
  "pass",
  "interception",
  "sack",
] as const;

const CLASS_LABEL: Record<string, string> = {
  reception: "Receptions",
  rush: "Rushes",
  pass: "Pass completions",
  interception: "Interceptions",
  sack: "Sacks",
};

function regWeeksInSeason(season: number): number {
  return season >= 2021 ? 18 : 17;
}

function formatPlayValue(row: PlayHighlightRow): string {
  if (Number.isInteger(row.value)) return String(row.value);
  return row.value.toFixed(1);
}

function RarityChip({ tier }: { tier: number }) {
  const color = rarityTierColor(tier);
  const labelColor = rarityTierContrastText(tier);
  return (
    <span
      className={cn(
        "inline-block rounded-none border-0 px-1 py-0.5 text-xs font-semibold tabular-nums",
        rarityTierShimmer(tier) && "rarity-chip-shimmer",
      )}
      style={{ backgroundColor: color, color: labelColor }}
    >
      {formatOneInN(tier)}
    </span>
  );
}

function PlayRow({ row, season }: { row: PlayHighlightRow; season: number }) {
  const tier = resolveRarityTier(row);
  const clock = row.gameClock ?? (row.clock ? `Q? ${row.clock}` : null);

  return (
    <li className="rounded-none border border-border bg-card px-3 py-2">
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <p className="font-medium text-foreground">
            <span className="mr-2 text-xs tabular-nums text-muted-foreground">
              {row.rank}
            </span>
            <PlayerComparisonLink playerId={row.playerId} season={season}>
              {row.name}
            </PlayerComparisonLink>
          </p>
          <p className="flex flex-wrap items-center gap-x-1.5 text-sm text-muted-foreground">
            <span>{row.position || "—"}</span>
            <span aria-hidden>·</span>
            <TeamAbbr team={row.team} />
            {row.opponent ? (
              <>
                <span aria-hidden>vs</span>
                <TeamAbbr team={row.opponent} />
              </>
            ) : null}
            <span aria-hidden>·</span>
            <span className="truncate">{row.statLabel}</span>
            {clock ? (
              <>
                <span aria-hidden>·</span>
                <span className="tabular-nums text-foreground/80">{clock}</span>
              </>
            ) : null}
            {row.touchdown ? (
              <>
                <span aria-hidden>·</span>
                <span className="font-medium text-foreground">TD</span>
              </>
            ) : null}
          </p>
          {row.description ? (
            <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
              {row.description}
            </p>
          ) : null}
        </div>
        <div className="shrink-0 text-right">
          <p className="text-sm font-semibold tabular-nums text-foreground">
            {formatPlayValue(row)}
          </p>
          {tier != null ? <RarityChip tier={tier} /> : null}
        </div>
      </div>
    </li>
  );
}

function PlayList({
  rows,
  season,
  emptyLabel,
}: {
  rows: PlayHighlightRow[];
  season: number;
  emptyLabel: string;
}) {
  if (!rows.length) {
    return <p className="text-sm text-muted-foreground">{emptyLabel}</p>;
  }
  return (
    <ul className="space-y-1">
      {rows.map((row) => (
        <PlayRow
          key={`${row.rank}-${row.playerId}-${row.playId}-${row.playClass}`}
          row={row}
          season={season}
        />
      ))}
    </ul>
  );
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

  // Static export freezes SSR props; refresh from Storage like home highlights.
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
  const [board, setBoard] = useState<PlayHighlightsBoardJson | null>(null);
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
    (nextSeason: number, nextWeek: number) => {
      writeBrowserQuery(
        patchQuery(searchParams, {
          season: String(nextSeason),
          week: String(nextWeek),
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
      const next = await fetchPlayHighlightsBoard(season, week);
      if (cancelled) return;
      setBoard(next);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [season, week]);

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
          Individual plays ranked within type (and position when available)
          against all-time peers. Only weeks you have uploaded under{" "}
          <code className="text-xs">highlights/plays/</code> will show rows —
          right now that is typically just the week you published.
        </p>
        <p className="text-xs text-muted-foreground">
          <Link href="/" className="underline-offset-2 hover:underline">
            ← Home game highlights
          </Link>
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
              syncUrl(nextSeason, nextWeek);
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
              syncUrl(season, nextWeek);
            }}
          >
            {weeks.map((w) => (
              <option key={w} value={w}>
                {w}
              </option>
            ))}
          </select>
        </label>
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
              Try week {latestWeek} if that is what you uploaded, or open{" "}
              <Link
                href={`/lab/plays/?season=${latestSeason}&week=${latestWeek}`}
                className="underline-offset-2 hover:underline"
              >
                /lab/plays/?season={latestSeason}&week={latestWeek}
              </Link>
              .
            </>
          ) : null}
        </p>
      ) : (
        <div className="space-y-8">
          <section className="space-y-2">
            <h2 className="text-sm font-semibold tracking-[0.08em] text-muted-foreground uppercase">
              Top plays
            </h2>
            <PlayList
              rows={board.top}
              season={season}
              emptyLabel="No rare plays for this week."
            />
          </section>
          {PLAY_CLASSES.map((playClass) => (
            <section key={playClass} className="space-y-2">
              <h2 className="text-sm font-semibold tracking-[0.08em] text-muted-foreground uppercase">
                {CLASS_LABEL[playClass] ?? playClass}
              </h2>
              <PlayList
                rows={board.byClass?.[playClass] ?? []}
                season={season}
                emptyLabel={`No ${CLASS_LABEL[playClass]?.toLowerCase() ?? playClass} yet.`}
              />
            </section>
          ))}
        </div>
      )}
    </main>
  );
}
