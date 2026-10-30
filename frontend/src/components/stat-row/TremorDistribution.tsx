"use client";
import { useReducedMotion } from "framer-motion";

import { useMemo } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatStatValue } from "@/lib/catalog/format";
import type { ValueFormat } from "@/lib/catalog/types";
import { playerKdeForStat } from "@/lib/player-kde";
import {
  CHART_PLOT,
  hoverStandingCopy,
  insertValuePoint,
  percentileColor,
  relativeFrequencyCopy,
  type Point,
  type StatPayload,
} from "@/lib/distribution";

export type DistributionChartProps = {
  id: string;
  label: string;
  playerValue: number;
  higherIsBetter: boolean;
  xMin: number;
  xMax: number;
  yMax: number;
  format: ValueFormat;
  curve: Point[];
  color: string;
  hoverStanding: (x: number) => string;
};

type CurveRow = {
  x: number;
  league: number;
  shaded: number | null;
};

function tickDensity(value: number): string {
  return value >= 10 ? value.toFixed(0) : value.toFixed(1);
}

function DistributionTooltip({
  active,
  payload,
  label,
  format,
  hoverStanding,
}: {
  active?: boolean;
  payload?: Array<{ dataKey?: string; value?: number; payload?: CurveRow }>;
  label: string;
  format: ValueFormat;
  hoverStanding: (x: number) => string;
}) {
  if (!active || !payload?.length) return null;
  const row = payload.find((item) => item.payload)?.payload;
  if (!row) return null;
  const densityY =
    payload.find(
      (item) =>
        (item.dataKey === "league" || item.dataKey === "shaded") &&
        item.value != null &&
        item.value > 0,
    )?.value ?? row.league;

  return (
    <div className="max-w-xs rounded-none border border-border bg-card px-2 py-1.5 text-xs">
      <p className="font-medium text-foreground">
        {formatStatValue(format, row.x)} {label}
      </p>
      <p className="mt-1 leading-5 text-text-secondary">{hoverStanding(row.x)}</p>
      <p className="mt-1 leading-5 text-muted-foreground">
        {relativeFrequencyCopy(densityY ?? 0)}
      </p>
    </div>
  );
}

export function DistributionChart({
  id,
  label,
  playerValue,
  higherIsBetter,
  xMin,
  xMax,
  yMax,
  format,
  curve,
  color,
  hoverStanding,
}: DistributionChartProps) {
  const reduceMotion = useReducedMotion();
  if (curve.length === 0) return null;

  const shadeRight = !higherIsBetter;
  const curveData: CurveRow[] = insertValuePoint(curve, playerValue).map(
    (point) => ({
      x: Number(point.x.toFixed(4)),
      league: point.y,
      shaded: shadeRight
        ? point.x >= playerValue - 1e-9
          ? point.y
          : null
        : point.x <= playerValue + 1e-9
          ? point.y
          : null,
    }),
  );

  return (
    <div style={{ height: CHART_PLOT.height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={curveData}
          margin={{
            top: CHART_PLOT.top,
            right: CHART_PLOT.right,
            left: 0,
            bottom: 0,
          }}
        >
          <defs>
            <linearGradient id={`shade-${id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.35} />
              <stop offset="100%" stopColor={color} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
          <XAxis
            dataKey="x"
            type="number"
            domain={[xMin, xMax]}
            tickLine={false}
            axisLine={false}
            tick={{ fill: "var(--chart-axis)", fontSize: 11 }}
            tickFormatter={(value: number) => formatStatValue(format, value)}
            minTickGap={24}
            padding={{ left: 0, right: 0 }}
          />
          <YAxis
            width={CHART_PLOT.left}
            domain={[0, yMax]}
            tickLine={false}
            axisLine={false}
            tick={{ fill: "var(--chart-axis)", fontSize: 11 }}
            tickFormatter={tickDensity}
          />
          <Tooltip
            cursor={{ stroke: "var(--chart-cursor)" }}
            content={
              <DistributionTooltip
                label={label}
                format={format}
                hoverStanding={hoverStanding}
              />
            }
          />
          <Area
            type="linear"
            dataKey="league"
            stroke="var(--chart-league-line)"
            strokeWidth={1.5}
            fill="var(--chart-league-fill)"
            fillOpacity={1}
            isAnimationActive={!reduceMotion}
            animationDuration={450}
          />
          <Area
            type="linear"
            dataKey="shaded"
            stroke={color}
            strokeWidth={2}
            fill={`url(#shade-${id})`}
            connectNulls={false}
            isAnimationActive={!reduceMotion}
            animationDuration={450}
          />
          <ReferenceLine
            x={playerValue}
            stroke={color}
            strokeDasharray="4 4"
            strokeWidth={1.5}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

type TremorDistributionProps = {
  stat: StatPayload;
};

/** Player-page wrapper: percentile color + percentile hover copy. */
export function TremorDistribution({ stat }: TremorDistributionProps) {
  const chart = useMemo(() => playerKdeForStat(stat), [stat]);
  if (
    stat.playerValue == null ||
    stat.percentile == null ||
    !chart
  ) {
    return null;
  }

  return (
    <DistributionChart
      id={stat.id}
      label={stat.label}
      playerValue={stat.playerValue}
      higherIsBetter={stat.higherIsBetter}
      xMin={chart.xMin}
      xMax={chart.xMax}
      yMax={chart.yMax}
      format={stat.format}
      curve={chart.curve}
      color={percentileColor(stat.percentile)}
      hoverStanding={(x) => hoverStandingCopy(stat, x)}
    />
  );
}
