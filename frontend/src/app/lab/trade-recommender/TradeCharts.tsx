"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Area,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { fittedCurve, formatPct, formatPoints } from "@/lib/league/project";
import type { PositionGap, TradeRecommendation, TeamStrength } from "@/lib/league/recommend-trades";

const WEAK = "#b56b78";
const STRONG = "#7d9a6a";
const YOU = "#6f8fbf";
const THEM = "#c48b5a";
const GRID = "var(--border)";

export function WeaknessChart({ gaps, teamName }: { gaps: PositionGap[]; teamName: string }) {
  const data = gaps.map((gap) => ({
    position: gap.position,
    gap: Math.round(gap.gap * 10) / 10,
    team: Math.round(gap.teamMean * 10) / 10,
    league: Math.round(gap.leagueMean * 10) / 10,
  }));
  return (
    <section className="space-y-2" aria-labelledby="weakness-chart">
      <div>
        <h3 id="weakness-chart" className="text-sm font-semibold">
          Position gaps vs league
        </h3>
        <p className="text-xs text-muted-foreground">
          Starter ROS means by position for {teamName}, minus the league average. Negative bars are relative weak spots (FLEX counted by the player&apos;s real position).
        </p>
      </div>
      <div className="h-56 w-full border border-border bg-card p-2">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
            <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
            <XAxis dataKey="position" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 11 }} width={40} />
            <Tooltip
              formatter={(value, name) => [`${Number(value).toFixed(1)} pts`, name === "gap" ? "vs league" : String(name)]}
              labelFormatter={(label) => String(label)}
            />
            <ReferenceLine y={0} stroke="var(--foreground)" strokeOpacity={0.35} />
            <Bar dataKey="gap" name="gap" radius={0}>
              {data.map((row) => (
                <Cell key={row.position} fill={row.gap < 0 ? WEAK : STRONG} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

export function LeagueStrengthBars({ strengths, teamNames, focusId }: { strengths: TeamStrength[]; teamNames: Map<string, string>; focusId: string }) {
  const data = [...strengths]
    .sort((a, b) => b.rosMean - a.rosMean)
    .map((row) => ({
      id: row.teamId,
      name: teamNames.get(row.teamId) ?? row.teamId,
      mean: Math.round(row.rosMean * 10) / 10,
      focus: row.teamId === focusId,
    }));
  return (
    <section className="space-y-2" aria-labelledby="league-strength">
      <div>
        <h3 id="league-strength" className="text-sm font-semibold">
          League ROS lineup means
        </h3>
        <p className="text-xs text-muted-foreground">Optimized starter totals from the same rest-of-season curves the league lab uses.</p>
      </div>
      <div className="h-56 w-full border border-border bg-card p-2">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 12, left: 4, bottom: 4 }}>
            <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
            <XAxis type="number" tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey="name" width={96} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(value) => [`${Number(value).toFixed(1)}`, "ROS mean"]} />
            <Bar dataKey="mean" name="ROS mean" radius={0}>
              {data.map((row) => (
                <Cell key={row.id} fill={row.focus ? YOU : "#8a7aab"} fillOpacity={row.focus ? 1 : 0.55} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

export function TradeScatter({ trades, leftName, rightLabel }: { trades: TradeRecommendation[]; leftName: string; rightLabel: string }) {
  const data = trades.map((trade, index) => ({
    id: trade.id,
    rank: index + 1,
    you: Math.round(trade.left.deltaMean * 10) / 10,
    them: Math.round(trade.right.deltaMean * 10) / 10,
    score: trade.score,
    pHelp: trade.left.pHelp,
  }));
  if (!data.length) return null;
  return (
    <section className="space-y-2" aria-labelledby="trade-scatter">
      <div>
        <h3 id="trade-scatter" className="text-sm font-semibold">
          Trade landscape
        </h3>
        <p className="text-xs text-muted-foreground">
          Each point is a candidate package. Up/right favors {leftName}; the other axis is {rightLabel}&apos;s ROS mean change.
        </p>
      </div>
      <div className="h-64 w-full border border-border bg-card p-2">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 12, right: 12, left: 4, bottom: 8 }}>
            <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
            <XAxis type="number" dataKey="them" name="Them" tick={{ fontSize: 11 }} label={{ value: `${rightLabel} Δ`, position: "insideBottom", offset: -2, fontSize: 11 }} />
            <YAxis type="number" dataKey="you" name="You" tick={{ fontSize: 11 }} width={44} label={{ value: `${leftName} Δ`, angle: -90, position: "insideLeft", fontSize: 11 }} />
            <ZAxis type="number" dataKey="pHelp" range={[40, 160]} />
            <ReferenceLine x={0} stroke="var(--foreground)" strokeOpacity={0.3} />
            <ReferenceLine y={0} stroke="var(--foreground)" strokeOpacity={0.3} />
            <Tooltip
              cursor={{ strokeDasharray: "3 3" }}
              formatter={(value, name) => {
                if (name === "you") return [`${Number(value).toFixed(1)}`, leftName];
                if (name === "them") return [`${Number(value).toFixed(1)}`, rightLabel];
                return [String(value), String(name)];
              }}
              labelFormatter={(_, payload) => {
                const row = payload?.[0]?.payload as { rank?: number } | undefined;
                return row?.rank ? `Rank #${row.rank}` : "Trade";
              }}
            />
            <Scatter data={data} fill={YOU} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

export function TradeImpactCurves({ trade, leftName, rightName }: { trade: TradeRecommendation; leftName: string; rightName: string }) {
  const series = [
    { id: "you-before", name: `${leftName} before`, mean: trade.left.beforeMean, sd: trade.left.beforeSd, color: YOU, dash: "4 3" },
    { id: "you-after", name: `${leftName} after`, mean: trade.left.afterMean, sd: trade.left.afterSd, color: YOU, dash: undefined },
    { id: "them-before", name: `${rightName} before`, mean: trade.right.beforeMean, sd: trade.right.beforeSd, color: THEM, dash: "4 3" },
    { id: "them-after", name: `${rightName} after`, mean: trade.right.afterMean, sd: trade.right.afterSd, color: THEM, dash: undefined },
  ].filter((row) => row.sd > 0);
  if (series.length < 2) return null;
  const from = Math.max(0, Math.min(...series.map((row) => row.mean - 3.1 * row.sd)));
  const to = Math.max(...series.map((row) => row.mean + 3.1 * row.sd), from + 1);
  const curves = series.map((row) => ({ ...row, points: fittedCurve(row.mean, row.sd, from, to, 56) }));
  const xs = curves[0]!.points.map((point) => point.x);
  const data = xs.map((x, index) => {
    const row: Record<string, number> = { x };
    for (const curve of curves) row[curve.id] = curve.points[index]?.y ?? 0;
    return row;
  });
  return (
    <section className="space-y-2" aria-labelledby="trade-curves">
      <div>
        <h3 id="trade-curves" className="text-sm font-semibold">
          Before / after ROS distributions
        </h3>
        <p className="text-xs text-muted-foreground">
          Fitted normals from published means and 5th–95th spreads. Dashed = before trade. {leftName} P(help) {formatPct(trade.left.pHelp)} · {rightName} P(hurt){" "}
          {formatPct(trade.right.pHurt)}.
        </p>
      </div>
      <div className="h-64 w-full border border-border bg-card p-2">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 8 }}>
            <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
            <XAxis dataKey="x" type="number" domain={[from, to]} tickFormatter={(value) => formatPoints(Number(value))} tick={{ fontSize: 11 }} />
            <YAxis hide domain={[0, "auto"]} />
            <Tooltip
              formatter={(value, name) => {
                const match = curves.find((curve) => curve.id === name);
                return [match ? `${match.name}` : String(name), ""];
              }}
              labelFormatter={(value) => `${formatPoints(Number(value))} ROS pts`}
            />
            {curves.map((curve) => (
              <Area key={`${curve.id}-fill`} type="monotone" dataKey={curve.id} stroke="none" fill={curve.color} fillOpacity={curve.dash ? 0.08 : 0.18} isAnimationActive={false} />
            ))}
            {curves.map((curve) => (
              <Line key={curve.id} type="monotone" dataKey={curve.id} stroke={curve.color} strokeWidth={2} strokeDasharray={curve.dash} dot={false} isAnimationActive={false} name={curve.id} />
            ))}
            <ReferenceLine x={trade.left.beforeMean} stroke={YOU} strokeOpacity={0.35} />
            <ReferenceLine x={trade.left.afterMean} stroke={YOU} strokeOpacity={0.7} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
