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
    <div className={cn(!ready && "opacity-70")}>
      <button
        type="button"
        aria-expanded={open}
        onClick={onToggle}
        className="flex w-full items-center gap-2 px-2 py-1 text-left hover:bg-zinc-50/80"
      >
        <ChevronRight
          className={cn(
            "size-4 shrink-0 transition-transform duration-300",
            open && "rotate-90",
            !ready && "text-zinc-400",
          )}
        />
        <span
          className={cn(
            "w-[4.75rem] shrink-0 truncate text-left text-sm font-semibold tabular-nums text-zinc-900",
            !ready && "font-normal text-zinc-400",
          )}
        >
          {stat.playerValue == null
            ? "—"
            : formatStatValue(stat.format, stat.playerValue)}
        </span>
        <div className="min-w-0 flex-1">
          <PercentileSlider
            stat={stat}
            disabled={!ready}
            alignWithChart={false}
            trackClassName="bg-zinc-200/60"
            thumbClassName="border-white"
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
    <div className="overflow-x-auto">
      <div
        className="min-w-[40rem]"
        style={{
          display: "grid",
          gridTemplateColumns: `10.5rem repeat(${colCount}, minmax(11rem, 1fr))`,
        }}
      >
        <div className="border-b border-zinc-200 px-2 py-2" />
        {columns.map((col) => (
          <div
            key={col.playerId}
            className="border-b border-l border-zinc-200 px-2 py-2"
          >
            <div className="min-w-0 px-2 py-0">
              <p className="truncate text-sm font-semibold text-zinc-900">
                {col.name}
              </p>
              <p className="flex flex-wrap items-center gap-x-1.5 truncate text-xs text-zinc-500">
                <span>{col.position}</span>
                <span aria-hidden>·</span>
                <TeamAbbr team={col.team} />
              </p>
            </div>
          </div>
        ))}

        {sections.map((section) => (
          <div key={section.title} className="contents">
            <div className="col-span-full px-2 pt-3 pb-1">
              <h2 className="text-xs font-semibold tracking-[0.2em] text-zinc-500 uppercase">
                {section.title}
              </h2>
            </div>
            {section.stats.map((templateStat) => {
              const open = openStatId === templateStat.id;
              return (
                <div key={templateStat.id} className="contents">
                  <div className="flex items-start border-t border-zinc-100 px-2 py-1">
                    <button
                      type="button"
                      aria-expanded={open}
                      onClick={() => toggleStat(templateStat.id)}
                      className="flex w-full items-start gap-1 py-1 text-left text-sm font-medium text-zinc-900 hover:bg-zinc-50/80"
                    >
                      <ChevronRight
                        className={cn(
                          "mt-0.5 size-4 shrink-0 transition-transform duration-300",
                          open && "rotate-90",
                        )}
                      />
                      <span className="leading-5" title={templateStat.label}>
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
                        className="border-t border-l border-zinc-100"
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
                          <div className="px-3 py-3">
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
