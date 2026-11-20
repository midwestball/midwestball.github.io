import { optimizeLineup, validSettings, type Lineup } from "@/lib/trades";
import type { RosPlayer, RosPosition, RosSnapshot } from "@/lib/ros";
import { playerDeviation, normalAtLeast, type LeagueProjection, type TeamProjection } from "./project";
import type { SavedLeague } from "./types";

export const POSITIONS: RosPosition[] = ["QB", "RB", "WR", "TE"];
/** Max players either side may send. */
export const MAX_PACKAGE_SIZE = 3;
/** For 3-player packages, only the top-N ROS means on each roster are enumerated (keeps search snappy). */
export const THREE_PACK_POOL = 10;

export type PositionGap = {
  position: RosPosition;
  teamMean: number;
  leagueMean: number;
  /** ±1σ on the position starter total. */
  teamSd: number;
  /** teamMean − leagueMean; negative means a relative weakness. */
  gap: number;
};

export type TeamStrength = {
  teamId: string;
  rosMean: number;
  rosSd: number;
  positions: PositionGap[];
};

export type GapOverlayRow = {
  position: RosPosition;
  leagueMean: number;
  beforeGap: number;
  afterGap: number;
  /** ±1σ on the after gap (after position SD; league mean treated as fixed). */
  afterError: number;
  deltaGap: number;
  /** ±1σ on the position delta with shared starters canceling. */
  deltaError: number;
};

export type StrengthOverlayRow = {
  teamId: string;
  beforeMean: number;
  beforeSd: number;
  afterMean: number | null;
  afterSd: number | null;
  deltaMean: number | null;
  /** ±1σ on after − before when this team is in the selected trade. */
  deltaError: number | null;
  involved: boolean;
};

export type TradeSide = {
  teamId: string;
  give: RosPlayer[];
  beforeMean: number;
  afterMean: number;
  beforeSd: number;
  afterSd: number;
  deltaMean: number;
  /** P(after ROS total > before), using lineup-diff variance. */
  pHelp: number;
  /** P(after ROS total < before). */
  pHurt: number;
  beforeLineup: Lineup;
  afterLineup: Lineup;
};

export type TradeRecommendation = {
  id: string;
  left: TradeSide;
  right: TradeSide;
  /** Higher is better for the favored (left) team under the current fairness. */
  score: number;
  fairnessPass: boolean;
};

export type RecommendOptions = {
  /** 0 = prefer even / slight mutual benefit; 1 = allow large hurt to the other team. */
  fairness: number;
  /** Max players either side can send in one package. */
  maxEachSide?: number;
  /** How many recommendations to keep. */
  limit?: number;
  /** When set, left team must give exactly these ROS player ids (order ignored). */
  forcedGiveIds?: string[];
};

function pool(team: TeamProjection): RosPlayer[] {
  const byId = new Map<string, RosPlayer>();
  for (const spot of team.lineup) {
    if (spot.player) byId.set(spot.player.playerId, spot.player);
  }
  for (const item of team.benched) byId.set(item.player.playerId, item.player);
  return [...byId.values()];
}

function lineupValue(players: RosPlayer[], settings: SavedLeague["rosterSettings"]): { mean: number; sd: number; lineup: Lineup } | null {
  if (!validSettings(settings) || !players.length) return null;
  try {
    const lineup = optimizeLineup(players, settings);
    const starters = lineup.assignments.flatMap((spot) => (spot.player ? [spot.player] : []));
    const mean = starters.reduce((sum, player) => sum + player.mean, 0);
    const sd = Math.sqrt(starters.reduce((sum, player) => sum + playerDeviation(player) ** 2, 0));
    return { mean, sd, lineup };
  } catch {
    return null;
  }
}

/** Position starter means for one team (FLEX/SUPERFLEX attributed to the player's real position). */
export function positionMeans(team: TeamProjection): Record<RosPosition, number> {
  const totals: Record<RosPosition, number> = { QB: 0, RB: 0, WR: 0, TE: 0 };
  for (const spot of team.lineup) {
    if (!spot.player) continue;
    totals[spot.player.position] += spot.player.mean;
  }
  return totals;
}

export function positionStatsFromLineup(lineup: Lineup): Record<RosPosition, { mean: number; sd: number }> {
  const means: Record<RosPosition, number> = { QB: 0, RB: 0, WR: 0, TE: 0 };
  const vars: Record<RosPosition, number> = { QB: 0, RB: 0, WR: 0, TE: 0 };
  for (const spot of lineup.assignments) {
    if (!spot.player) continue;
    const position = spot.player.position;
    means[position] += spot.player.mean;
    vars[position] += playerDeviation(spot.player) ** 2;
  }
  return {
    QB: { mean: means.QB, sd: Math.sqrt(vars.QB) },
    RB: { mean: means.RB, sd: Math.sqrt(vars.RB) },
    WR: { mean: means.WR, sd: Math.sqrt(vars.WR) },
    TE: { mean: means.TE, sd: Math.sqrt(vars.TE) },
  };
}

function startersAt(lineup: Lineup, position: RosPosition): RosPlayer[] {
  return lineup.assignments.flatMap((spot) => (spot.player && spot.player.position === position ? [spot.player] : []));
}

/** SD of after − before at one position when shared starters cancel. */
export function positionDeltaSd(before: Lineup, after: Lineup, position: RosPosition): number {
  const beforePlayers = startersAt(before, position);
  const afterPlayers = startersAt(after, position);
  const beforeIds = new Set(beforePlayers.map((player) => player.playerId));
  const afterIds = new Set(afterPlayers.map((player) => player.playerId));
  const byId = new Map<string, RosPlayer>();
  for (const player of [...beforePlayers, ...afterPlayers]) byId.set(player.playerId, player);
  let variance = 0;
  for (const id of beforeIds) {
    if (!afterIds.has(id)) variance += playerDeviation(byId.get(id)!) ** 2;
  }
  for (const id of afterIds) {
    if (!beforeIds.has(id)) variance += playerDeviation(byId.get(id)!) ** 2;
  }
  return Math.sqrt(variance);
}

export function analyzeTeamStrengths(league: SavedLeague, projection: LeagueProjection): TeamStrength[] {
  const usable = projection.teams.filter((team) => team.rosMean !== null && team.lineupError === null);
  if (!usable.length) return [];
  const leagueAvg: Record<RosPosition, number> = { QB: 0, RB: 0, WR: 0, TE: 0 };
  for (const team of usable) {
    const means = positionMeans(team);
    for (const position of POSITIONS) leagueAvg[position] += means[position];
  }
  for (const position of POSITIONS) leagueAvg[position] /= usable.length;

  return usable.map((team) => {
    const stats = positionStatsFromLineup({
      total: team.rosMedianSum ?? 0,
      assignments: team.lineup.map((spot) => ({ slot: spot.slot, player: spot.player })),
    });
    return {
      teamId: team.teamId,
      rosMean: team.rosMean ?? 0,
      rosSd: team.rosSd ?? 0,
      positions: POSITIONS.map((position) => ({
        position,
        teamMean: stats[position].mean,
        teamSd: stats[position].sd,
        leagueMean: leagueAvg[position],
        gap: stats[position].mean - leagueAvg[position],
      })),
    };
  });
}

/** Before/after position gaps for a team in a selected trade (league means held fixed). */
export function gapOverlayForSide(strength: TeamStrength, side: TradeSide): GapOverlayRow[] {
  const before = positionStatsFromLineup(side.beforeLineup);
  const after = positionStatsFromLineup(side.afterLineup);
  const leagueByPos = new Map(strength.positions.map((row) => [row.position, row.leagueMean]));
  return POSITIONS.map((position) => {
    const leagueMean = leagueByPos.get(position) ?? 0;
    const beforeGap = before[position].mean - leagueMean;
    const afterGap = after[position].mean - leagueMean;
    return {
      position,
      leagueMean,
      beforeGap,
      afterGap,
      afterError: after[position].sd,
      deltaGap: afterGap - beforeGap,
      deltaError: positionDeltaSd(side.beforeLineup, side.afterLineup, position),
    };
  });
}

/** League ROS means with after totals + delta uncertainty for teams in the selected trade. */
export function strengthOverlayForTrade(strengths: TeamStrength[], trade: TradeRecommendation): StrengthOverlayRow[] {
  const byId = new Map([
    [trade.left.teamId, trade.left],
    [trade.right.teamId, trade.right],
  ]);
  return strengths.map((row) => {
    const side = byId.get(row.teamId);
    if (!side) {
      return {
        teamId: row.teamId,
        beforeMean: row.rosMean,
        beforeSd: row.rosSd,
        afterMean: null,
        afterSd: null,
        deltaMean: null,
        deltaError: null,
        involved: false,
      };
    }
    return {
      teamId: row.teamId,
      beforeMean: side.beforeMean,
      beforeSd: side.beforeSd,
      afterMean: side.afterMean,
      afterSd: side.afterSd,
      deltaMean: side.deltaMean,
      deltaError: diffSd(side.beforeLineup, side.afterLineup),
      involved: true,
    };
  });
}

function starterIds(lineup: Lineup): Set<string> {
  return new Set(lineup.assignments.flatMap((spot) => (spot.player ? [spot.player.playerId] : [])));
}

/** Variance of after − before when shared starters cancel. */
function diffSd(before: Lineup, after: Lineup): number {
  const beforeSet = starterIds(before);
  const afterSet = starterIds(after);
  const byId = new Map<string, RosPlayer>();
  for (const spot of [...before.assignments, ...after.assignments]) {
    if (spot.player) byId.set(spot.player.playerId, spot.player);
  }
  let variance = 0;
  for (const id of beforeSet) {
    if (!afterSet.has(id)) variance += playerDeviation(byId.get(id)!) ** 2;
  }
  for (const id of afterSet) {
    if (!beforeSet.has(id)) variance += playerDeviation(byId.get(id)!) ** 2;
  }
  return Math.sqrt(variance);
}

function sideStats(
  teamId: string,
  give: RosPlayer[],
  before: NonNullable<ReturnType<typeof lineupValue>>,
  after: NonNullable<ReturnType<typeof lineupValue>>,
): TradeSide {
  const deltaMean = after.mean - before.mean;
  const sd = diffSd(before.lineup, after.lineup);
  const pHelp = normalAtLeast(deltaMean, Math.max(sd, 1e-6), 0);
  const pHurt = 1 - pHelp;
  return {
    teamId,
    give,
    beforeMean: before.mean,
    afterMean: after.mean,
    beforeSd: before.sd,
    afterSd: after.sd,
    deltaMean,
    pHelp,
    pHurt,
    beforeLineup: before.lineup,
    afterLineup: after.lineup,
  };
}

function combinations<T>(items: T[], size: number): T[][] {
  if (size <= 0) return [[]];
  if (size > items.length) return [];
  if (size === items.length) return [items.slice()];
  const out: T[][] = [];
  const walk = (start: number, chosen: T[]) => {
    if (chosen.length === size) {
      out.push(chosen.slice());
      return;
    }
    for (let index = start; index < items.length; index += 1) {
      chosen.push(items[index]!);
      walk(index + 1, chosen);
      chosen.pop();
    }
  };
  walk(0, []);
  return out;
}

function poolForSize(players: RosPlayer[], size: number): RosPlayer[] {
  if (size < 3 || players.length <= THREE_PACK_POOL) return players;
  return [...players]
    .sort((a, b) => b.mean - a.mean || a.playerId.localeCompare(b.playerId))
    .slice(0, THREE_PACK_POOL);
}

function packageCombos(players: RosPlayer[], size: number): RosPlayer[][] {
  return combinations(poolForSize(players, size), size);
}

export function clampPackageSize(value: number): number {
  return Math.min(MAX_PACKAGE_SIZE, Math.max(1, Math.round(value)));
}

/** Soft floor on the other team's ROS mean change: ~−2 at fairness 0, ~−120 at fairness 1. */
export function otherDeltaFloor(fairness: number): number {
  const t = Math.min(1, Math.max(0, fairness));
  return -2 - t * 118;
}

/** How large a package-value gap (their loss vs your gain) is tolerated. */
export function unfairnessBudget(fairness: number, userGain: number): number {
  const t = Math.min(1, Math.max(0, fairness));
  return Math.max(0, userGain) * (0.35 + t * 4) + t * 40;
}

function passesFairness(left: TradeSide, right: TradeSide, fairness: number): boolean {
  if (!(left.deltaMean > 0.25)) return false;
  if (right.deltaMean < otherDeltaFloor(fairness)) return false;
  const theirLoss = Math.max(0, -right.deltaMean);
  if (theirLoss > unfairnessBudget(fairness, left.deltaMean)) return false;
  // At low fairness, prefer deals that do not crush the counterparty's P(help).
  if (fairness < 0.35 && right.pHurt > 0.72 && right.deltaMean < -1) return false;
  return true;
}

function scoreTrade(left: TradeSide, right: TradeSide, fairness: number): number {
  const t = Math.min(1, Math.max(0, fairness));
  const mutual = Math.min(left.deltaMean, Math.max(0, right.deltaMean));
  const theirLoss = Math.max(0, -right.deltaMean);
  return (
    left.deltaMean * (0.55 + 0.35 * left.pHelp) +
    mutual * (1 - t) * 0.85 -
    theirLoss * (1 - t) * 1.15 -
    theirLoss * t * 0.08 +
    left.deltaMean * t * 0.55
  );
}

function applySwap(leftPool: RosPlayer[], rightPool: RosPlayer[], giveLeft: RosPlayer[], giveRight: RosPlayer[]) {
  const leftIds = new Set(giveLeft.map((player) => player.playerId));
  const rightIds = new Set(giveRight.map((player) => player.playerId));
  const nextLeft = [...leftPool.filter((player) => !leftIds.has(player.playerId)), ...giveRight];
  const nextRight = [...rightPool.filter((player) => !rightIds.has(player.playerId)), ...giveLeft];
  return { nextLeft, nextRight };
}

function packageKey(give: RosPlayer[]): string {
  return give.map((player) => player.playerId).sort().join("+") || "none";
}

export function recommendTrades(
  league: SavedLeague,
  projection: LeagueProjection,
  leftTeamId: string,
  rightTeamId: string,
  options: RecommendOptions,
): TradeRecommendation[] {
  if (projection.mode === "blocked" || leftTeamId === rightTeamId) return [];
  if (!validSettings(league.rosterSettings)) return [];
  const leftRow = projection.teams.find((team) => team.teamId === leftTeamId);
  const rightRow = projection.teams.find((team) => team.teamId === rightTeamId);
  if (!leftRow || !rightRow || leftRow.lineupError || rightRow.lineupError) return [];

  const leftPool = pool(leftRow);
  const rightPool = pool(rightRow);
  const beforeLeft = lineupValue(leftPool, league.rosterSettings);
  const beforeRight = lineupValue(rightPool, league.rosterSettings);
  if (!beforeLeft || !beforeRight) return [];

  const fairness = options.fairness ?? 0;
  const maxEach = clampPackageSize(options.maxEachSide ?? 2);
  const limit = Math.min(40, Math.max(1, options.limit ?? 8));
  const forced = options.forcedGiveIds ? new Set(options.forcedGiveIds) : null;

  const leftCombos: RosPlayer[][] = [];
  if (forced) {
    const chosen = leftPool.filter((player) => forced.has(player.playerId));
    if (chosen.length !== forced.size || chosen.length === 0 || chosen.length > maxEach) return [];
    leftCombos.push(chosen);
  } else {
    for (let size = 1; size <= maxEach; size += 1) leftCombos.push(...packageCombos(leftPool, size));
  }

  const results: TradeRecommendation[] = [];
  for (const giveLeft of leftCombos) {
    for (let size = 1; size <= maxEach; size += 1) {
      // Allow uneven packages, but skip empty-for-empty and pure dump unless forced give.
      for (const giveRight of packageCombos(rightPool, size)) {
        if (!giveLeft.length && !giveRight.length) continue;
        const { nextLeft, nextRight } = applySwap(leftPool, rightPool, giveLeft, giveRight);
        const afterLeft = lineupValue(nextLeft, league.rosterSettings);
        const afterRight = lineupValue(nextRight, league.rosterSettings);
        if (!afterLeft || !afterRight) continue;
        const left = sideStats(leftTeamId, giveLeft, beforeLeft, afterLeft);
        const right = sideStats(rightTeamId, giveRight, beforeRight, afterRight);
        if (!passesFairness(left, right, fairness)) continue;
        results.push({
          id: `${packageKey(giveLeft)}>${packageKey(giveRight)}`,
          left,
          right,
          score: scoreTrade(left, right, fairness),
          fairnessPass: true,
        });
      }
    }
  }

  results.sort((a, b) => b.score - a.score || b.left.deltaMean - a.left.deltaMean || a.right.deltaMean - b.right.deltaMean);
  const seen = new Set<string>();
  const unique: TradeRecommendation[] = [];
  for (const row of results) {
    if (seen.has(row.id)) continue;
    seen.add(row.id);
    unique.push(row);
    if (unique.length >= limit) break;
  }
  return unique;
}

/** Best trades for the favored team against every other club. */
export function recommendForTeam(
  league: SavedLeague,
  projection: LeagueProjection,
  yourTeamId: string,
  options: RecommendOptions & { partnerId?: string | null },
): TradeRecommendation[] {
  const partners = options.partnerId
    ? [options.partnerId]
    : league.teams.map((team) => team.id).filter((id) => id !== yourTeamId);
  const perPartner = Math.max(2, Math.ceil((options.limit ?? 8) / Math.max(1, partners.length)));
  const merged: TradeRecommendation[] = [];
  for (const partnerId of partners) {
    merged.push(...recommendTrades(league, projection, yourTeamId, partnerId, { ...options, limit: perPartner }));
  }
  merged.sort((a, b) => b.score - a.score);
  return merged.slice(0, options.limit ?? 8);
}

export function tradeablePlayers(projection: LeagueProjection, teamId: string): RosPlayer[] {
  const row = projection.teams.find((team) => team.teamId === teamId);
  return row ? pool(row) : [];
}

/** Guard used by callers that already loaded ROS; season mismatch is handled by projectLeague. */
export function canRecommend(_ros: RosSnapshot | null, projection: LeagueProjection | null): boolean {
  return !!projection && projection.mode !== "blocked";
}
