import { fittedCurve, formatPct, formatPoints, playerDeviation } from "@/lib/league/project";
import type { LeagueProjection, TeamProjection } from "@/lib/league/project";
import type { RosPlayer } from "@/lib/ros";
import type { SavedLeague } from "@/lib/league/types";

const SERIES = ["#6f8fbf", "#c48b5a", "#7d9a6a", "#b56b78", "#8a7aab", "#5f8f8a", "#a39a62", "#7f8c9a", "#a67c62", "#6e7f9a", "#8d6e7a", "#6a8f78", "#9a8464", "#6d7d8f", "#8f7568", "#70849a"];

type Point = { x: number; y: number };

function linePath(points: Point[], xOf: (x: number) => number, yOf: (y: number) => number): string {
  return points.map((point, index) => `${index === 0 ? "M" : "L"}${xOf(point.x).toFixed(1)} ${yOf(point.y).toFixed(1)}`).join(" ");
}

export function PlayerCurve({ player }: { player: RosPlayer }) {
  const sd = playerDeviation(player);
  if (!(sd > 0)) return null;
  const from = Math.max(0, player.mean - 3 * sd);
  const to = Math.max(from + 1, player.mean + 3 * sd);
  const points = fittedCurve(player.mean, sd, from, to, 36);
  const yMax = Math.max(...points.map((point) => point.y), 1e-9);
  const width = 220;
  const height = 48;
  const xOf = (x: number) => ((x - from) / (to - from)) * width;
  const yOf = (y: number) => 4 + (1 - y / yMax) * (height - 8);
  const path = linePath(points, xOf, yOf);
  return <svg viewBox={`0 0 ${width} ${height}`} className="mt-1 h-12 w-full max-w-xs" role="img" aria-label={`${player.name} fitted points from ${formatPoints(player.quantiles[0])} to ${formatPoints(player.quantiles[4])}, mean ${formatPoints(player.mean)}`}>
    <path d={`${path} L${width} ${height} L0 ${height} Z`} fill="var(--chart-league-fill)" />
    <path d={path} fill="none" stroke="var(--chart-threshold)" strokeWidth="1.5" />
    <line x1={xOf(player.mean)} x2={xOf(player.mean)} y1="4" y2={height - 2} stroke="var(--chart-axis)" strokeDasharray="2 2" />
  </svg>;
}

export function LeagueDistributions({ league, projection }: { league: SavedLeague; projection: LeagueProjection }) {
  const names = new Map(league.teams.map((team) => [team.id, team.name]));
  const series = projection.teams.flatMap((team) => {
    if (team.rosMean === null || team.rosSd === null || !(team.rosSd > 0)) return [];
    const mean = team.projectedPoints ?? team.rosMean;
    return [{ id: team.teamId, name: names.get(team.teamId) ?? team.teamId, mean, sd: team.rosSd, yours: team.teamId === league.selectedTeamId }];
  }).sort((a, b) => Number(b.yours) - Number(a.yours) || b.mean - a.mean);
  const chances = projection.teams.some((team) => team.pBestRecord !== null || team.pMostPoints !== null);
  if (!series.length && !chances) return null;
  return <div className="space-y-4">
    {series.length > 0 && <DistributionOverlay series={series} banked={projection.teams.some((team) => team.projectedPoints !== null)} />}
    {chances && <TitleChances teams={projection.teams} names={names} selectedId={league.selectedTeamId} />}
  </div>;
}

function DistributionOverlay({ series, banked }: { series: { id: string; name: string; mean: number; sd: number; yours: boolean }[]; banked: boolean }) {
  const from = Math.max(0, Math.min(...series.map((item) => item.mean - 3 * item.sd)));
  const to = Math.max(...series.map((item) => item.mean + 3 * item.sd), from + 1);
  const curves = series.map((item, index) => ({ ...item, color: item.yours ? "var(--chart-threshold)" : SERIES[index % SERIES.length]!, points: fittedCurve(item.mean, item.sd, from, to) }));
  const yMax = Math.max(...curves.flatMap((curve) => curve.points.map((point) => point.y)), 1e-9);
  const width = 640;
  const height = 176;
  const pad = { left: 8, right: 8, top: 8, bottom: 22 };
  const xOf = (x: number) => pad.left + ((x - from) / (to - from)) * (width - pad.left - pad.right);
  const yOf = (y: number) => pad.top + (1 - y / yMax) * (height - pad.top - pad.bottom);
  return <section className="space-y-2" aria-labelledby="league-distributions">
    <h3 id="league-distributions" className="text-sm font-semibold">Point distributions</h3>
    <p className="text-xs text-muted-foreground">{banked ? "Each curve is points already scored plus the fitted rest-of-season lineup." : "Each curve is the fitted rest-of-season lineup. Points already scored are not included."} A taller curve is a tighter range.</p>
    <svg viewBox={`0 0 ${width} ${height}`} className="h-44 w-full border border-border bg-card" role="img" aria-label="Fitted point distributions for every linked team">
      {curves.map((curve) => <path key={curve.id} d={linePath(curve.points, xOf, yOf)} fill="none" stroke={curve.color} strokeWidth={curve.yours ? 2.5 : 1.25} />)}
      <text x={pad.left} y={height - 6} fill="var(--chart-axis)" fontSize="11">{formatPoints(from)}</text>
      <text x={width - pad.right} y={height - 6} fill="var(--chart-axis)" fontSize="11" textAnchor="end">{formatPoints(to)}</text>
    </svg>
    <ul className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
      {curves.map((curve) => <li key={curve.id} className={curve.yours ? "font-semibold text-foreground" : undefined}><span className="mr-1 inline-block h-2 w-2" style={{ background: curve.color }} />{curve.name}{curve.yours ? " · yours" : ""} · {formatPoints(curve.mean)}</li>)}
    </ul>
  </section>;
}

function TitleChances({ teams, names, selectedId }: { teams: TeamProjection[]; names: Map<string, string>; selectedId: string | null }) {
  const rows = [...teams].sort((a, b) => (b.pBestRecord ?? -1) - (a.pBestRecord ?? -1) || (b.pMostPoints ?? -1) - (a.pMostPoints ?? -1));
  return <section className="space-y-2" aria-labelledby="league-title-chances">
    <h3 id="league-title-chances" className="text-sm font-semibold">Title chances</h3>
    <p className="text-xs text-muted-foreground">The upper bar is the chance of the best record. The lower bar is the chance of scoring the most points.</p>
    <ul className="space-y-2">
      {rows.map((team) => <li key={team.teamId} className="grid grid-cols-[minmax(6rem,12rem)_1fr] items-center gap-2 text-xs">
        <span className={team.teamId === selectedId ? "font-semibold" : "text-muted-foreground"}>{names.get(team.teamId)}</span>
        <span className="space-y-1">
          <ChanceBar value={team.pBestRecord} label="best record" strong />
          <ChanceBar value={team.pMostPoints} label="most points" strong={false} />
        </span>
      </li>)}
    </ul>
  </section>;
}

function ChanceBar({ value, label, strong }: { value: number | null; label: string; strong: boolean }) {
  const width = value === null ? 0 : Math.max(0, Math.min(100, value * 100));
  return <span className="block h-1.5 bg-muted" title={value === null ? undefined : `${label} ${formatPct(value)}`}>
    <span className="block h-full" style={{ width: `${width}%`, background: strong ? "var(--chart-threshold)" : "var(--chart-axis)" }} />
  </span>;
}
