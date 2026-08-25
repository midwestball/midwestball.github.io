"use client";

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
import {
  CHART_PLOT,
  hoverStandingCopy,
  insertValuePoint,
  percentileColor,
  relativeFrequencyCopy,
  type StatPayload,
} from "@/lib/distribution";

type TremorDistributionProps = {
  stat: StatPayload;
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
  stat,
}: {
  active?: boolean;
  payload?: Array<{ dataKey?: string; value?: number; payload?: CurveRow }>;
  stat: StatPayload;
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
    <div className="max-w-xs rounded-none border border-zinc-200 bg-white px-2 py-1.5 text-xs">
      <p className="font-medium text-zinc-900">
        {formatStatValue(stat.format, row.x)} {stat.label}
      </p>
      <p className="mt-1 leading-5 text-zinc-600">
        {hoverStandingCopy(stat, row.x)}
      </p>
      <p className="mt-1 leading-5 text-zinc-500">
        {relativeFrequencyCopy(densityY ?? 0)}
      </p>
    </div>
  );
}

export function TremorDistribution({ stat }: TremorDistributionProps) {
  if (
    stat.playerValue == null ||
    stat.percentile == null ||
    stat.curve.length === 0
  ) {
    return null;
  }

  const playerValue = stat.playerValue;
  const color = percentileColor(stat.percentile);
  const shadeRight = !stat.higherIsBetter;
  const curveData: CurveRow[] = insertValuePoint(stat.curve, playerValue).map(
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
            <linearGradient id={`shade-${stat.id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.35} />
              <stop offset="100%" stopColor={color} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="#e4e4e7" />
          <XAxis
            dataKey="x"
            type="number"
            domain={[stat.xMin, stat.xMax]}
            tickLine={false}
            axisLine={false}
            tick={{ fill: "#71717a", fontSize: 11 }}
            tickFormatter={(value: number) => formatStatValue(stat.format, value)}
            minTickGap={24}
            padding={{ left: 0, right: 0 }}
          />
          <YAxis
            width={CHART_PLOT.left}
            domain={[0, stat.yMax]}
            tickLine={false}
            axisLine={false}
            tick={{ fill: "#71717a", fontSize: 11 }}
            tickFormatter={tickDensity}
          />
          <Tooltip
            cursor={{ stroke: "#d4d4d8" }}
            content={<DistributionTooltip stat={stat} />}
          />
          <Area
            type="linear"
            dataKey="league"
            stroke="#a1a1aa"
            strokeWidth={1.5}
            fill="rgba(244, 244, 245, 0.9)"
            fillOpacity={1}
            isAnimationActive
            animationDuration={450}
          />
          <Area
            type="linear"
            dataKey="shaded"
            stroke={color}
            strokeWidth={2}
            fill={`url(#shade-${stat.id})`}
            connectNulls={false}
            isAnimationActive
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
