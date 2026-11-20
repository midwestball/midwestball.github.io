import { describe, expect, it } from "vitest";
import type { RosPlayer, RosPosition, RosSnapshot } from "@/lib/ros";
import { projectLeague } from "./project";
import {
  analyzeTeamStrengths,
  clampPackageSize,
  gapOverlayForSide,
  otherDeltaFloor,
  recommendTrades,
  strengthOverlayForTrade,
  unfairnessBudget,
} from "./recommend-trades";
import type { SavedLeague } from "./types";

function player(playerId: string, position: RosPosition, mean: number, name = playerId): RosPlayer {
  const q = mean;
  return {
    playerId,
    name,
    position,
    team: "CHI",
    remainingTeamGames: 8,
    mean,
    quantiles: [q - 20, q - 10, q, q + 10, q + 20],
  };
}

function snapshot(entities: RosPlayer[]): RosSnapshot {
  return {
    schemaVersion: 1,
    kind: "ros",
    snapshotId: "snap",
    season: 2026,
    cutoffWeek: 1,
    generatedAt: "2026-11-01T00:00:00Z",
    modelVersion: "test",
    scoringProfile: "ppr-v1",
    quantileLevels: [0.05, 0.25, 0.5, 0.75, 0.95],
    methodology: "test",
    entities,
  };
}

function leagueOf(teams: SavedLeague["teams"]): SavedLeague {
  return {
    version: 1,
    id: "sleeper:10:2026",
    provider: "sleeper",
    providerLeagueId: "10",
    season: 2026,
    name: "Friends",
    importedAt: "2026-11-14T00:00:00Z",
    selectedTeamId: "1",
    selectionSource: "manual",
    asOfWeek: 2,
    receptionPoints: 1,
    playoffWeekStart: 15,
    notes: [],
    unsupportedSlots: [],
    rosterSettings: { QB: 1, RB: 1, WR: 1, TE: 0, FLEX: 0, SUPERFLEX: 0, bench: 2, ir: 0, K: 0, DST: 0 },
    teams,
    matchups: [
      { week: 1, matchupId: "a", teamId: "1", points: 100 },
      { week: 1, matchupId: "a", teamId: "2", points: 90 },
    ],
  };
}

describe("recommend-trades", () => {
  it("widens the other-team hurt floor as fairness rises", () => {
    expect(otherDeltaFloor(0)).toBeCloseTo(-2, 5);
    expect(otherDeltaFloor(1)).toBeCloseTo(-120, 5);
    expect(unfairnessBudget(0, 10)).toBeLessThan(unfairnessBudget(1, 10));
  });

  it("finds a fair 1-for-1 that helps the weaker team's need", () => {
    // Alpha is RB-poor / WR-deep; Beta is WR-poor / RB-deep — a classic mutually helpful swap.
    const ros = snapshot([
      player("qb-a", "QB", 70, "Alpha QB"),
      player("rb-weak", "RB", 30, "Weak RB"),
      player("wr-a1", "WR", 80, "Alpha WR1"),
      player("wr-a2", "WR", 75, "Alpha WR2"),
      player("qb-b", "QB", 70, "Beta QB"),
      player("rb-b1", "RB", 85, "Beta RB1"),
      player("rb-b2", "RB", 80, "Beta RB2"),
      player("wr-weak", "WR", 25, "Weak WR"),
    ]);
    const league = leagueOf([
      {
        id: "1",
        name: "Alpha",
        manager: "A",
        wins: 1,
        losses: 0,
        ties: 0,
        points: 100,
        players: [
          { providerPlayerId: "1", name: "Alpha QB", position: "QB", nflTeam: "CHI", gsisId: "qb-a", ir: false, taxi: false },
          { providerPlayerId: "2", name: "Weak RB", position: "RB", nflTeam: "CHI", gsisId: "rb-weak", ir: false, taxi: false },
          { providerPlayerId: "3", name: "Alpha WR1", position: "WR", nflTeam: "CHI", gsisId: "wr-a1", ir: false, taxi: false },
          { providerPlayerId: "4", name: "Alpha WR2", position: "WR", nflTeam: "CHI", gsisId: "wr-a2", ir: false, taxi: false },
        ],
      },
      {
        id: "2",
        name: "Beta",
        manager: "B",
        wins: 0,
        losses: 1,
        ties: 0,
        points: 90,
        players: [
          { providerPlayerId: "5", name: "Beta QB", position: "QB", nflTeam: "CHI", gsisId: "qb-b", ir: false, taxi: false },
          { providerPlayerId: "6", name: "Beta RB1", position: "RB", nflTeam: "CHI", gsisId: "rb-b1", ir: false, taxi: false },
          { providerPlayerId: "7", name: "Beta RB2", position: "RB", nflTeam: "CHI", gsisId: "rb-b2", ir: false, taxi: false },
          { providerPlayerId: "8", name: "Weak WR", position: "WR", nflTeam: "CHI", gsisId: "wr-weak", ir: false, taxi: false },
        ],
      },
    ]);
    const projection = projectLeague(league, ros, { sims: 20, seed: 1 });
    const strengths = analyzeTeamStrengths(league, projection);
    const alpha = strengths.find((row) => row.teamId === "1")!;
    expect(alpha.positions.find((row) => row.position === "RB")!.gap).toBeLessThan(0);

    const fair = recommendTrades(league, projection, "1", "2", { fairness: 0, limit: 8, maxEachSide: 1 });
    expect(fair.length).toBeGreaterThan(0);
    expect(fair.every((trade) => trade.left.deltaMean > 0)).toBe(true);
    expect(fair.every((trade) => trade.right.deltaMean >= otherDeltaFloor(0) - 1e-9)).toBe(true);
    expect(fair.some((trade) => trade.right.deltaMean > 0)).toBe(true);

    const forced = recommendTrades(league, projection, "1", "2", {
      fairness: 0,
      limit: 8,
      maxEachSide: 1,
      forcedGiveIds: ["wr-a2"],
    });
    expect(forced.length).toBeGreaterThan(0);
    expect(forced.every((trade) => trade.left.give.some((player) => player.playerId === "wr-a2"))).toBe(true);
  });

  it("returns nothing when fairness forbids crushing the partner", () => {
    const ros = snapshot([
      player("star", "RB", 120, "Star"),
      player("scrub", "RB", 10, "Scrub"),
      player("qb1", "QB", 60, "QB1"),
      player("qb2", "QB", 55, "QB2"),
      player("wr1", "WR", 40, "WR1"),
      player("wr2", "WR", 35, "WR2"),
    ]);
    const league = leagueOf([
      {
        id: "1",
        name: "Need",
        manager: "A",
        wins: 0,
        losses: 0,
        ties: 0,
        points: 0,
        players: [
          { providerPlayerId: "1", name: "QB1", position: "QB", nflTeam: "CHI", gsisId: "qb1", ir: false, taxi: false },
          { providerPlayerId: "2", name: "Scrub", position: "RB", nflTeam: "CHI", gsisId: "scrub", ir: false, taxi: false },
          { providerPlayerId: "3", name: "WR1", position: "WR", nflTeam: "CHI", gsisId: "wr1", ir: false, taxi: false },
        ],
      },
      {
        id: "2",
        name: "Has",
        manager: "B",
        wins: 0,
        losses: 0,
        ties: 0,
        points: 0,
        players: [
          { providerPlayerId: "4", name: "QB2", position: "QB", nflTeam: "CHI", gsisId: "qb2", ir: false, taxi: false },
          { providerPlayerId: "5", name: "Star", position: "RB", nflTeam: "CHI", gsisId: "star", ir: false, taxi: false },
          { providerPlayerId: "6", name: "WR2", position: "WR", nflTeam: "CHI", gsisId: "wr2", ir: false, taxi: false },
        ],
      },
    ]);
    const projection = projectLeague(league, ros, { sims: 10, seed: 2 });
    const strict = recommendTrades(league, projection, "1", "2", {
      fairness: 0,
      limit: 20,
      maxEachSide: 1,
      forcedGiveIds: ["scrub"],
    });
    // Scrub-for-Star is a huge steal; fairness 0 should reject it.
    expect(strict.every((trade) => !trade.right.give.some((player) => player.playerId === "star"))).toBe(true);

    const loose = recommendTrades(league, projection, "1", "2", {
      fairness: 1,
      limit: 20,
      maxEachSide: 1,
      forcedGiveIds: ["scrub"],
    });
    expect(loose.some((trade) => trade.right.give.some((player) => player.playerId === "star"))).toBe(true);
  });

  it("clamps package size and can search up to 3-player packages", () => {
    expect(clampPackageSize(0)).toBe(1);
    expect(clampPackageSize(2.4)).toBe(2);
    expect(clampPackageSize(9)).toBe(3);

    const ros = snapshot([
      player("qb-a", "QB", 70, "Alpha QB"),
      player("rb-a1", "RB", 25, "A RB1"),
      player("rb-a2", "RB", 20, "A RB2"),
      player("wr-a1", "WR", 55, "A WR1"),
      player("wr-a2", "WR", 50, "A WR2"),
      player("wr-a3", "WR", 45, "A WR3"),
      player("qb-b", "QB", 65, "Beta QB"),
      player("rb-b1", "RB", 80, "B RB1"),
      player("rb-b2", "RB", 70, "B RB2"),
      player("rb-b3", "RB", 60, "B RB3"),
      player("wr-b1", "WR", 30, "B WR1"),
      player("wr-b2", "WR", 22, "B WR2"),
    ]);
    const league = leagueOf([
      {
        id: "1",
        name: "Alpha",
        manager: "A",
        wins: 1,
        losses: 0,
        ties: 0,
        points: 100,
        players: [
          { providerPlayerId: "1", name: "Alpha QB", position: "QB", nflTeam: "CHI", gsisId: "qb-a", ir: false, taxi: false },
          { providerPlayerId: "2", name: "A RB1", position: "RB", nflTeam: "CHI", gsisId: "rb-a1", ir: false, taxi: false },
          { providerPlayerId: "3", name: "A RB2", position: "RB", nflTeam: "CHI", gsisId: "rb-a2", ir: false, taxi: false },
          { providerPlayerId: "4", name: "A WR1", position: "WR", nflTeam: "CHI", gsisId: "wr-a1", ir: false, taxi: false },
          { providerPlayerId: "5", name: "A WR2", position: "WR", nflTeam: "CHI", gsisId: "wr-a2", ir: false, taxi: false },
          { providerPlayerId: "6", name: "A WR3", position: "WR", nflTeam: "CHI", gsisId: "wr-a3", ir: false, taxi: false },
        ],
      },
      {
        id: "2",
        name: "Beta",
        manager: "B",
        wins: 0,
        losses: 1,
        ties: 0,
        points: 90,
        players: [
          { providerPlayerId: "7", name: "Beta QB", position: "QB", nflTeam: "CHI", gsisId: "qb-b", ir: false, taxi: false },
          { providerPlayerId: "8", name: "B RB1", position: "RB", nflTeam: "CHI", gsisId: "rb-b1", ir: false, taxi: false },
          { providerPlayerId: "9", name: "B RB2", position: "RB", nflTeam: "CHI", gsisId: "rb-b2", ir: false, taxi: false },
          { providerPlayerId: "10", name: "B RB3", position: "RB", nflTeam: "CHI", gsisId: "rb-b3", ir: false, taxi: false },
          { providerPlayerId: "11", name: "B WR1", position: "WR", nflTeam: "CHI", gsisId: "wr-b1", ir: false, taxi: false },
          { providerPlayerId: "12", name: "B WR2", position: "WR", nflTeam: "CHI", gsisId: "wr-b2", ir: false, taxi: false },
        ],
      },
    ]);
    const projection = projectLeague(league, ros, { sims: 10, seed: 3 });
    const trades = recommendTrades(league, projection, "1", "2", { fairness: 0.85, limit: 20, maxEachSide: 3 });
    expect(trades.length).toBeGreaterThan(0);
    expect(trades.every((trade) => trade.left.give.length <= 3 && trade.right.give.length <= 3)).toBe(true);

    const threeOut = recommendTrades(league, projection, "1", "2", {
      fairness: 1,
      limit: 12,
      maxEachSide: 3,
      forcedGiveIds: ["wr-a1", "wr-a2", "wr-a3"],
    });
    expect(threeOut.length).toBeGreaterThan(0);
    expect(threeOut.every((trade) => trade.left.give.length === 3)).toBe(true);
    expect(threeOut.some((trade) => trade.right.give.length >= 1)).toBe(true);
  });

  it("builds gap and strength overlays with error bars for a selected trade", () => {
    const ros = snapshot([
      player("qb-a", "QB", 70, "Alpha QB"),
      player("rb-weak", "RB", 30, "Weak RB"),
      player("wr-a1", "WR", 80, "Alpha WR1"),
      player("wr-a2", "WR", 75, "Alpha WR2"),
      player("qb-b", "QB", 70, "Beta QB"),
      player("rb-b1", "RB", 85, "Beta RB1"),
      player("rb-b2", "RB", 80, "Beta RB2"),
      player("wr-weak", "WR", 25, "Weak WR"),
    ]);
    const league = leagueOf([
      {
        id: "1",
        name: "Alpha",
        manager: "A",
        wins: 1,
        losses: 0,
        ties: 0,
        points: 100,
        players: [
          { providerPlayerId: "1", name: "Alpha QB", position: "QB", nflTeam: "CHI", gsisId: "qb-a", ir: false, taxi: false },
          { providerPlayerId: "2", name: "Weak RB", position: "RB", nflTeam: "CHI", gsisId: "rb-weak", ir: false, taxi: false },
          { providerPlayerId: "3", name: "Alpha WR1", position: "WR", nflTeam: "CHI", gsisId: "wr-a1", ir: false, taxi: false },
          { providerPlayerId: "4", name: "Alpha WR2", position: "WR", nflTeam: "CHI", gsisId: "wr-a2", ir: false, taxi: false },
        ],
      },
      {
        id: "2",
        name: "Beta",
        manager: "B",
        wins: 0,
        losses: 1,
        ties: 0,
        points: 90,
        players: [
          { providerPlayerId: "5", name: "Beta QB", position: "QB", nflTeam: "CHI", gsisId: "qb-b", ir: false, taxi: false },
          { providerPlayerId: "6", name: "Beta RB1", position: "RB", nflTeam: "CHI", gsisId: "rb-b1", ir: false, taxi: false },
          { providerPlayerId: "7", name: "Beta RB2", position: "RB", nflTeam: "CHI", gsisId: "rb-b2", ir: false, taxi: false },
          { providerPlayerId: "8", name: "Weak WR", position: "WR", nflTeam: "CHI", gsisId: "wr-weak", ir: false, taxi: false },
        ],
      },
    ]);
    const projection = projectLeague(league, ros, { sims: 10, seed: 4 });
    const strengths = analyzeTeamStrengths(league, projection);
    const trades = recommendTrades(league, projection, "1", "2", { fairness: 0, limit: 5, maxEachSide: 1 });
    expect(trades.length).toBeGreaterThan(0);
    const trade = trades[0]!;
    const alpha = strengths.find((row) => row.teamId === "1")!;
    const gaps = gapOverlayForSide(alpha, trade.left);
    expect(gaps).toHaveLength(4);
    expect(gaps.every((row) => row.afterError >= 0 && row.deltaError >= 0)).toBe(true);
    expect(gaps.reduce((sum, row) => sum + row.deltaGap, 0)).toBeCloseTo(trade.left.deltaMean, 5);

    const overlay = strengthOverlayForTrade(strengths, trade);
    const left = overlay.find((row) => row.teamId === "1")!;
    const right = overlay.find((row) => row.teamId === "2")!;
    expect(left.involved).toBe(true);
    expect(right.involved).toBe(true);
    expect(left.afterMean).toBeCloseTo(trade.left.afterMean, 5);
    expect(left.deltaError).toBeGreaterThan(0);
    expect(right.deltaMean).toBeCloseTo(trade.right.deltaMean, 5);
  });
});
