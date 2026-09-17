"use client";

import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronRight } from "lucide-react";
import { formatStatValue } from "@/lib/catalog/format";
import type { StatPayload } from "@/lib/distribution";
import { isStatReady } from "@/lib/stat-status";
import { compareFillColor } from "@/lib/team-colors";
import { cn } from "@/lib/utils";
import { PercentileSlider } from "@/components/stat-row/PercentileSlider";
import { TeamAbbr } from "@/components/TeamAbbr";
import {
  CompareOverlayChart,
  shortPlayerName,
  type OverlayMarker,
} from "./CompareOverlayChart";

export type CompareColumn = {
  playerId: string;
  name: string;
  position: string;
  team: string;
  stats: StatPayload[];
};

function meanReadyPercentile(stats: StatPayload[]): number {
  let sum = 0;
  let n = 0;
  for (const stat of stats) {
    if (isStatReady(stat) && stat.percentile != null) {
      sum += stat.percentile;
      n += 1;
    }
  }
  return n === 0 ? 50 : sum / n;
}

function groupBySection(stats: StatPayload[]) {
  const sections: { title: string; stats: StatPayload[] }[] = [];
  const byTitle = new Map<string, StatPayload[]>();
  for (const stat of stats) {
    const existing = byTitle.get(stat.section);
    if (existing) {
      existing.push(stat);
      continue;
    }
    const next = [stat];
    byTitle.set(stat.section, next);
    sections.push({ title: stat.section, stats: next });
  }
  return sections;
}

function CompareCell({
  stat,
  open,
  onToggle,
}: {
  stat: StatPayload;
  open: boolean;
  onToggle: () => void;
}) {
  const ready = isStatReady(stat);

  return (
    <div className={cn("h-full min-w-0", !ready && "opacity-70")}>
      <button
        type="button"
        aria-expanded={open}
        onClick={onToggle}
        className="flex h-full w-full min-w-0 flex-col items-stretch justify-center gap-0.5 px-1 py-1 text-left hover:bg-zinc-50/80 md:flex-row md:items-center md:gap-2 md:px-2"
      >
        <ChevronRight
          className={cn(
            "hidden size-4 shrink-0 transition-transform duration-300 md:block",
            open && "rotate-90",
            !ready && "text-zinc-400",
          )}
        />
        <span
          className={cn(
            "min-w-0 truncate text-left text-[11px] font-semibold tabular-nums text-zinc-900 md:w-[4.75rem] md:shrink-0 md:text-sm",
            !ready && "font-normal text-zinc-400",
          )}
        >
          {stat.playerValue == null
            ? "—"
            : formatStatValue(stat.format, stat.playerValue)}
        </span>
        <div className="min-w-0 w-full flex-1">
          <PercentileSlider
            stat={stat}
            disabled={!ready}
            alignWithChart={false}
            className="max-md:px-2"
            trackClassName="bg-zinc-200/60"
            thumbClassName="border-white max-md:size-5 max-md:text-[9px]"
          />
        </div>
      </button>
    </div>
  );
}

export function CompareBoard({ columns }: { columns: CompareColumn[] }) {
  const [openStatId, setOpenStatId] = useState<string | null>(null);

  const fills = useMemo(() => {
    const scores = columns.map((col) => ({
      playerId: col.playerId,
      team: col.team,
      score: meanReadyPercentile(col.stats),
    }));
    const byTeam = new Map<string, number[]>();
    for (const row of scores) {
      const list = byTeam.get(row.team) ?? [];
      list.push(row.score);
      byTeam.set(row.team, list);
    }
    const out = new Map<string, string>();
    for (const row of scores) {
      out.set(
        row.playerId,
        compareFillColor(
          row.team,
          row.score,
          byTeam.get(row.team) ?? [row.score],
        ),
      );
    }
    return out;
  }, [columns]);

  const template = columns[0]?.stats ?? [];
  const sections = groupBySection(template);
  const colCount = columns.length;

  function toggleStat(statId: string) {
    setOpenStatId((current) => (current === statId ? null : statId));
  }

  function markersFor(
    statId: string,
    templateStat: StatPayload,
  ): OverlayMarker[] {
    return columns.map((col) => {
      const stat = col.stats.find((s) => s.id === statId) ?? templateStat;
      return {
        playerId: col.playerId,
        name: col.name,
        color: fills.get(col.playerId) ?? "#52525b",
        stat,
      };
    });
  }

  if (colCount === 0) return null;

  return (
    <div className="md:overflow-x-auto">
      <div
        className="compare-board-grid grid w-full md:min-w-[40rem]"
        style={
          { "--compare-cols": String(colCount) } as React.CSSProperties
        }
      >
        <div className="border-b border-zinc-200 px-1 py-2 md:px-2" />
        {columns.map((col) => (
          <div
            key={col.playerId}
            className="min-w-0 border-b border-l border-zinc-200 px-1 py-2 md:px-2"
          >
            <div className="min-w-0 px-0 py-0 md:px-2">
              <p className="truncate text-xs font-semibold text-zinc-900 md:text-sm">
                <span className="md:hidden">{shortPlayerName(col.name)}</span>
                <span className="hidden md:inline">{col.name}</span>
              </p>
              <p className="flex flex-wrap items-center gap-x-1 truncate text-[10px] text-zinc-500 md:gap-x-1.5 md:text-xs">
                <span>{col.position}</span>
                <span aria-hidden>·</span>
                <TeamAbbr team={col.team} />
              </p>
            </div>
          </div>
        ))}

        {sections.map((section) => (
          <div key={section.title} className="contents">
            <div className="col-span-full px-1 pt-3 pb-1 md:px-2">
              <h2 className="text-xs font-semibold tracking-[0.2em] text-zinc-500 uppercase">
                {section.title}
              </h2>
            </div>
            {section.stats.map((templateStat) => {
              const open = openStatId === templateStat.id;
              return (
                <div key={templateStat.id} className="contents">
                  <div className="flex min-w-0 items-start border-t border-zinc-100 px-1 py-1 md:px-2">
                    <button
                      type="button"
                      aria-expanded={open}
                      onClick={() => toggleStat(templateStat.id)}
                      className="flex w-full min-w-0 items-start gap-0.5 py-1 text-left text-xs font-medium text-zinc-900 hover:bg-zinc-50/80 md:gap-1 md:text-sm"
                    >
                      <ChevronRight
                        className={cn(
                          "mt-0.5 size-3.5 shrink-0 transition-transform duration-300 md:size-4",
                          open && "rotate-90",
                        )}
                      />
                      <span
                        className="min-w-0 leading-4 break-words md:leading-5"
                        title={templateStat.label}
                      >
                        {templateStat.label}
                      </span>
                    </button>
                  </div>
                  {columns.map((col) => {
                    const stat =
                      col.stats.find((s) => s.id === templateStat.id) ??
                      templateStat;
                    return (
                      <div
                        key={`${col.playerId}-${templateStat.id}`}
                        className="min-w-0 border-t border-l border-zinc-100"
                      >
                        <CompareCell
                          stat={stat}
                          open={open}
                          onToggle={() => toggleStat(templateStat.id)}
                        />
                      </div>
                    );
                  })}
                  <div className="col-span-full overflow-hidden border-t border-zinc-100">
                    <AnimatePresence initial={false}>
                      {open ? (
                        <motion.div
                          key={`chart-${templateStat.id}`}
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{
                            duration: 0.38,
                            ease: [0.32, 0.72, 0, 1],
                          }}
                        >
                          <div className="px-2 py-3 md:px-3">
                            <CompareOverlayChart
                              markers={markersFor(
                                templateStat.id,
                                templateStat,
                              )}
                              fills={fills}
                            />
                          </div>
                        </motion.div>
                      ) : null}
                    </AnimatePresence>
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
