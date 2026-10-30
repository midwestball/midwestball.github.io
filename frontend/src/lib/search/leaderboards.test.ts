import { describe, expect, it } from "vitest";
import { boardGroupOf, matchesPositionFilter, rampHoldMin, resolveVolume, sortFantasyRankRows, sortLeaderboardRows } from "./leaderboards";
import { STATS_BY_GROUP } from "@/lib/catalog";
import type { LeaderboardRow } from "@/lib/payload";
const row = (id: string, percentile: number | null, rank = 1): LeaderboardRow => ({ playerId: id, name: id, team: "CHI", position: "WR", value: 10, percentile, denomYtd: 20, qualified: true, fantasyPosRank: rank });
describe("leaderboard policies", () => {
  it("splits discovery positions while sharing board identity", () => {
    expect(boardGroupOf("wr")).toBe(boardGroupOf("te"));
    expect(matchesPositionFilter("TE", "wr")).toBe(false);
    expect(matchesPositionFilter("TE", "te")).toBe(true);
  });
  it("uses completed-week ramp then holds after five weeks", () => {
    const stat = STATS_BY_GROUP.qb.find(s => s.minNBase != null)!;
    expect(rampHoldMin(stat, 3)).toBe(stat.minNBase! * 3);
    expect(rampHoldMin(stat, 8)).toBe(stat.minNBase! * 5);
    expect(rampHoldMin(stat, 0)).toBeNull();
  });
  it("keeps null percentiles last and fantasy rank direction separate", () => {
    const rows = [row("missing", null, 3), row("low", 20, 2), row("high", 90, 1)];
    expect(sortLeaderboardRows(rows, "best", true).map(r => r.playerId)).toEqual(["high", "low", "missing"]);
    expect(sortLeaderboardRows(rows, "worst", true).map(r => r.playerId)).toEqual(["low", "high", "missing"]);
    expect(sortFantasyRankRows(rows, "worst")[0].playerId).toBe("missing");
  });
  it("prefers the published volume sibling before denominator fallback", () => {
    expect(resolveVolume(row("a", 50), new Map([["a", 42]]))).toBe(42);
    expect(resolveVolume(row("a", 50), null)).toBe(20);
  });
});
