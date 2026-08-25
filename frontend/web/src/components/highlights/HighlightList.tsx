"use client";

import { useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronRight } from "lucide-react";
import type { LeagueGroupJson } from "@/lib/ballnet-store";
import type { HighlightRow } from "@/lib/payload";
import { STATS_BY_GROUP, type PositionGroup } from "@/lib/catalog";
import { formatStatValue } from "@/lib/catalog/format";
import {
  formatZScore,
  hoverSigmaStandingCopy,
  sigmaColor,
  sigmaContrastText,
  sigmaStandingParts,
  type Point,
} from "@/lib/distribution";
import { cn } from "@/lib/utils";
import { DistributionChart } from "@/components/stat-row/TremorDistribution";

function catalogDef(row: HighlightRow) {
  const group = row.positionGroup as PositionGroup;
  return STATS_BY_GROUP[group]?.find((s) => s.id === row.statId);
}

function formatHighlightValue(row: HighlightRow): string {
  const def = catalogDef(row);
  if (def) return formatStatValue(def.format, row.value);
  if (Number.isInteger(row.value)) return String(row.value);
  return row.value.toFixed(1);
}

function curveForRow(
  row: HighlightRow,
  weeklyByGroup: Record<string, LeagueGroupJson | null>,
): { curve: Point[]; xMin: number; xMax: number; yMax: number } | null {
  const shape = weeklyByGroup[row.positionGroup]?.stats?.[row.statId];
  if (!shape?.curve?.length) return null;
  return {
    curve: shape.curve,
    xMin: shape.xMin,
    xMax: shape.xMax,
    yMax: shape.yMax,
  };
}

function HighlightRowExpandable({
  row,
  season,
  weeklyByGroup,
}: {
  row: HighlightRow;
  season: number;
  weeklyByGroup: Record<string, LeagueGroupJson | null>;
}) {
  const [open, setOpen] = useState(false);
  const def = catalogDef(row);
  const higherIsBetter = def?.higherIsBetter ?? true;
  const format = def?.format ?? "one_decimal";
  const color = sigmaColor(row.zScore);
  const labelColor = sigmaContrastText(row.zScore);
  const shape = curveForRow(row, weeklyByGroup);
  const standing = sigmaStandingParts({
    label: row.statLabel,
    playerValue: row.value,
    format,
    higherIsBetter,
    zScore: row.zScore,
  });

  return (
    <li className="rounded-none border border-zinc-200 bg-white">
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
        className="flex w-full cursor-pointer items-center gap-2 px-3 py-2 text-left hover:bg-zinc-50"
      >
        <ChevronRight
          className={cn(
            "size-4 shrink-0 text-zinc-400 transition-transform duration-300",
            open && "rotate-90",
          )}
        />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-zinc-900">
            <span className="mr-2 text-xs tabular-nums text-zinc-400">
              {row.rank}
            </span>
            <Link
              href={`/players/${row.playerId}?season=${season}`}
              onClick={(e) => e.stopPropagation()}
              className="hover:underline"
            >
              {row.name}
            </Link>
          </p>
          <p className="truncate text-sm text-zinc-500">
            {row.position} · {row.team}
            {row.opponent ? ` vs ${row.opponent}` : ""} · {row.statLabel}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-sm font-semibold tabular-nums text-zinc-900">
            {formatHighlightValue(row)}
          </p>
          <p
            className="inline-block rounded-none px-1 py-0.5 text-xs font-semibold tabular-nums"
            style={{ backgroundColor: color, color: labelColor }}
          >
            {formatZScore(row.zScore)}
          </p>
        </div>
      </div>

      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            key="chart"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.38, ease: [0.32, 0.72, 0, 1] }}
            className="overflow-hidden"
          >
            <div className="border-t border-zinc-100 px-3 pb-2 pt-2">
              <p className="mb-1 text-[11px] leading-4 text-zinc-400">
                {standing.prefix}
                <span
                  className="rounded-none px-1 py-0.5 font-semibold tabular-nums"
                  style={{ backgroundColor: color, color: labelColor }}
                >
                  {standing.zLabel}
                </span>
                {standing.rest}
              </p>
              {shape ? (
                <DistributionChart
                  id={`hl-${row.rank}-${row.playerId}-${row.statId}`}
                  label={row.statLabel}
                  playerValue={row.value}
                  higherIsBetter={higherIsBetter}
                  xMin={shape.xMin}
                  xMax={shape.xMax}
                  yMax={shape.yMax}
                  format={format}
                  curve={shape.curve}
                  color={color}
                  hoverStanding={() =>
                    hoverSigmaStandingCopy(row.statLabel, row.zScore)
                  }
                />
              ) : (
                <div className="flex min-h-16 items-center justify-center rounded-none border border-dashed border-zinc-200 bg-zinc-50 px-3 py-3 text-center text-xs leading-4 text-zinc-500">
                  Waiting on a single-game league curve for this stat.
                </div>
              )}
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </li>
  );
}

type HighlightListProps = {
  rows: HighlightRow[];
  season: number;
  weeklyByGroup?: Record<string, LeagueGroupJson | null>;
  emptyLabel?: string;
};

export function HighlightList({
  rows,
  season,
  weeklyByGroup = {},
  emptyLabel = "No highlights published for this week yet.",
}: HighlightListProps) {
  if (rows.length === 0) {
    return <p className="text-sm text-zinc-500">{emptyLabel}</p>;
  }

  return (
    <ul className="space-y-1">
      {rows.map((row) => (
        <HighlightRowExpandable
          key={`${row.rank}-${row.playerId}-${row.statId}`}
          row={row}
          season={season}
          weeklyByGroup={weeklyByGroup}
        />
      ))}
    </ul>
  );
}
