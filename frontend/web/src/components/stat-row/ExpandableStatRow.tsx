"use client";

import { useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronRight } from "lucide-react";
import { formatStatValue } from "@/lib/catalog/format";
import {
  percentileColor,
  percentileContrastText,
  playerStandingParts,
  type StatPayload,
} from "@/lib/distribution";
import { isStatReady } from "@/lib/stat-status";
import { cn } from "@/lib/utils";
import { PercentileSlider } from "./PercentileSlider";

export type StatRowTheme = {
  shell: string;
  header: string;
  name: string;
  value: string;
  meta: string;
  chartWrap: string;
  sliderTrack?: string;
  sliderThumb?: string;
};

type ExpandableStatRowProps = {
  stat: StatPayload;
  theme: StatRowTheme;
  chart: ReactNode;
  defaultOpen?: boolean;
  sliderPlacement?: "below" | "inline";
  rowPaddingY?: number;
};

export function ExpandableStatRow({
  stat,
  theme,
  chart,
  defaultOpen = false,
  sliderPlacement = "below",
  rowPaddingY,
}: ExpandableStatRowProps) {
  const [open, setOpen] = useState(defaultOpen);
  const ready = isStatReady(stat);
  const color =
    ready && stat.percentile != null
      ? percentileColor(stat.percentile)
      : undefined;
  const labelColor =
    ready && stat.percentile != null
      ? percentileContrastText(stat.percentile)
      : undefined;
  const standing = ready ? playerStandingParts(stat) : null;
  const inline = sliderPlacement === "inline";

  // Fixed width so value starts and slider starts share a column across rows.
  const value = (
    <span
      className={cn(
        "w-[4.75rem] shrink-0 truncate text-left tabular-nums",
        theme.value,
        !ready && "font-normal text-zinc-400",
      )}
    >
      {stat.playerValue == null
        ? "—"
        : formatStatValue(stat.format, stat.playerValue)}
    </span>
  );

  const slider = (
    <PercentileSlider
      stat={stat}
      disabled={!ready}
      alignWithChart={!inline}
      trackClassName={theme.sliderTrack}
      thumbClassName={theme.sliderThumb}
    />
  );

  return (
    <div
      className={cn("overflow-hidden", theme.shell, !ready && "opacity-70")}
    >
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className={cn(
          "flex w-full items-center gap-2 px-2 text-left",
          rowPaddingY == null && (inline ? "py-1.5" : "py-2"),
          theme.header,
        )}
        style={
          rowPaddingY != null
            ? { paddingTop: rowPaddingY, paddingBottom: rowPaddingY }
            : undefined
        }
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
            "truncate font-medium",
            inline ? "w-[12.5rem] shrink-0" : "min-w-0 flex-1",
            theme.name,
            !ready && "text-zinc-500",
          )}
          title={stat.label}
        >
          {stat.label}
        </span>
        {inline ? (
          <>
            {value}
            <div className="min-w-0 flex-1">{slider}</div>
          </>
        ) : null}
      </button>

      {inline ? null : (
        <div className="flex items-center gap-2 px-2 pb-2">
          {value}
          <div className="min-w-0 flex-1">{slider}</div>
        </div>
      )}

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
            <div className={cn("px-2 pb-2", theme.chartWrap)}>
              {standing && color ? (
                <p className={cn("mb-1 text-[11px] leading-4", theme.meta)}>
                  {standing.prefix}
                  <span
                    className="rounded-none px-1 py-0.5 font-semibold tabular-nums"
                    style={{ backgroundColor: color, color: labelColor }}
                  >
                    {standing.pctLabel}
                  </span>
                  {standing.rest}
                </p>
              ) : null}
              {chart}
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
