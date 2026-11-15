"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { THRESHOLD_COLOR, clampThreshold, isOverThreshold, snapThreshold, thresholdNudge, valueFromClientX } from "@/components/projections/ProjectionOverlayChart";
import { fittedCurve, formatPct, formatPoints, normalAhead, normalAtLeast, playerDeviation } from "@/lib/league/project";
import type { LeagueProjection, TeamProjection } from "@/lib/league/project";
import type { RosPlayer } from "@/lib/ros";
import type { SavedLeague } from "@/lib/league/types";

const SERIES = ["#6f8fbf", "#c48b5a", "#7d9a6a", "#b56b78", "#8a7aab", "#5f8f8a", "#a39a62", "#7f8c9a", "#a67c62", "#6e7f9a", "#8d6e7a", "#6a8f78", "#9a8464", "#6d7d8f", "#8f7568", "#70849a"];
const GRID = 72;
const YAXIS_WIDTH = 44;
const MARGIN = { top: 26, right: 12, bottom: 16, left: 0 } as const;
const control = "border border-border bg-card px-2 py-1 text-sm";
const pressed = "border border-ring bg-muted px-2 py-1 text-sm font-semibold";

type CurveSeries = { id: string; name: string; mean: number; sd: number; color: string };
type ChartView = "teams" | "compare" | "players";
type PointBasis = "season" | "ros";
type PlayerOption = { id: string; teamId: string; teamName: string; label: string; mean: number; sd: number };

function teamCurves(league: SavedLeague, projection: LeagueProjection, basis: PointBasis): Omit<CurveSeries, "color">[] {
  const names = new Map(league.teams.map((team) => [team.id, team.name]));
  return projection.teams.flatMap((team) => {
    if (team.rosMean === null || team.rosSd === null || !(team.rosSd > 0)) return [];
    const mean = basis === "season" && team.projectedPoints !== null ? team.projectedPoints : team.rosMean;
    return [{ id: team.teamId, name: names.get(team.teamId) ?? team.teamId, mean, sd: team.rosSd }];
  });
}

function withColors(series: Omit<CurveSeries, "color">[]): CurveSeries[] {
  return series.map((item, index) => ({ ...item, color: SERIES[index % SERIES.length]! }));
}

function playerOptions(league: SavedLeague, projection: LeagueProjection): PlayerOption[] {
  const names = new Map(league.teams.map((team) => [team.id, team.name]));
  const options: PlayerOption[] = [];
  for (const team of projection.teams) {
    const teamName = names.get(team.teamId) ?? team.teamId;
    const add = (player: RosPlayer, label: string) => {
      const sd = playerDeviation(player);
      if (!(sd > 0)) return;
      options.push({ id: `${team.teamId}:${player.playerId}:${label}`, teamId: team.teamId, teamName, label: `${label} ${player.name}`, mean: player.mean, sd });
    };
    team.lineup.forEach((spot) => { if (spot.player) add(spot.player, spot.slot); });
    team.benched.forEach((item) => add(item.player, "Bench"));
  }
  return options;
}

function domain(series: { mean: number; sd: number }[]): { from: number; to: number } {
  const from = Math.max(0, Math.min(...series.map((item) => item.mean - 3.2 * item.sd)));
  const to = Math.max(...series.map((item) => item.mean + 3.2 * item.sd), from + 1);
  return { from, to };
}

export function PlayerCurve({ player }: { player: RosPlayer }) {
  const sd = playerDeviation(player);
  const from = Math.max(0, player.mean - 3 * sd);
  const to = Math.max(from + 1, player.mean + 3 * sd);
  const [threshold, setThreshold] = useState(player.mean);
  if (!(sd > 0)) return null;
  const active = clampThreshold(threshold, from, to);
  const points = fittedCurve(player.mean, sd, from, to, 36);
  const yMax = Math.max(...points.map((point) => point.y), 1e-9);
  const width = 220;
  const height = 48;
  const xOf = (x: number) => ((x - from) / (to - from)) * width;
  const yOf = (y: number) => 4 + (1 - y / yMax) * (height - 8);
  const path = points.map((point, index) => `${index === 0 ? "M" : "L"}${xOf(point.x).toFixed(1)} ${yOf(point.y).toFixed(1)}`).join(" ");
  const cut = xOf(active);
  const move = (clientX: number, rect: DOMRect) => {
    const ratio = rect.width ? (clientX - rect.left) / rect.width : 0;
    setThreshold(clampThreshold(from + Math.min(1, Math.max(0, ratio)) * (to - from), from, to));
  };
  return <span className="mt-1 block max-w-xs">
    <svg viewBox={`0 0 ${width} ${height}`} className="h-12 w-full cursor-ew-resize" role="img" aria-label={`${player.name} fitted points, ${formatPct(normalAtLeast(player.mean, sd, active))} at least ${formatPoints(active)}`} onPointerDown={(event) => move(event.clientX, event.currentTarget.getBoundingClientRect())} onPointerMove={(event) => { if (event.buttons === 1) move(event.clientX, event.currentTarget.getBoundingClientRect()); }}>
      <path d={`${path} L${width} ${height} L0 ${height} Z`} fill="var(--chart-league-fill)" />
      <path d={path} fill="none" stroke="var(--chart-threshold)" strokeWidth="1.5" />
      <line x1={cut} x2={cut} y1="2" y2={height - 1} stroke="var(--chart-axis)" />
    </svg>
    <input type="range" min={from} max={to} step={0.1} value={active} aria-label={`${player.name} points threshold`} onChange={(event) => setThreshold(Number(event.target.value))} className="mt-1 w-full" />
    <span className="block text-[11px]">{formatPoints(active)} · {formatPct(normalAtLeast(player.mean, sd, active))} at least</span>
  </span>;
}

export function LeagueDistributions({ league, projection }: { league: SavedLeague; projection: LeagueProjection }) {
  const banked = projection.teams.some((team) => team.projectedPoints !== null);
  const [view, setView] = useState<ChartView>("teams");
  const [basis, setBasis] = useState<PointBasis>(banked ? "season" : "ros");
  const [hidden, setHidden] = useState<string[]>([]);
  const [focusId, setFocusId] = useState("");
  const [threshold, setThreshold] = useState<number | null>(null);
  const teams = useMemo(() => withColors(teamCurves(league, projection, basis)), [league, projection, basis]);
  const players = useMemo(() => playerOptions(league, projection), [league, projection]);
  const [compareA, setCompareA] = useState(() => teams.find((team) => team.id === league.selectedTeamId)?.id ?? teams[0]?.id ?? "");
  const [compareB, setCompareB] = useState(() => teams.find((team) => team.id !== (teams.find((item) => item.id === league.selectedTeamId)?.id ?? teams[0]?.id))?.id ?? "");
  const [playerA, setPlayerA] = useState(players[0]?.id ?? "");
  const [playerB, setPlayerB] = useState(players.find((player) => player.id !== players[0]?.id)?.id ?? "");
  const visible = view === "players"
    ? withColors(players.filter((player) => player.id === playerA || player.id === playerB).map(({ id, label, mean, sd }) => ({ id, name: `${label} · ${players.find((player) => player.id === id)?.teamName ?? ""}`, mean, sd })))
    : view === "compare"
      ? teams.filter((team) => team.id === compareA || team.id === compareB)
      : teams.filter((team) => !hidden.includes(team.id));
  const focus = visible.find((series) => series.id === focusId) ?? visible[0] ?? null;
  const bounds = visible.length ? domain(visible) : { from: 0, to: 1 };
  const activeThreshold = clampThreshold(threshold ?? focus?.mean ?? bounds.from, bounds.from, bounds.to);

  if (!teams.length && !players.length) return null;
  return <div className="space-y-4">
    <section className="space-y-3" aria-labelledby="league-distributions">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 id="league-distributions" className="text-sm font-semibold">Point distributions</h3>
          <p className="text-xs text-muted-foreground">Drag the line, or type a total, to read the chance of scoring at least that many. Click a line to shade it. {view === "players" ? "Player curves are each player’s fitted rest-of-season total." : basis === "season" && banked ? "Team curves add points already scored to the fitted rest-of-season lineup." : "These curves are the fitted rest-of-season totals."}</p>
        </div>
        <div className="flex flex-wrap gap-2" role="group" aria-label="What to chart">
          <button type="button" aria-pressed={view === "teams"} onClick={() => { setView("teams"); setThreshold(null); }} className={view === "teams" ? pressed : control}>All teams</button>
          <button type="button" aria-pressed={view === "compare"} onClick={() => { setView("compare"); setThreshold(null); }} className={view === "compare" ? pressed : control} disabled={teams.length < 2}>Two teams</button>
          <button type="button" aria-pressed={view === "players"} onClick={() => { setView("players"); setThreshold(null); }} className={view === "players" ? pressed : control} disabled={players.length < 2}>Two players</button>
        </div>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        {view !== "players" && <label className="text-xs font-semibold">Shown points
          <select value={basis} onChange={(event) => { setBasis(event.target.value === "ros" ? "ros" : "season"); setThreshold(null); }} className={`${control} mt-1 block`} disabled={!banked}>
            <option value="season">Season total</option>
            <option value="ros">Rest of season only</option>
          </select>
        </label>}
        {view === "compare" && <>
          <TeamSelect label="First team" value={compareA} teams={teams} onChange={(id) => { setCompareA(id); setFocusId(id); setThreshold(null); }} />
          <TeamSelect label="Second team" value={compareB} teams={teams} onChange={(id) => { setCompareB(id); setThreshold(null); }} />
        </>}
        {view === "players" && <>
          <PlayerSelect label="First player" value={playerA} players={players} onChange={(id) => { setPlayerA(id); setFocusId(id); setThreshold(null); }} />
          <PlayerSelect label="Second player" value={playerB} players={players} onChange={(id) => { setPlayerB(id); setThreshold(null); }} />
        </>}
        {focus && <label className="text-xs font-semibold">At least
          <input type="number" step="0.1" min={bounds.from} max={bounds.to} value={activeThreshold.toFixed(1)} onChange={(event) => setThreshold(clampThreshold(Number(event.target.value), bounds.from, bounds.to))} className={`${control} mt-1 w-28`} />
        </label>}
      </div>
      {view === "teams" && <ul className="flex flex-wrap gap-3" aria-label="Teams on the chart">
        {teams.map((team) => {
          const shown = !hidden.includes(team.id);
          const only = shown && teams.filter((item) => !hidden.includes(item.id)).length === 1;
          return <li key={team.id} className="flex items-center gap-1 text-xs">
            <input type="checkbox" checked={shown} disabled={only} aria-label={`Show ${team.name}`} onChange={() => setHidden((current) => shown ? [...current, team.id] : current.filter((id) => id !== team.id))} />
            <button type="button" onClick={() => setFocusId(team.id)} className={focus?.id === team.id ? "font-semibold" : "text-muted-foreground"}><span className="mr-1 inline-block h-2 w-2 align-middle" style={{ background: team.color }} />{team.name}</button>
          </li>;
        })}
      </ul>}
      {view === "teams" && <p className="text-[11px] text-muted-foreground">Check a team to draw its curve. Click its name to shade the chance of scoring at least the line. One team always stays on the chart.</p>}
      {visible.length >= 1 && focus ? <InteractiveCurves series={visible} focusId={focus.id} threshold={activeThreshold} onFocus={setFocusId} onThreshold={setThreshold} /> : <p className="text-sm text-muted-foreground">Choose at least one curve.</p>}
      {focus && <ul className="grid gap-1 text-xs sm:grid-cols-2">
        {visible.map((series) => <li key={series.id} className={series.id === focus.id ? "font-semibold" : "text-muted-foreground"}><span className="mr-1 inline-block h-2 w-2" style={{ background: series.color }} />{series.name}: {formatPct(normalAtLeast(series.mean, series.sd, activeThreshold))} at least {formatPoints(activeThreshold)} <span className="font-normal text-muted-foreground">· mean {formatPoints(series.mean)}</span></li>)}
      </ul>}
      {view !== "teams" && visible.length === 2 && <p className="text-sm">{visible[0]!.name} finishes ahead of {visible[1]!.name} on these fitted curves {formatPct(normalAhead(visible[0]!.mean, visible[0]!.sd, visible[1]!.mean, visible[1]!.sd))} of the time. That comparison ignores the weekly schedule.</p>}
    </section>
    {projection.teams.some((team) => team.pBestRecord !== null || team.pMostPoints !== null) && <TitleChances teams={projection.teams} names={new Map(league.teams.map((team) => [team.id, team.name]))} selectedId={league.selectedTeamId} onCompare={(id) => { setView("compare"); setCompareA(id); setFocusId(id); setThreshold(null); }} />}
  </div>;
}

function TeamSelect({ label, value, teams, onChange }: { label: string; value: string; teams: CurveSeries[]; onChange: (id: string) => void }) {
  return <label className="text-xs font-semibold">{label}
    <select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)} className={`${control} mt-1 block max-w-full`}>{teams.map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}</select>
  </label>;
}

function PlayerSelect({ label, value, players, onChange }: { label: string; value: string; players: PlayerOption[]; onChange: (id: string) => void }) {
  const groups = [...new Map(players.map((player) => [player.teamId, player.teamName])).entries()];
  return <label className="text-xs font-semibold">{label}
    <select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)} className={`${control} mt-1 block max-w-full`}>{groups.map(([teamId, teamName]) => <optgroup key={teamId} label={teamName}>{players.filter((player) => player.teamId === teamId).map((player) => <option key={player.id} value={player.id}>{player.label} · {formatPoints(player.mean)}</option>)}</optgroup>)}</select>
  </label>;
}

function InteractiveCurves({ series, focusId, threshold, onFocus, onThreshold }: {
  series: CurveSeries[];
  focusId: string;
  threshold: number;
  onFocus: (id: string) => void;
  onThreshold: (value: number) => void;
}) {
  const { from, to } = domain(series);
  const plotRef = useRef<HTMLDivElement>(null);
  const pendingRef = useRef<number | null>(null);
  const hoverRef = useRef(false);
  const [dragValue, setDragValue] = useState<number | null>(null);
  const [hovered, setHovered] = useState(false);
  const [handleFocused, setHandleFocused] = useState(false);
  const [plotBox, setPlotBox] = useState<{ width: number; height: number } | null>(null);
  const active = dragValue ?? threshold;
  const draggingNow = dragValue != null;
  const setDrag = useCallback((value: number | null) => { pendingRef.current = value; setDragValue(value); }, []);
  const valueAt = useCallback((clientX: number) => {
    const rect = plotRef.current?.getBoundingClientRect();
    if (!rect) return null;
    return valueFromClientX(clientX, rect.left, rect.width, from, to);
  }, [from, to]);
  useEffect(() => {
    const element = plotRef.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const measure = () => {
      const rect = element.getBoundingClientRect();
      setPlotBox((previous) => previous && previous.width === rect.width && previous.height === rect.height ? previous : { width: rect.width, height: rect.height });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!draggingNow) return;
    const move = (event: PointerEvent) => { const value = valueAt(event.clientX); if (value != null) setDrag(value); };
    const release = () => {
      const pending = pendingRef.current;
      setDrag(null);
      if (pending != null) onThreshold(snapThreshold(pending, from, to));
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", release);
    window.addEventListener("pointercancel", release);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", release);
      window.removeEventListener("pointercancel", release);
    };
  }, [draggingNow, from, to, onThreshold, setDrag, valueAt]);

  const curves = new Map(series.map((item) => [item.id, fittedCurve(item.mean, item.sd, from, to, GRID)]));
  const data = curves.get(series[0]!.id)!.map((point, index) => {
    const row: Record<string, number | null> = { x: point.x };
    for (const item of series) row[item.id] = curves.get(item.id)?.[index]?.y ?? null;
    row.shaded = point.x >= active ? curves.get(focusId)?.[index]?.y ?? null : null;
    return row;
  });
  const showBand = hovered || draggingNow || handleFocused;
  return <div className="border border-border bg-card p-2">
    <div ref={plotRef} className="relative h-72" style={{ touchAction: "none", cursor: hovered || draggingNow ? "ew-resize" : undefined }} onPointerMove={(event) => {
      const plotWidth = (plotBox?.width ?? 0) - YAXIS_WIDTH - MARGIN.right;
      const near = isOverThreshold(valueAt(event.clientX), active, plotWidth / (to - from || 1));
      if (near !== hoverRef.current) { hoverRef.current = near; setHovered(near); }
    }} onPointerLeave={() => { if (!hoverRef.current) return; hoverRef.current = false; setHovered(false); }} onPointerDown={(event) => {
      if (event.button !== 0) return;
      const value = valueAt(event.clientX);
      const rect = plotRef.current?.getBoundingClientRect();
      if (value == null || !rect) return;
      const plotWidth = rect.width - YAXIS_WIDTH - MARGIN.right;
      if (!isOverThreshold(value, threshold, plotWidth / (to - from || 1))) return;
      setDrag(value);
      event.preventDefault();
    }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={MARGIN}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
          <XAxis dataKey="x" type="number" domain={[from, to]} tick={{ fill: "var(--chart-axis)", fontSize: 11 }} stroke="var(--chart-axis)" tickFormatter={(value) => Number(value).toFixed(0)} label={{ value: "Fantasy points", position: "insideBottom", offset: -2, fill: "var(--chart-axis)", fontSize: 11 }} />
          <YAxis width={YAXIS_WIDTH} tick={{ fill: "var(--chart-axis)", fontSize: 11 }} stroke="var(--chart-axis)" tickFormatter={(value) => Number(value).toFixed(3)} />
          <Tooltip content={() => null} cursor={false} isAnimationActive={false} />
          <Area dataKey="shaded" stroke="none" fill="var(--chart-league-line)" fillOpacity={0.22} isAnimationActive={false} />
          {series.map((item) => <Line key={item.id} dataKey={item.id} name={item.name} stroke={item.color} strokeWidth={item.id === focusId ? 3 : 1.75} dot={false} connectNulls isAnimationActive={false} onClick={() => onFocus(item.id)} />)}
          <ReferenceLine x={active} stroke={THRESHOLD_COLOR} strokeWidth={draggingNow ? 3 : 2} strokeDasharray={draggingNow || hovered ? undefined : "4 3"} label={(props: { x?: number }) => {
            const x = props.x ?? 0;
            return <g role="slider" tabIndex={0} aria-label="Points threshold" aria-valuemin={from} aria-valuemax={to} aria-valuenow={Number(active.toFixed(1))} aria-valuetext={`${active.toFixed(1)} points`} style={{ cursor: "ew-resize", outline: "none" }} onFocus={() => setHandleFocused(true)} onBlur={() => setHandleFocused(false)} onKeyDown={(event) => {
              const next = thresholdNudge(event.key, active, event.shiftKey, from, to);
              if (next == null) return;
              event.preventDefault();
              onThreshold(snapThreshold(next, from, to));
            }}>
              <rect x={x - 12} y={MARGIN.top - 13} width={24} height={26} fill="transparent" />
              <text x={plotBox ? Math.min(Math.max(x, 28), plotBox.width - 28) : x} y={MARGIN.top - 6} textAnchor="middle" fontSize={11} fontWeight={600} fill={THRESHOLD_COLOR} stroke="var(--card)" strokeWidth={3} paintOrder="stroke">{active.toFixed(1)}</text>
              {showBand && plotBox ? <rect x={x - 12} y={MARGIN.top} width={24} height={Math.max(0, plotBox.height - MARGIN.top - MARGIN.bottom)} fill={THRESHOLD_COLOR} opacity={draggingNow ? 0.12 : 0.07} /> : null}
            </g>;
          }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  </div>;
}

function TitleChances({ teams, names, selectedId, onCompare }: { teams: TeamProjection[]; names: Map<string, string>; selectedId: string | null; onCompare: (id: string) => void }) {
  const rows = [...teams].sort((a, b) => (b.pBestRecord ?? -1) - (a.pBestRecord ?? -1) || (b.pMostPoints ?? -1) - (a.pMostPoints ?? -1));
  return <section className="space-y-2" aria-labelledby="league-title-chances">
    <h3 id="league-title-chances" className="text-sm font-semibold">Title chances</h3>
    <p className="text-xs text-muted-foreground">The upper bar is the chance of the best record. The lower bar is the chance of scoring the most points. Choose a team to compare its curve.</p>
    <ul className="space-y-2">
      {rows.map((team) => <li key={team.teamId} className="grid grid-cols-[minmax(6rem,14rem)_1fr] items-center gap-2 text-xs">
        <button type="button" onClick={() => onCompare(team.teamId)} className={team.teamId === selectedId ? "text-left font-semibold" : "text-left text-muted-foreground"}>{names.get(team.teamId)}</button>
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
  return <span className="block h-2 bg-muted" title={value === null ? undefined : `${label} ${formatPct(value)}`}>
    <span className="block h-full" style={{ width: `${width}%`, background: strong ? "var(--chart-threshold)" : "var(--chart-axis)" }} />
  </span>;
}
