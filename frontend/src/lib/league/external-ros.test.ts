import { describe, expect, it } from "vitest";
import {
  externalRos,
  formatSourceLine,
  rankingPoints,
  remapRosPlayer,
  sourceProjection,
} from "./external-ros";
import type { RosPlayer } from "@/lib/ros";

function player(overrides: Partial<RosPlayer> & Pick<RosPlayer, "playerId" | "name">): RosPlayer {
  return {
    position: "WR",
    team: "CIN",
    remainingTeamGames: 8,
    mean: 129.42,
    quantiles: [29.7, 99.0, 124.6, 167.0, 222.6],
    ...overrides,
  };
}

describe("external ros helpers", () => {
  it("loads the hardcoded snapshot", () => {
    expect(externalRos.kind).toBe("external-ros");
    expect(externalRos.horizonEndWeek).toBeGreaterThanOrEqual(externalRos.horizonStartWeek);
    expect(Object.keys(externalRos.players).length).toBeGreaterThan(100);
  });

  it("blends midwestball with sleeper and espn when present", () => {
    const chaseId = Object.entries(externalRos.players).find(([, row]) => row.name === "Ja'Marr Chase")?.[0];
    expect(chaseId).toBeTruthy();
    const row = externalRos.players[chaseId!];
    const chase = player({
      playerId: chaseId!,
      name: "Ja'Marr Chase",
      mean: 129.42,
      quantiles: [29.7, 99.0, 124.6, 167.0, 222.6],
    });
    const proj = sourceProjection(chase);
    expect(proj.midwestball).toBeCloseTo(129.42, 2);
    expect(proj.sleeper).toBe(row.sleeper);
    expect(proj.espn).toBe(row.espn);
    if (row.sleeper != null && row.espn != null) {
      expect(proj.sourceCount).toBe(3);
      expect(proj.blend).toBeCloseTo((129.42 + row.sleeper + row.espn) / 3, 5);
      expect(rankingPoints(chase, "sleeper")).toBe(row.sleeper);
      expect(rankingPoints(chase, "espn")).toBe(row.espn);
      expect(rankingPoints(chase, "mean")).toBeCloseTo(proj.blend, 5);
      const remapped = remapRosPlayer(chase, "sleeper");
      expect(remapped.mean).toBe(row.sleeper);
      expect(formatSourceLine(remapped, chase)).toContain("MB 129.4");
    }
    expect(formatSourceLine(chase)).toContain("MB");
  });
});
