"use client";

import {
  CHART_PLOT,
  ordinal,
  percentileColor,
  percentileContrastText,
  type StatPayload,
} from "@/lib/distribution";
import { cn } from "@/lib/utils";

type PercentileSliderProps = {
  stat: StatPayload;
  disabled?: boolean;
  alignWithChart?: boolean;
  className?: string;
  trackClassName?: string;
  thumbClassName?: string;
};

export function PercentileSlider({
  stat,
  disabled = false,
  alignWithChart = true,
  className,
  trackClassName,
  thumbClassName,
}: PercentileSliderProps) {
  const percentile = stat.percentile;
  const ready = !disabled && percentile != null;
  const color = ready ? percentileColor(percentile) : "#d4d4d8";
  const labelColor = ready ? percentileContrastText(percentile) : "#52525b";
  const x = ready ? Math.min(100, Math.max(0, percentile)) : 0;

  return (
    <div
      className={cn("relative", !alignWithChart && "px-3", className)}
      style={
        alignWithChart
          ? {
              paddingLeft: CHART_PLOT.left,
              paddingRight: CHART_PLOT.right,
            }
          : undefined
      }
    >
      <div
        className={cn(
          "relative h-2 w-full rounded-none bg-black/10",
          trackClassName,
        )}
        role="meter"
        aria-label={`${stat.label} percentile`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={ready ? Math.round(percentile) : undefined}
        aria-valuetext={
          ready ? `${ordinal(percentile)} percentile` : "unavailable"
        }
      >
        {ready ? (
          <>
            <div
              className="absolute inset-y-0 left-0 rounded-none"
              style={{ width: `${x}%`, backgroundColor: color }}
            />
            <div
              className={cn(
                "absolute top-1/2 z-10 flex size-6 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-none border border-white text-[10px] font-bold",
                thumbClassName,
              )}
              style={{
                left: `${x}%`,
                backgroundColor: color,
                color: labelColor,
              }}
            >
              {Math.round(percentile)}
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
