"use client";

import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ChevronRight } from "lucide-react";
import type {
  LeagueStatShape,
  PlayLeagueShapesJson,
} from "@/lib/ballnet-store";
import type { PlayHighlightRow } from "@/lib/payload";
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

export const PLAY_BOARD_CLASSES = [
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

export const PLAY_CLASS_LABEL: Record<string, string> = {
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

function isEpaMode(row: PlayHighlightRow): boolean {
  return row.metricMode === "epa" || row.statId === "epa";
}

/** Raw-outcome labels for EPA rows (boards store rawValue separately). */
const RAW_OUTCOME_LABEL: Record<string, string> = {
  completion: "yard pass",
  pass: "passing yards",
  reception: "receiving yards",
  rush: "rushing yards",
  interception: "INT return yards",
  sack: "sack yards",
  kick_return: "yard kick return",
  punt_return: "yard punt return",
  field_goal: "yard field goal",
  punt: "yard punt",
  tackle_for_loss: "yard TFL",
  fumble_recovery: "yard fumble return",
};

function formatPlayValue(row: PlayHighlightRow): string {
  if (isEpaMode(row) || row.playClass === "forced_fumble") {
    return row.value.toFixed(2);
  }
  if (Number.isInteger(row.value)) return String(row.value);
  return row.value.toFixed(1);
}

function formatRawNumber(value: number): string {
  if (Number.isInteger(value)) return String(value);
  return value.toFixed(1);
}

/** e.g. "66 yard pass" — for EPA rows that still have a yards/etc. outcome. */
function formatRawOutcome(row: PlayHighlightRow): string | null {
  if (!isEpaMode(row)) return null;
  if (row.playClass === "forced_fumble") return null;
  const raw = row.rawValue;
  if (raw == null || !Number.isFinite(raw)) return null;
  const label = RAW_OUTCOME_LABEL[row.playClass];
  if (!label) return null;
  if (label.startsWith("yard ")) {
    return `${formatRawNumber(raw)} ${label}`;
  }
  return `${formatRawNumber(raw)} ${label}`;
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
    const outcome = formatRawOutcome(row);
    const epa = `${formatPlayValue(row)} EPA`;
    return outcome ? `${outcome} · ${epa}` : epa;
  }
  if (isCompletion(row) || row.statLabel.startsWith("yard ")) {
    return `${formatPlayValue(row)} ${row.statLabel}`;
  }
  if (row.playClass === "forced_fumble") {
    return `${formatPlayValue(row)} EPA forced fumble`;
  }
  return row.statLabel;
}

function downOrdinal(down: number): string | null {
  if (down === 1) return "1st";
  if (down === 2) return "2nd";
  if (down === 3) return "3rd";
  if (down === 4) return "4th";
  return null;
}

/** e.g. "2nd & 7 from ARI 25" */
function formatSituation(row: PlayHighlightRow): string | null {
  const parts: string[] = [];
  const ordinal =
    row.down != null && Number.isFinite(row.down) ? downOrdinal(row.down) : null;
  if (ordinal != null && row.distance != null && Number.isFinite(row.distance)) {
    parts.push(`${ordinal} & ${formatRawNumber(row.distance)}`);
  }
  const yardline =
    typeof row.yardline === "string" ? row.yardline.trim() : "";
  if (yardline) {
    parts.push(`from ${yardline}`);
  } else if (row.yardline100 != null && Number.isFinite(row.yardline100)) {
    parts.push(`from opp ${formatRawNumber(row.yardline100)}`);
  }
  return parts.length ? parts.join(" ") : null;
}

function yardsPhrase(yards: number, unit: string): string {
  return `${formatRawNumber(yards)} yd ${unit}`;
}

/** Class-specific outcome line; completions include air / YAC when published. */
function formatPlayOutcome(row: PlayHighlightRow): string | null {
  const parts: string[] = [];
  const yards =
    isEpaMode(row) && row.rawValue != null && Number.isFinite(row.rawValue)
      ? row.rawValue
      : !isEpaMode(row) && Number.isFinite(row.value)
        ? row.value
        : null;

  switch (row.playClass) {
    case "completion":
    case "pass":
    case "reception":
      if (yards != null) parts.push(yardsPhrase(yards, "pass"));
      if (row.airYards != null && Number.isFinite(row.airYards)) {
        parts.push(`${formatRawNumber(row.airYards)} air`);
      }
      if (
        row.yardsAfterCatch != null &&
        Number.isFinite(row.yardsAfterCatch)
      ) {
        parts.push(`${formatRawNumber(row.yardsAfterCatch)} YAC`);
      }
      break;
    case "rush":
      if (yards != null) parts.push(yardsPhrase(yards, "rush"));
      break;
    case "interception":
      if (yards != null) parts.push(yardsPhrase(yards, "INT return"));
      break;
    case "sack":
      if (yards != null) parts.push(yardsPhrase(yards, "sack"));
      break;
    case "kick_return":
      if (yards != null) parts.push(yardsPhrase(yards, "kick return"));
      break;
    case "punt_return":
      if (yards != null) parts.push(yardsPhrase(yards, "punt return"));
      break;
    case "field_goal":
      if (yards != null) parts.push(yardsPhrase(yards, "FG"));
      break;
    case "punt":
      if (yards != null) parts.push(yardsPhrase(yards, "punt"));
      break;
    case "tackle_for_loss":
      if (yards != null) parts.push(yardsPhrase(yards, "TFL"));
      break;
    case "fumble_recovery":
      if (yards != null) parts.push(yardsPhrase(yards, "fumble return"));
      break;
    case "forced_fumble":
      parts.push(`${formatPlayValue(row)} EPA`);
      break;
    default:
      break;
  }

  if (isEpaMode(row) && row.playClass !== "forced_fumble") {
    parts.push(`${formatPlayValue(row)} EPA`);
  }

  return parts.length ? parts.join(" · ") : null;
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

  const situation = formatSituation(row);
  const outcome = formatPlayOutcome(row) ?? formatHeadline(row);

  return (
    <div className="space-y-3">
      <div className="space-y-1" data-testid="play-summary">
        {situation ? (
          <p className="text-sm leading-5 text-foreground/90">{situation}</p>
        ) : null}
        <p className="text-sm leading-5 text-foreground/90">
          <span className="font-medium">{outcome}</span>
          {row.gameClock ? (
            <>
              <span className="text-muted-foreground" aria-hidden>
                {" "}
                ·{" "}
              </span>
              <span className="tabular-nums text-muted-foreground">
                {row.gameClock}
              </span>
            </>
          ) : null}
        </p>
      </div>
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
  const rawOutcome = formatRawOutcome(row);

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
            {rawOutcome ? (
              <>
                <span aria-hidden>·</span>
                <span className="font-medium text-foreground/85 tabular-nums">
                  {rawOutcome}
                </span>
              </>
            ) : null}
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

const SECTION_PREVIEW_N = 5;

type PlayHighlightListProps = {
  rows: PlayHighlightRow[];
  season: number;
  shapes: PlayLeagueShapesJson | null;
  emptyLabel: string;
};

export function PlayHighlightList({
  rows,
  season,
  shapes,
  emptyLabel,
}: PlayHighlightListProps) {
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

function PlayHighlightListPreview({
  rows,
  season,
  shapes,
  emptyLabel,
  resetKey,
  initialVisible = SECTION_PREVIEW_N,
}: PlayHighlightListProps & {
  resetKey: string;
  initialVisible?: number;
}) {
  const [expansion, setExpansion] = useState({ key: resetKey, expanded: false });
  const expanded = expansion.key === resetKey && expansion.expanded;
  const visible =
    expanded || rows.length <= initialVisible
      ? rows
      : rows.slice(0, initialVisible);
  const hiddenCount = rows.length - initialVisible;

  if (!rows.length) {
    return <p className="text-sm text-muted-foreground">{emptyLabel}</p>;
  }

  return (
    <div className="space-y-1">
      <PlayHighlightList
        rows={visible}
        season={season}
        shapes={shapes}
        emptyLabel={emptyLabel}
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

type PlayHighlightsSectionsProps = {
  board: {
    top: PlayHighlightRow[];
    byClass?: Record<string, PlayHighlightRow[]>;
  };
  season: number;
  shapes: PlayLeagueShapesJson | null;
  /** Change when season/week/metric changes so “see more” collapses again. */
  resetKey?: string;
};

export function PlayHighlightsSections({
  board,
  season,
  shapes,
  resetKey = "plays",
}: PlayHighlightsSectionsProps) {
  return (
    <div className="space-y-8">
      <section className="space-y-2">
        <h2 className="text-xs font-semibold tracking-[0.15em] text-muted-foreground uppercase">
          Top plays
        </h2>
        <PlayHighlightListPreview
          rows={board.top}
          season={season}
          shapes={shapes}
          emptyLabel="No rare plays for this week."
          resetKey={`${resetKey}-top`}
        />
      </section>
      {PLAY_BOARD_CLASSES.map((playClass) => (
        <section key={playClass} className="space-y-2">
          <h2 className="text-xs font-semibold tracking-[0.15em] text-muted-foreground uppercase">
            {PLAY_CLASS_LABEL[playClass] ?? playClass}
          </h2>
          <PlayHighlightListPreview
            rows={board.byClass?.[playClass] ?? []}
            season={season}
            shapes={shapes}
            emptyLabel={`No ${PLAY_CLASS_LABEL[playClass]?.toLowerCase() ?? playClass} yet.`}
            resetKey={`${resetKey}-${playClass}`}
          />
        </section>
      ))}
    </div>
  );
}
