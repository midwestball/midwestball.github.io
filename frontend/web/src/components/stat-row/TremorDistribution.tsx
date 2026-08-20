"use client";

import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatStatValue } from "@/lib/catalog/format";
import {
  binHighlighted,
  CHART_PLOT,
  hoverStandingCopy,
  insertValuePoint,
  percentileColor,
  relativeFrequencyCopy,
  withAlpha,
  type HistogramBin,
  type StatPayload,
} from "@/lib/distribution";

type TremorDistributionProps = {
  stat: StatPayload;
};

type ChartRow = {
  x: number;
  league: number;
  shaded: number | null;
  bin?: HistogramBin;
};

function tickPercent(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

function ChartTooltip({
  active,
  payload,
  stat,
}: {
  active?: boolean;
  payload?: Array<{ value?: number; payload?: ChartRow }>;
  stat: StatPayload;
}) {
  if (!active || !payload?.length) return null;
  const row = payload.find((item) => item.payload)?.payload;
  const y = payload.find((item) => item.value != null && item.value > 0)?.value;
  if (!row || y === undefined) return null;

  const hoverValue = row.bin ? row.bin.x0 : row.x;

  return (
    <div className="max-w-xs rounded-none border border-zinc-200 bg-white px-2 py-1.5 text-xs">
      <p className="font-medium text-zinc-900">
        {formatStatValue(stat.format, hoverValue)} {stat.label}
      </p>
      <p className="mt-1 leading-5 text-zinc-600">
        {hoverStandingCopy(stat, hoverValue)}
      </p>
      <p className="mt-1 leading-5 text-zinc-500">
        {relativeFrequencyCopy(stat, y, row.bin)}
      </p>
    </div>
  );
}

export function TremorDistribution({ stat }: TremorDistributionProps) {
  if (stat.playerValue == null || stat.percentile == null) return null;
  const playerValue = stat.playerValue;
  const color = percentileColor(stat.percentile);

  if (stat.kind === "continuous") {
    const data: ChartRow[] = insertValuePoint(stat.curve, playerValue).map(
      (point) => ({
        x: Number(point.x.toFixed(4)),
        league: point.y,
        shaded: point.x <= playerValue + 1e-9 ? point.y : null,
      }),
    );

    return (
      <div style={{ height: CHART_PLOT.height }} className="w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={data}
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
              tickFormatter={tickPercent}
            />
            <Tooltip
              cursor={{ stroke: "#d4d4d8" }}
              content={<ChartTooltip stat={stat} />}
            />
            <Area
              type="monotone"
              dataKey="league"
              stroke="#a1a1aa"
              strokeWidth={1.5}
              fill="rgba(244, 244, 245, 0.9)"
              fillOpacity={1}
              isAnimationActive
              animationDuration={450}
            />
            <Area
              type="monotone"
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

  return (
    <div style={{ height: CHART_PLOT.height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={stat.bins.map((bin) => ({
            x: bin.mid,
            league: bin.y,
            shaded: null,
            bin,
          }))}
          margin={{
            top: CHART_PLOT.top,
            right: CHART_PLOT.right,
            left: 0,
            bottom: 0,
          }}
          barCategoryGap={2}
        >
          <CartesianGrid vertical={false} stroke="#e4e4e7" />
          <XAxis
            dataKey="x"
            type="number"
            domain={[stat.xMin, stat.xMax]}
            tickLine={false}
            axisLine={false}
            tick={{ fill: "#71717a", fontSize: 11 }}
            tickFormatter={(value: number) => formatStatValue(stat.format, value)}
            padding={{ left: 0, right: 0 }}
          />
          <YAxis
            width={CHART_PLOT.left}
            domain={[0, stat.yMax]}
            tickLine={false}
            axisLine={false}
            tick={{ fill: "#71717a", fontSize: 11 }}
            tickFormatter={tickPercent}
          />
          <Tooltip
            cursor={{ fill: "rgba(24, 24, 27, 0.04)" }}
            content={<ChartTooltip stat={stat} />}
          />
          <Bar dataKey="league" radius={[4, 4, 0, 0]} maxBarSize={28}>
            {stat.bins.map((bin) => (
              <Cell
                key={`${bin.x0}-${bin.x1}`}
                fill={
                  binHighlighted(bin, playerValue)
                    ? color
                    : withAlpha(color, 0.18)
                }
              />
            ))}
          </Bar>
          <ReferenceLine
            x={playerValue}
            stroke={color}
            strokeDasharray="4 4"
            strokeWidth={1.5}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
