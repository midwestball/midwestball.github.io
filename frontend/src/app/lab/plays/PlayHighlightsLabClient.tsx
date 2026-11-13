"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ChevronRight } from "lucide-react";
import { writeBrowserQuery } from "@/components/share/browser-query";
import { patchQuery } from "@/lib/share-state/common";
import {
  fetchCurrentMeta,
  fetchPlayHighlightsBoard,
  fetchPlayLeagueShapes,
  type LeagueStatShape,
  type PlayLeagueShapesJson,
} from "@/lib/ballnet-store";
import type {
  PlayHighlightRow,
  PlayHighlightsBoardJson,
  PlayMetricMode,
} from "@/lib/payload";
import {
  formatOneInN,
  rarityStandingParts,
  rarityTierColor,
  rarityTierContrastText,
  rarityTierShimmer,
  resolveRarityTier,
} from "@/lib/distribution";
import { PlayerComparisonLink } from "@/components/PlayerComparisonLink";
import { TeamAbbr } from "@/components/TeamAbbr";
import { HistogramChart } from "@/components/stat-row/HistogramChart";
import { cn } from "@/lib/utils";

const BOARD_CLASSES = [
  "completion",
  "rush",
  "interception",
  "sack",
  "kick_return",
  "punt_return",
  "field_goal",
  "punt",
  "tackle_for_loss",
  "fumble_recovery",
  "forced_fumble",
] as const;

const CLASS_LABEL: Record<string, string> = {
  completion: "Completions",
  rush: "Rushes",
  interception: "Interceptions",
  sack: "Sacks",
  kick_return: "Kick returns",
  punt_return: "Punt returns",
  field_goal: "Field goals",
  punt: "Punts",
  tackle_for_loss: "Tackles for loss",
  fumble_recovery: "Fumble recoveries",
  forced_fumble: "Forced fumbles",
};

function regWeeksInSeason(season: number): number {
  return season >= 2021 ? 18 : 17;
}

function isEpaMode(row: PlayHighlightRow): boolean {
  return row.metricMode === "epa" || row.statId === "epa";
}

function formatPlayValue(row: PlayHighlightRow): string {
  if (isEpaMode(row) || row.playClass === "forced_fumble") {
    return row.value.toFixed(2);
  }
  if (Number.isInteger(row.value)) return String(row.value);
  return row.value.toFixed(1);
}

function valueFormat(row: PlayHighlightRow): "count" | "one_decimal" {
  return isEpaMode(row) || row.playClass === "forced_fumble"
    ? "one_decimal"
    : "count";
}

function isCompletion(row: PlayHighlightRow): boolean {
  return (
    row.playClass === "completion" &&
    Boolean(row.passerId) &&
    Boolean(row.receiverId)
  );
}

function CompletionTitle({
  row,
  season,
}: {
  row: PlayHighlightRow;
  season: number;
}) {
  return (
    <>
      <PlayerComparisonLink playerId={row.passerId!} season={season}>
        {row.passerName || "Passer"}
      </PlayerComparisonLink>
      <span className="mx-1 text-muted-foreground" aria-hidden>
        →
      </span>
      <PlayerComparisonLink playerId={row.receiverId!} season={season}>
        {row.receiverName || "Receiver"}
      </PlayerComparisonLink>
    </>
  );
}

function formatHeadline(row: PlayHighlightRow): string {
  if (isEpaMode(row)) {
    return `${formatPlayValue(row)} EPA`;
  }
  if (isCompletion(row) || row.statLabel.startsWith("yard ")) {
    return `${formatPlayValue(row)} ${row.statLabel}`;
  }
  if (row.playClass === "forced_fumble") {
    return `${formatPlayValue(row)} EPA forced fumble`;
  }
  return row.statLabel;
}

function peerBucketCopy(row: PlayHighlightRow): string {
  if (row.playClass === "completion") {
    const primary =
      row.peerKey?.startsWith("reception|")
        ? `receptions by ${row.receiverPosition || row.position || "receiver"}`
        : row.peerKey?.startsWith("pass|")
          ? `completions by ${row.passerPosition || "QB"}`
          : "completions";
    return primary;
  }
  if (row.peerKey?.includes("|pos:")) {
    return `${row.playClass} plays by ${row.position}`;
  }
  if (row.peerKey?.includes("|group:")) {
    return `${row.playClass} plays in this position group`;
  }
  return `${row.playClass} plays`;
}

function RarityChip({ tier }: { tier: number }) {
  const color = rarityTierColor(tier);
  const labelColor = rarityTierContrastText(tier);
  return (
    <span
      className={cn(
        "inline-block rounded-none px-1 py-0.5 text-xs font-semibold tabular-nums",
        rarityTierShimmer(tier) && "rarity-chip-shimmer",
      )}
      style={{ backgroundColor: color, color: labelColor }}
    >
      {formatOneInN(tier)}
    </span>
  );
}

function shapeForKey(
  peerKey: string | undefined,
  shapes: PlayLeagueShapesJson | null,
): LeagueStatShape | null {
  if (!shapes || !peerKey) return null;
  return shapes.stats?.[peerKey] ?? null;
}

function HistogramBlock({
  label,
  markerName,
  value,
  peerKey,
  favorableCount,
  peerN,
  bucketCopy,
  tier,
  shapes,
  format = "count",
}: {
  label: string;
  markerName: string;
  value: number;
  peerKey?: string;
  favorableCount?: number;
  peerN?: number;
  bucketCopy: string;
  tier: number | null | undefined;
  shapes: PlayLeagueShapesJson | null;
  format?: "count" | "one_decimal";
}) {
  const shape = shapeForKey(peerKey, shapes);
  const color = tier != null ? rarityTierColor(tier) : "rgb(161, 161, 170)";
  const labelColor =
    tier != null ? rarityTierContrastText(tier) : "#ffffff";
  const standing =
    tier != null
      ? rarityStandingParts({
          label,
          playerValue: value,
          format,
          higherIsBetter: true,
          rarityTier: tier,
        })
      : null;

  return (
    <div className="space-y-1">
      <p className="text-[11px] font-semibold tracking-[0.08em] text-muted-foreground uppercase">
        {label}
      </p>
      {standing && tier != null ? (
        <p className="text-[11px] leading-4 text-muted-foreground">
          {standing.prefix}
          <span
            className={cn(
              "rounded-none px-1 py-0.5 font-semibold tabular-nums",
              rarityTierShimmer(tier) && "rarity-chip-shimmer",
            )}
            style={{ backgroundColor: color, color: labelColor }}
          >
            {standing.rarityLabel}
          </span>
          {standing.rest}
        </p>
      ) : null}
      {favorableCount != null && peerN != null ? (
        <p className="text-xs text-text-secondary">
          {favorableCount} of {peerN} qualifying {bucketCopy} were at least
          this favorable.
        </p>
      ) : null}
      {shape?.bins?.length ? (
        <HistogramChart
          label={label}
          bins={shape.bins}
          format={format}
          markers={[{ name: markerName, value, color }]}
          interactive
          shadeColor={color}
        />
      ) : (
        <div className="flex min-h-16 items-center justify-center rounded-none border border-dashed border-border bg-muted px-3 py-3 text-center text-xs leading-4 text-muted-foreground">
          Waiting on a play-level peer histogram for this bucket.
        </div>
      )}
    </div>
  );
}

function PerformanceBlock({
  row,
  shapes,
}: {
  row: PlayHighlightRow;
  shapes: PlayLeagueShapesJson | null;
}) {
  const tier = resolveRarityTier(row);
  const secondaryTier = row.secondaryRarityTier ?? null;
  const primaryLabel =
    row.playClass === "completion"
      ? row.peerKey?.startsWith("reception|")
        ? `As catch (${row.receiverPosition || "receiver"})`
        : `As throw (${row.passerPosition || "QB"})`
      : row.statLabel;
  const secondaryLabel =
    row.secondaryRole === "reception"
      ? `As catch (${row.receiverPosition || "receiver"})`
      : row.secondaryRole === "pass"
        ? `As throw (${row.passerPosition || "QB"})`
        : "Other perspective";

  return (
    <div className="space-y-3">
      <p className="text-[11px] leading-4 text-muted-foreground">
        <span className="font-medium text-text-secondary">
          {formatHeadline(row)}
        </span>
        {row.gameClock ? (
          <>
            <span aria-hidden> · </span>
            <span className="tabular-nums">{row.gameClock}</span>
          </>
        ) : null}
      </p>
      <HistogramBlock
        label={primaryLabel}
        markerName={
          isCompletion(row)
            ? row.peerKey?.startsWith("reception|")
              ? row.receiverName || row.name
              : row.passerName || row.name
            : row.name
        }
        value={row.value}
        peerKey={row.peerKey}
        favorableCount={row.favorableCount}
        peerN={row.peerN}
        bucketCopy={peerBucketCopy(row)}
        tier={tier}
        shapes={shapes}
        format={valueFormat(row)}
      />
      {row.secondaryPeerKey ? (
        <HistogramBlock
          label={secondaryLabel}
          markerName={
            row.secondaryRole === "reception"
              ? row.receiverName || row.name
              : row.passerName || row.name
          }
          value={row.value}
          peerKey={row.secondaryPeerKey}
          favorableCount={row.secondaryFavorableCount}
          peerN={row.secondaryPeerN}
          bucketCopy={
            row.secondaryRole === "reception"
              ? `receptions by ${row.receiverPosition || "receiver"}`
              : `completions by ${row.passerPosition || "QB"}`
          }
          tier={secondaryTier}
          shapes={shapes}
          format={valueFormat(row)}
        />
      ) : null}
    </div>
  );
}

function PlayRowExpandable({
  row,
  season,
  shapes,
}: {
  row: PlayHighlightRow;
  season: number;
  shapes: PlayLeagueShapesJson | null;
}) {
  const reduceMotion = useReducedMotion();
  const [open, setOpen] = useState(false);
  const tier = resolveRarityTier(row);
  const clock = row.gameClock ?? (row.clock ? `Q? ${row.clock}` : null);
  const also = row.also ?? [];

  return (
    <li className="rounded-none border border-border bg-card">
      <div
        role="button"
        tabIndex={0}
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setOpen((current) => !current);
          }
        }}
        className="flex w-full cursor-pointer items-center gap-2 px-3 py-2 text-left hover:bg-muted"
      >
        <ChevronRight
          className={cn(
            "size-4 shrink-0 text-muted-foreground transition-transform duration-300",
            open && "rotate-90",
          )}
        />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-foreground">
            <span className="mr-2 text-xs tabular-nums text-muted-foreground">
              {row.rank}
            </span>
            {isCompletion(row) ? (
              <CompletionTitle row={row} season={season} />
            ) : (
              <PlayerComparisonLink playerId={row.playerId} season={season}>
                {row.name}
              </PlayerComparisonLink>
            )}
          </p>
          <p className="flex flex-wrap items-center gap-x-1.5 text-sm text-muted-foreground">
            <span>
              {isCompletion(row)
                ? `${row.passerPosition || "QB"} → ${row.receiverPosition || row.position || "—"}`
                : row.position || "—"}
            </span>
            <span aria-hidden>·</span>
            <TeamAbbr team={row.team} />
            {row.opponent ? (
              <>
                <span aria-hidden>vs</span>
                <TeamAbbr team={row.opponent} />
              </>
            ) : null}
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
            {also.length > 0 ? (
              <span className="text-muted-foreground">+{also.length} more</span>
            ) : null}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-sm font-semibold text-foreground">
            <span className="tabular-nums">{formatPlayValue(row)}</span>{" "}
            <span className="font-medium text-muted-foreground">
              {isEpaMode(row) ? "EPA" : row.statLabel}
            </span>
          </p>
          {tier != null ? <RarityChip tier={tier} /> : null}
        </div>
      </div>

      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            key="chart"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{
              duration: reduceMotion ? 0 : 0.21,
              ease: [0.32, 0.72, 0, 1],
            }}
            className="overflow-hidden"
          >
            <div className="space-y-3 border-t border-border px-3 pb-2 pt-2">
              <PerformanceBlock row={row} shapes={shapes} />
              {also.length > 0 ? (
                <div className="space-y-3 border-t border-border pt-2">
                  <p className="text-[11px] font-semibold tracking-[0.12em] text-muted-foreground uppercase">
                    Also this week
                  </p>
                  {also.map((secondary) => (
                    <PerformanceBlock
                      key={`${secondary.playerId}-${secondary.playId}-${secondary.playClass}`}
                      row={secondary}
                      shapes={shapes}
                    />
                  ))}
                </div>
              ) : null}
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </li>
  );
}

function PlayList({
  rows,
  season,
  shapes,
  emptyLabel,
}: {
  rows: PlayHighlightRow[];
  season: number;
  shapes: PlayLeagueShapesJson | null;
  emptyLabel: string;
}) {
  if (!rows.length) {
    return <p className="text-sm text-muted-foreground">{emptyLabel}</p>;
  }
  return (
    <ul className="space-y-1">
      {rows.map((row) => (
        <PlayRowExpandable
          key={`${row.rank}-${row.playerId}-${row.playId}-${row.playClass}`}
          row={row}
          season={season}
          shapes={shapes}
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
          Expand a row for the peer histogram — same idea as home game
          highlights.
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
              ["raw", "Raw stat"],
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
        <div className="space-y-8">
          <section className="space-y-2">
            <h2 className="text-sm font-semibold tracking-[0.08em] text-muted-foreground uppercase">
              Top plays
            </h2>
            <PlayList
              rows={board.top}
              season={season}
              shapes={shapes}
              emptyLabel="No rare plays for this week."
            />
          </section>
          {BOARD_CLASSES.map((playClass) => (
            <section key={playClass} className="space-y-2">
              <h2 className="text-sm font-semibold tracking-[0.08em] text-muted-foreground uppercase">
                {CLASS_LABEL[playClass] ?? playClass}
              </h2>
              <PlayList
                rows={board.byClass?.[playClass] ?? []}
                season={season}
                shapes={shapes}
                emptyLabel={`No ${CLASS_LABEL[playClass]?.toLowerCase() ?? playClass} yet.`}
              />
            </section>
          ))}
        </div>
      )}
    </main>
  );
}
