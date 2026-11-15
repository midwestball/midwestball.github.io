import type { RosPlayer, RosSnapshot } from "@/lib/ros";
import { optimizeLineup, validSettings, type SlotType } from "@/lib/trades";
import type { LeagueMatchup, LeagueTeam, SavedLeague } from "./types";

const Z95 = 1.6448536269514722;
export const SIMULATIONS = 2000;

export type LineupSpot = { slot: SlotType; player: RosPlayer | null; rosterName: string | null };
export type Omission = { name: string; detail: string };
export type RecordLine = { label: string; probability: number };
export type TeamProjection = {
  teamId: string;
  lineup: LineupSpot[];
  unmapped: Omission[];
  heldOut: Omission[];
  lineupError: string | null;
  fantasyGames: number;
  rosMean: number | null;
  rosMedianSum: number | null;
  through: { wins: number; losses: number; ties: number; points: number };
  projectedPoints: number | null;
  pBestRecord: number | null;
  pMostPoints: number | null;
  expectedWins: number | null;
  records: RecordLine[];
};

export type ProjectionMode = "blocked" | "remaining-only" | "points-only" | "standings" | "simulated";
export type LeagueProjection = {
  mode: ProjectionMode;
  reason: string | null;
  cutoffWeek: number;
  caveats: string[];
  sims: number;
  teams: TeamProjection[];
};

type Standing = { wins: number; losses: number; ties: number; points: number };

export function formatPct(probability: number): string {
  const pct = probability * 100;
  if (pct > 0 && pct < 1) return "<1%";
  if (pct >= 99 && pct < 100) return ">99%";
  return `${Math.round(pct)}%`;
}

export function formatPoints(value: number): string {
  return value.toFixed(1);
}

export function formatRecord(wins: number, losses: number, ties: number): string {
  return ties ? `${wins}-${losses}-${ties}` : `${wins}-${losses}`;
}

export function methodCaveats(league?: SavedLeague | null): string[] {
  const caveats = [
    "Projections are full-PPR rest-of-season totals. The league's reception scoring, tight-end premium, bonuses, and negative points are not applied.",
    "Kickers, team defenses, and individual defensive players are omitted. An empty lineup slot counts as zero.",
    "Starters are the single highest-median lineup for the whole rest of the season. The lineup does not change by week, and IR or taxi players do not start.",
    "Each modeled player is treated as an independent normal curve fit to the published mean and the gap between the 5th and 95th percentiles. These are not the model's own simulated draws. A weekly score is that season curve split evenly across the fantasy team's remaining regular-season games and floored at zero.",
    "The split ignores opponent, weather, correlation between teammates, and which week a player is actually on bye.",
    "Published rest-of-season totals run through the rest of the NFL season. Each player is scaled by the share of their remaining games that fit in this fantasy league's remaining regular-season games, so production after the fantasy playoffs is not added in full.",
    "Best-record chance is the share of simulations with the best regular-season winning percentage, with points as the tiebreak. It is not the chance of winning a playoff bracket.",
    "A Sleeper username can preselect a team. That match does not prove the team is yours.",
    "ESPN session cookies are not accepted and are not saved. This static site cannot attach them to ESPN.",
  ];
  if (league && league.receptionPoints !== null && Math.abs(league.receptionPoints - 1) > 0.001) {
    caveats.unshift(`This league scores ${league.receptionPoints} points per reception. The totals below stay full PPR.`);
  } else if (league && league.receptionPoints === null) {
    caveats.unshift("This league's points per reception were not identified. The totals below stay full PPR.");
  }
  if (league?.playoffWeekStart === null) caveats.push("The league did not report when playoffs start, so the regular season is assumed to end after week 14.");
  for (const note of league?.notes ?? []) caveats.push(note);
  if (league && league.unsupportedSlots.length) caveats.push(`Unsupported roster slots are ignored: ${league.unsupportedSlots.join(", ")}.`);
  return caveats;
}

function spread(player: RosPlayer): { mean: number; sd: number } {
  return { mean: player.mean, sd: Math.max(0, (player.quantiles[4] - player.quantiles[0]) / (2 * Z95)) };
}

function mulberry32(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function normal(rng: () => number): number {
  let u = 0;
  let v = 0;
  while (u === 0) u = rng();
  while (v === 0) v = rng();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

function sameName(a: string, b: string): boolean {
  return a.toLowerCase().replace(/[^a-z0-9]/g, "") === b.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function emptyThrough(): Standing {
  return { wins: 0, losses: 0, ties: 0, points: 0 };
}

/** Weeks where every saved score is zero are treated as unplayed so future 0-point schedules are not counted as results. */
export function replayThrough(matchups: LeagueMatchup[], teamIds: string[], cutoffWeek: number): { through: Map<string, Standing>; skippedWeeks: number[]; usable: boolean } {
  const through = new Map(teamIds.map((id) => [id, emptyThrough()]));
  const byWeek = new Map<number, LeagueMatchup[]>();
  for (const matchup of matchups) {
    if (matchup.week > cutoffWeek) continue;
    const rows = byWeek.get(matchup.week) ?? [];
    rows.push(matchup);
    byWeek.set(matchup.week, rows);
  }
  const skippedWeeks: number[] = [];
  for (const [week, rows] of [...byWeek.entries()].sort((a, b) => a[0] - b[0])) {
    if (rows.every((row) => row.points === 0)) {
      skippedWeeks.push(week);
      continue;
    }
    for (const row of rows) through.get(row.teamId)!.points += row.points;
    const groups = new Map<string, LeagueMatchup[]>();
    for (const row of rows) {
      if (row.matchupId === null) continue;
      const group = groups.get(row.matchupId) ?? [];
      group.push(row);
      groups.set(row.matchupId, group);
    }
    for (const group of groups.values()) {
      if (group.length !== 2) continue;
      const [left, right] = group;
      const leftScore = round2(left!.points), rightScore = round2(right!.points);
      const leftStanding = through.get(left!.teamId)!, rightStanding = through.get(right!.teamId)!;
      if (leftScore > rightScore) { leftStanding.wins += 1; rightStanding.losses += 1; }
      else if (rightScore > leftScore) { rightStanding.wins += 1; leftStanding.losses += 1; }
      else { leftStanding.ties += 1; rightStanding.ties += 1; }
    }
  }
  const usable = cutoffWeek === 0 || [...byWeek.values()].some((rows) => rows.some((row) => row.points !== 0));
  return { through, skippedWeeks, usable };
}

function remainingGames(matchups: LeagueMatchup[], cutoffWeek: number, playoffWeekStart: number): { week: number; teams: [string, string] }[] {
  const groups = new Map<string, LeagueMatchup[]>();
  for (const matchup of matchups) {
    if (matchup.week <= cutoffWeek || matchup.week >= playoffWeekStart || matchup.matchupId === null) continue;
    const key = `${matchup.week}:${matchup.matchupId}`;
    const group = groups.get(key) ?? [];
    group.push(matchup);
    groups.set(key, group);
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b)).flatMap(([, group]) => {
    if (group.length !== 2) return [];
    const teams = [group[0]!.teamId, group[1]!.teamId].sort((a, b) => a.localeCompare(b)) as [string, string];
    return [{ week: group[0]!.week, teams }];
  });
}

function scaleToFantasy(player: RosPlayer, gamesLeft: number): RosPlayer {
  const factor = gamesLeft <= 0 || player.remainingTeamGames <= 0 ? 0 : Math.min(gamesLeft, player.remainingTeamGames) / player.remainingTeamGames;
  return { ...player, mean: player.mean * factor, quantiles: player.quantiles.map((quantile) => quantile * factor) as RosPlayer["quantiles"] };
}

function lineupFor(team: LeagueTeam, byId: Map<string, RosPlayer>, settings: SavedLeague["rosterSettings"], gamesLeft: number): Pick<TeamProjection, "lineup" | "unmapped" | "heldOut" | "lineupError" | "fantasyGames" | "rosMean" | "rosMedianSum"> {
  const unmapped: Omission[] = [];
  const heldOut: Omission[] = [];
  const chosen = new Map<string, { player: RosPlayer; rosterName: string }>();
  for (const rosterPlayer of team.players) {
    if (rosterPlayer.position === "K" || rosterPlayer.position === "DST") {
      unmapped.push({ name: rosterPlayer.name, detail: "Kickers and defenses are not projected." });
      continue;
    }
    if (rosterPlayer.ir || rosterPlayer.taxi) {
      heldOut.push({ name: rosterPlayer.name, detail: rosterPlayer.ir ? "IR, not started." : "Taxi, not started." });
      continue;
    }
    if (!rosterPlayer.gsisId || !byId.has(rosterPlayer.gsisId)) {
      unmapped.push({ name: rosterPlayer.name, detail: rosterPlayer.gsisId ? "No rest-of-season projection." : "No GSIS id, so this player was not matched by name." });
      continue;
    }
    const player = scaleToFantasy(byId.get(rosterPlayer.gsisId)!, gamesLeft);
    if (!chosen.has(player.playerId)) chosen.set(player.playerId, { player, rosterName: rosterPlayer.name });
  }
  if (!validSettings(settings)) {
    return { lineup: [], unmapped, heldOut, lineupError: "This league's starting slots aren't supported by the lineup calculator.", fantasyGames: gamesLeft, rosMean: null, rosMedianSum: null };
  }
  const optimized = optimizeLineup([...chosen.values()].map((item) => item.player), settings);
  const lineup = optimized.assignments.map((assignment) => ({
    slot: assignment.slot,
    player: assignment.player,
    rosterName: assignment.player && !sameName(assignment.player.name, chosen.get(assignment.player.playerId)?.rosterName ?? "") ? chosen.get(assignment.player.playerId)!.rosterName : null,
  }));
  const starters = lineup.flatMap((spot) => spot.player ? [spot.player] : []);
  return {
    lineup, unmapped, heldOut, lineupError: null, fantasyGames: gamesLeft,
    rosMean: starters.reduce((sum, player) => sum + player.mean, 0),
    rosMedianSum: optimized.total,
  };
}

function blankTeam(team: LeagueTeam, through: Standing): TeamProjection {
  return {
    teamId: team.id, lineup: [], unmapped: [], heldOut: [], lineupError: null, fantasyGames: 0, rosMean: null, rosMedianSum: null,
    through, projectedPoints: null, pBestRecord: null, pMostPoints: null, expectedWins: null, records: [],
  };
}

type Ranked = { pct: number; points: number };

function rankValue(standing: Standing): Ranked {
  const games = standing.wins + standing.losses + standing.ties;
  return { pct: games ? (standing.wins + 0.5 * standing.ties) / games : 0, points: round2(standing.points) };
}

function leaders(rows: { id: string; standing: Standing }[], score: (standing: Standing) => Ranked): Map<string, number> {
  let best: Ranked | null = null;
  const ranked = rows.map((row) => ({ id: row.id, score: score(row.standing) }));
  for (const row of ranked) {
    if (!best || row.score.pct > best.pct + 1e-12 || (Math.abs(row.score.pct - best.pct) <= 1e-12 && row.score.points > best.points)) best = row.score;
  }
  const winners = ranked.filter((row) => best && Math.abs(row.score.pct - best.pct) <= 1e-12 && row.score.points === best.points);
  const share = winners.length ? 1 / winners.length : 0;
  return new Map(winners.map((winner) => [winner.id, share]));
}

function recordLeaders(rows: { id: string; standing: Standing }[]): Map<string, number> {
  return leaders(rows, rankValue);
}

function pointLeaders(rows: { id: string; standing: Standing }[]): Map<string, number> {
  return leaders(rows, (standing) => ({ pct: 0, points: round2(standing.points) }));
}

function sampleScore(mean: number, sd: number, rng: () => number): number {
  return Math.max(0, mean + sd * normal(rng));
}

function finishPointsOnly(league: SavedLeague, built: Map<string, ReturnType<typeof lineupFor>>, through: Map<string, Standing>, caveats: string[], cutoffWeek: number, options?: { sims?: number; seed?: number }): LeagueProjection {
  const sims = options?.sims ?? SIMULATIONS;
  const rng = mulberry32(options?.seed ?? 0x4c454147);
  const teamIds = league.teams.map((team) => team.id).sort((a, b) => a.localeCompare(b));
  const pointWins = new Map(teamIds.map((id) => [id, 0]));
  for (let sim = 0; sim < sims; sim++) {
    const rows = teamIds.map((id) => {
      const base = through.get(id) ?? emptyThrough();
      let points = base.points;
      for (const player of (built.get(id)?.lineup ?? []).flatMap((spot) => spot.player ? [spot.player] : []).sort((a, b) => a.playerId.localeCompare(b.playerId))) {
        const shape = spread(player);
        points += sampleScore(shape.mean, shape.sd, rng);
      }
      return { id, standing: { ...base, points } };
    });
    for (const [id, share] of pointLeaders(rows)) pointWins.set(id, pointWins.get(id)! + share);
  }
  return {
    mode: "points-only", reason: null, cutoffWeek, caveats, sims,
    teams: league.teams.map((team) => {
      const base = built.get(team.id)!;
      const baseline = through.get(team.id) ?? emptyThrough();
      return {
        ...blankTeam(team, baseline), ...base,
        projectedPoints: base.rosMean === null ? null : baseline.points + base.rosMean,
        pMostPoints: (pointWins.get(team.id) ?? 0) / sims,
      };
    }),
  };
}

export function projectLeague(league: SavedLeague, ros: RosSnapshot, options?: { sims?: number; seed?: number }): LeagueProjection {
  const caveats = methodCaveats(league);
  const teamIds = league.teams.map((team) => team.id);
  if (league.season !== ros.season) {
    return {
      mode: "blocked",
      reason: `Rest-of-season projections are for ${ros.season}. This league is ${league.season}, so points and record chances are not estimated.`,
      cutoffWeek: ros.cutoffWeek,
      caveats,
      sims: 0,
      teams: league.teams.map((team) => blankTeam(team, emptyThrough())),
    };
  }
  const byId = new Map(ros.entities.map((player) => [player.playerId, player]));
  const replay = replayThrough(league.matchups, teamIds, ros.cutoffWeek);
  if (replay.skippedWeeks.length) caveats.push(`Week ${replay.skippedWeeks.join(", ")} was saved as all zeros and was left out of the results.`);
  const playoffStart = league.playoffWeekStart ?? 15;
  const futureWeekCount = Math.max(0, playoffStart - ros.cutoffWeek - 1);
  const games = remainingGames(league.matchups, ros.cutoffWeek, playoffStart);
  const pairedWeeks = new Set(games.map((game) => game.week)).size;
  const gamesLeftFor = (teamId: string) => games.length ? games.filter((game) => game.teams.includes(teamId)).length : futureWeekCount;
  const built = new Map(league.teams.map((team) => [team.id, lineupFor(team, byId, league.rosterSettings, gamesLeftFor(team.id))]));
  const missingSkill = [...built.values()].reduce((sum, row) => sum + row.unmapped.filter((item) => item.detail !== "Kickers and defenses are not projected.").length, 0);
  if (missingSkill) caveats.push(`${missingSkill} skill-player spots have no rest-of-season projection and are left out of the totals.`);
  const startersOf = (teamId: string) => (built.get(teamId)?.lineup ?? []).flatMap((spot) => spot.player ? [spot.player] : []).sort((a, b) => a.playerId.localeCompare(b.playerId));
  if (!replay.usable) {
    caveats.unshift("Saved matchups don't include results through the projection cutoff, so rest-of-season points are not added to points already scored, and record chances are omitted.");
    return {
      mode: "remaining-only", reason: null, cutoffWeek: ros.cutoffWeek, caveats, sims: 0,
      teams: league.teams.map((team) => ({ ...blankTeam(team, replay.through.get(team.id) ?? emptyThrough()), ...built.get(team.id)! })),
    };
  }
  if (games.length === 0 && futureWeekCount === 0) {
    const rows = league.teams.map((team) => ({ id: team.id, standing: { ...(replay.through.get(team.id) ?? emptyThrough()) } }));
    const records = recordLeaders(rows), points = pointLeaders(rows);
    caveats.push("No regular-season games remain after the projection cutoff, so the best-record and points-title marks are the saved standings.");
    return {
      mode: "standings", reason: null, cutoffWeek: ros.cutoffWeek, caveats, sims: 0,
      teams: league.teams.map((team) => {
        const base = built.get(team.id)!;
        const through = replay.through.get(team.id) ?? emptyThrough();
        const label = formatRecord(through.wins, through.losses, through.ties);
        return {
          ...blankTeam(team, through), ...base,
          projectedPoints: base.rosMean === null ? null : through.points + base.rosMean,
          pBestRecord: records.get(team.id) ?? 0,
          pMostPoints: points.get(team.id) ?? 0,
          expectedWins: through.wins,
          records: [{ label, probability: 1 }],
        };
      }),
    };
  }
  if (games.length === 0) {
    caveats.push("Remaining regular-season games were not paired in the saved schedule, so record chances are omitted. Point-title chances use each team's scaled rest-of-season total.");
    return finishPointsOnly(league, built, replay.through, caveats, ros.cutoffWeek, options);
  }
  if (pairedWeeks < futureWeekCount) caveats.push("Some regular-season weeks after the cutoff had no saved matchup, so those weeks are not in the record simulation.");

  const sims = options?.sims ?? SIMULATIONS;
  const rng = mulberry32(options?.seed ?? 0x4c454147);
  const recordWins = new Map(teamIds.map((id) => [id, 0]));
  const pointWins = new Map(teamIds.map((id) => [id, 0]));
  const winSum = new Map(teamIds.map((id) => [id, 0]));
  const recordCounts = new Map(teamIds.map((id) => [id, new Map<string, number>()]));
  for (let sim = 0; sim < sims; sim++) {
    const standings = new Map(teamIds.map((id) => [id, { ...(replay.through.get(id) ?? emptyThrough()) }]));
    for (const game of games) {
      const scores = game.teams.map((teamId) => {
        const n = Math.max(gamesLeftFor(teamId), 1);
        let score = 0;
        for (const player of startersOf(teamId)) {
          const shape = spread(player);
          score += sampleScore(shape.mean / n, shape.sd / Math.sqrt(n), rng);
        }
        return score;
      });
      const [leftId, rightId] = game.teams;
      const left = standings.get(leftId)!, right = standings.get(rightId)!;
      left.points += scores[0]!;
      right.points += scores[1]!;
      const leftScore = round2(scores[0]!), rightScore = round2(scores[1]!);
      if (leftScore > rightScore) { left.wins += 1; right.losses += 1; }
      else if (rightScore > leftScore) { right.wins += 1; left.losses += 1; }
      else { left.ties += 1; right.ties += 1; }
    }
    const rows = [...standings.entries()].map(([id, standing]) => ({ id, standing }));
    for (const [id, share] of recordLeaders(rows)) recordWins.set(id, recordWins.get(id)! + share);
    for (const [id, share] of pointLeaders(rows)) pointWins.set(id, pointWins.get(id)! + share);
    for (const [id, standing] of standings) {
      winSum.set(id, winSum.get(id)! + standing.wins);
      const label = formatRecord(standing.wins, standing.losses, standing.ties);
      const counts = recordCounts.get(id)!;
      counts.set(label, (counts.get(label) ?? 0) + 1);
    }
  }
  return {
    mode: "simulated",
    reason: null,
    cutoffWeek: ros.cutoffWeek,
    caveats,
    sims,
    teams: league.teams.map((team) => {
      const base = built.get(team.id)!;
      const through = replay.through.get(team.id) ?? emptyThrough();
      const counts = [...(recordCounts.get(team.id)?.entries() ?? [])].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
      return {
        ...blankTeam(team, through), ...base,
        projectedPoints: base.rosMean === null ? null : through.points + base.rosMean,
        pBestRecord: (recordWins.get(team.id) ?? 0) / sims,
        pMostPoints: (pointWins.get(team.id) ?? 0) / sims,
        expectedWins: (winSum.get(team.id) ?? 0) / sims,
        records: counts.slice(0, 3).map(([label, count]) => ({ label, probability: count / sims })),
      };
    }),
  };
}
