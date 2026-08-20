"use client";

import { isStatReady } from "@/lib/stat-status";
import type { StatPayload } from "@/lib/distribution";
import { cn } from "@/lib/utils";
import { ExpandableStatRow, type StatRowTheme } from "./ExpandableStatRow";
import { TremorDistribution } from "./TremorDistribution";
import { UnavailableChart } from "./UnavailableChart";

export const tremorTheme: StatRowTheme = {
  shell: "border border-zinc-200 bg-white",
  header: "hover:bg-zinc-50",
  name: "text-zinc-900",
  value: "text-zinc-900 font-semibold",
  meta: "text-zinc-400",
  chartWrap: "",
  sliderTrack: "bg-zinc-100",
  sliderThumb: "border-white",
};

const flushTheme: StatRowTheme = {
  shell: "",
  header: "hover:bg-zinc-50/80",
  name: "text-zinc-900",
  value: "text-zinc-900 font-semibold",
  meta: "text-zinc-400",
  chartWrap: "",
  sliderTrack: "bg-zinc-200/70",
  sliderThumb: "border-white",
};

const nestedTheme: StatRowTheme = {
  shell: "",
  header: "hover:bg-zinc-50",
  name: "text-zinc-900",
  value: "text-zinc-900 font-semibold",
  meta: "text-zinc-400",
  chartWrap: "",
  sliderTrack: "bg-zinc-100",
  sliderThumb: "border-white",
};

const flatTheme: StatRowTheme = {
  shell: "",
  header: "hover:bg-zinc-50/50",
  name: "text-zinc-900",
  value: "text-zinc-900 font-semibold",
  meta: "text-zinc-400",
  chartWrap: "",
  sliderTrack: "bg-zinc-200/60",
  sliderThumb: "border-white",
};

export type StatStackLayout =
  | "cards"
  | "flush"
  | "section-card"
  | "ruled"
  | "sheet";

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

function StatRows({
  stats,
  theme,
  defaultOpenId,
  sliderPlacement = "below",
  rowPaddingY,
}: {
  stats: StatPayload[];
  theme: StatRowTheme;
  defaultOpenId?: string;
  sliderPlacement?: "below" | "inline";
  rowPaddingY?: number;
}) {
  return (
    <>
      {stats.map((stat) => (
        <ExpandableStatRow
          key={stat.id}
          stat={stat}
          theme={theme}
          sliderPlacement={sliderPlacement}
          rowPaddingY={rowPaddingY}
          defaultOpen={stat.id === defaultOpenId}
          chart={
            isStatReady(stat) ? (
              <TremorDistribution stat={stat} />
            ) : (
              <UnavailableChart stat={stat} />
            )
          }
        />
      ))}
    </>
  );
}

export function StatStack({
  stats,
  layout = "cards",
  sliderPlacement = "below",
  defaultOpenId,
  rowPaddingY,
  sectionGap,
  headingGap,
}: {
  stats: StatPayload[];
  layout?: StatStackLayout;
  sliderPlacement?: "below" | "inline";
  defaultOpenId?: string;
  rowPaddingY?: number;
  sectionGap?: number;
  headingGap?: number;
}) {
  const sections = groupBySection(stats);
  const rowProps = { sliderPlacement, defaultOpenId, rowPaddingY };
  const stackStyle =
    sectionGap != null ? { gap: sectionGap } : undefined;
  const headingStyle =
    headingGap != null ? { marginBottom: headingGap } : undefined;

  if (layout === "sheet") {
    return (
      <div className="overflow-hidden border border-zinc-200 bg-white">
        {sections.map((section, index) => (
          <section
            key={section.title}
            className={cn(index > 0 && "border-t border-zinc-200")}
          >
            <h2
              className="px-4 text-xs font-semibold tracking-[0.2em] text-zinc-500 uppercase"
              style={
                headingGap != null
                  ? { paddingTop: headingGap, paddingBottom: Math.max(2, headingGap / 2) }
                  : { paddingTop: 20, paddingBottom: 4 }
              }
            >
              {section.title}
            </h2>
            <div className="divide-y divide-zinc-100">
              <StatRows
                stats={section.stats}
                theme={nestedTheme}
                {...rowProps}
              />
            </div>
          </section>
        ))}
      </div>
    );
  }

  return (
    <div
      className={cn("flex flex-col", sectionGap == null && "gap-2")}
      style={stackStyle}
    >
      {sections.map((section) => {
        if (layout === "section-card") {
          return (
            <section key={section.title}>
              <h2
                className="text-xs font-semibold tracking-[0.2em] text-zinc-500 uppercase"
                style={headingStyle ?? { marginBottom: 8 }}
              >
                {section.title}
              </h2>
              <div className="divide-y divide-zinc-100 overflow-hidden border border-zinc-200 bg-white">
                <StatRows
                  stats={section.stats}
                  theme={nestedTheme}
                  {...rowProps}
                />
              </div>
            </section>
          );
        }

        if (layout === "flush") {
          return (
            <section key={section.title}>
              <h2
                className="text-xs font-semibold tracking-[0.2em] text-zinc-500 uppercase"
                style={headingStyle ?? { marginBottom: 4 }}
              >
                {section.title}
              </h2>
              <div className="divide-y divide-zinc-200">
                <StatRows
                  stats={section.stats}
                  theme={flushTheme}
                  {...rowProps}
                />
              </div>
            </section>
          );
        }

        if (layout === "ruled") {
          return (
            <section key={section.title}>
              <h2
                className="text-xs font-semibold tracking-[0.2em] text-zinc-500 uppercase"
                style={headingStyle ?? { marginBottom: 4 }}
              >
                {section.title}
              </h2>
              <div>
                <StatRows
                  stats={section.stats}
                  theme={flatTheme}
                  {...rowProps}
                />
              </div>
            </section>
          );
        }

        return (
          <section key={section.title} className="flex flex-col gap-1">
            <h2 className="text-xs font-semibold tracking-[0.2em] text-zinc-500 uppercase">
              {section.title}
            </h2>
            <StatRows
              stats={section.stats}
              theme={tremorTheme}
              {...rowProps}
            />
          </section>
        );
      })}
    </div>
  );
}

export function TremorVariant({
  stats,
  defaultOpenId,
}: {
  stats: StatPayload[];
  defaultOpenId?: string;
}) {
  return (
    <StatStack
      stats={stats}
      layout="ruled"
      sliderPlacement="inline"
      rowPaddingY={0}
      sectionGap={0}
      headingGap={0}
      defaultOpenId={defaultOpenId}
    />
  );
}
