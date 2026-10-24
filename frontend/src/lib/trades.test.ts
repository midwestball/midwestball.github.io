import { describe, expect, it } from "vitest";
import { DEFAULT_SETTINGS, evaluateTrade, optimizeLineup, restoreRoster, type RosterSettings } from "./trades";
import type { RosPlayer, RosPosition } from "./ros";

const player = (playerId: string, position: RosPosition, median: number): RosPlayer => ({ playerId, name: playerId, position, team: "CHI", remainingTeamGames: 10, mean: median + 5, quantiles: [0, median / 2, median, median * 1.5, median * 2] });
const settings = (extra: Partial<RosterSettings>): RosterSettings => ({ ...DEFAULT_SETTINGS, QB: 0, RB: 0, WR: 0, TE: 0, FLEX: 0, SUPERFLEX: 0, ...extra });

describe("median trade analysis", () => {
  it("reassigns players across FLEX rather than greedily blocking a starter", () => {
    const ps = [player("rb", "RB", 100), player("wr", "WR", 90), player("te", "TE", 80)];
    const result = optimizeLineup(ps, settings({ RB: 1, FLEX: 1 }));
    expect(result.total).toBe(190);
    expect(result.assignments.map(a => a.player?.playerId)).toEqual(["rb", "wr"]);
  });
  it("allows a second QB only in superflex or a second QB slot", () => {
    const ps = [player("q1", "QB", 200), player("q2", "QB", 180), player("w", "WR", 100)];
    expect(optimizeLineup(ps, settings({ QB: 1, FLEX: 1 })).total).toBe(300);
    expect(optimizeLineup(ps, settings({ QB: 1, SUPERFLEX: 1 })).total).toBe(380);
  });
  it("shows why a two-for-one package gain can lose starting points", () => {
    const ps = [player("out", "RB", 130), player("in", "RB", 80), player("depth", "WR", 80), player("starter", "WR", 100)];
    const roster = ["out", "starter"].map(playerId => ({ playerId, ir: false }));
    const result = evaluateTrade(ps, roster, ["out"], ["in", "depth"], [], settings({ RB: 1, WR: 1 }));
    expect(result.packageDelta).toBe(30);
    expect(result.lineupDelta).toBe(-50);
  });
  it("excludes IR and cancels unchanged starters", () => {
    const ps = [player("ir", "RB", 200), player("a", "RB", 80), player("b", "RB", 100), player("w", "WR", 90)];
    const result = evaluateTrade(ps, [{ playerId: "ir", ir: true }, { playerId: "a", ir: false }, { playerId: "w", ir: false }], ["a"], ["b"], [], settings({ RB: 1, WR: 1 }));
    expect(result.before.total).toBe(170);
    expect(result.lineupDelta).toBe(20);
  });
  it("requires a drop for an over-capacity two-for-one and charges its value", () => {
    const ps = [player("a", "RB", 100), player("bench", "WR", 50), player("b", "RB", 90), player("c", "WR", 80)];
    const roster = ["a", "bench"].map(playerId => ({ playerId, ir: false }));
    const s = settings({ RB: 1, bench: 1 });
    expect(() => evaluateTrade(ps, roster, ["a"], ["b", "c"], [], s)).toThrow(/limit/);
    expect(evaluateTrade(ps, roster, ["a"], ["b", "c"], ["bench"], s).rosterDelta).toBe(20);
  });
  it("rejects duplicate players, own-player receipts, missing projections and excess IR", () => {
    const ps = [player("a", "RB", 10), player("b", "RB", 20)];
    const roster = [{ playerId: "a", ir: false }];
    const s = settings({ RB: 1 });
    expect(() => evaluateTrade(ps, roster, ["a", "a"], ["b"], [], s)).toThrow(/once/);
    expect(() => evaluateTrade(ps, roster, [], ["a"], [], s)).toThrow(/outside/);
    expect(() => evaluateTrade(ps, roster, ["a"], ["missing"], [], s)).toThrow(/unavailable/);
    expect(() => evaluateTrade(ps, [{ playerId: "a", ir: true }], [], ["b"], [], { ...s, ir: 0 })).toThrow(/IR/);
  });
  it("treats empty slots as zero and uses medians rather than means", () => {
    const lineup = optimizeLineup([player("a", "WR", 20)], settings({ WR: 2 }));
    expect(lineup.total).toBe(20);
    expect(lineup.assignments.filter(a => !a.player)).toHaveLength(1);
  });
  it("validates saved rosters before restoring them", () => {
    expect(restoreRoster({ version: 1, settings: DEFAULT_SETTINGS, roster: [{ playerId: "a", ir: false }] })).not.toBeNull();
    expect(restoreRoster({ version: 1, settings: { ...DEFAULT_SETTINGS, SUPERFLEX: 100 }, roster: [] })).toBeNull();
    expect(restoreRoster({ version: 1, settings: DEFAULT_SETTINGS, roster: [{ playerId: "a", ir: "false" }] })).toBeNull();
  });
  it("agrees with exhaustive assignments on mixed flex/superflex rosters", () => {
    const slots = ["RB", "WR", "FLEX", "SUPERFLEX"] as const;
    for (let seed = 0; seed < 20; seed++) {
      const positions: RosPosition[] = ["QB", "RB", "RB", "WR", "WR", "TE", "QB"];
      const ps = positions.map((pos, i) => player(String(i), pos, (seed * 37 + i * 23) % 101));
      function brute(index: number, used: Set<string>): number {
        if (index === slots.length) return 0;
        const slot = slots[index];
        let best = brute(index + 1, used);
        for (const p of ps) {
          if (used.has(p.playerId) || !(slot === "SUPERFLEX" || slot === p.position || (slot === "FLEX" && p.position !== "QB"))) continue;
          best = Math.max(best, p.quantiles[2] + brute(index + 1, new Set([...used, p.playerId])));
        }
        return best;
      }
      expect(optimizeLineup(ps, settings({ RB: 1, WR: 1, FLEX: 1, SUPERFLEX: 1 })).total).toBe(brute(0, new Set()));
    }
  });
});
