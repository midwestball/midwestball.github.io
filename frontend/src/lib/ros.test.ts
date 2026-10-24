import { afterEach, describe, expect, it, vi } from "vitest";
import { isRosSnapshot } from "./ros";
import { loadRosSnapshot } from "./projections";

const document = {
  schemaVersion: 1, kind: "ros", season: 2026, cutoffWeek: 6, snapshotId: "ros-test",
  generatedAt: "2026-10-20T00:00:00Z", modelVersion: "v1", scoringProfile: "ppr-v1",
  quantileLevels: [.05, .25, .5, .75, .95], methodology: "Test",
  entities: ["QB", "RB", "WR", "TE"].map(position => ({ playerId: position, position, name: position, team: "CHI", remainingTeamGames: 11, mean: 100, quantiles: [0, 20, 90, 150, 200] })),
};
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });
describe("ROS public contract", () => {
  it("accepts summaries but rejects crossed, negative and nonfinite quantiles or duplicate IDs", () => {
    expect(isRosSnapshot(document)).toBe(true);
    for (const quantiles of [[0, 100, 90, 150, 200], [-1, 20, 90, 150, 200], [0, 20, NaN, 150, 200]]) {
      expect(isRosSnapshot({ ...document, entities: [{ ...document.entities[0], quantiles }, ...document.entities.slice(1)] })).toBe(false);
    }
    expect(isRosSnapshot({ ...document, entities: [...document.entities, document.entities[0]] })).toBe(false);
  });
  it("loads optional ROS data relative to the weekly immutable index", async () => {
    vi.stubEnv("VIZ_STORAGE_BASE_URL", "https://example.test/storage/v1/object/public/test");
    const pointer = { schemaVersion: 1, season: 2026, week: 7, snapshotId: "ros-test", indexPath: "projections/2026/w7/ros-test/index.json", manifestPath: "projections/2026/w7/ros-test/manifest.json", generatedAt: document.generatedAt };
    const index = { ...pointer, trainedThrough: { season: 2026, week: 6 }, modelFamily: "crps_forest", modelVersion: "v1", scoringProfile: "ppr-v1", manifestPath: "manifest.json", rosPath: "ros.json", xGrid: [0, 1], entities: [], scoringDescriptions: Object.fromEntries(["QB", "RB", "WR", "TE", "K", "DST"].map(p => [p, "test"])), positionModelStatus: Object.fromEntries(["QB", "RB", "WR", "TE", "K", "DST"].map(p => [p, "promoted"])) };
    const fetch = vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith("current.json") ? pointer : url.endsWith("index.json") ? index : document), { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    expect((await loadRosSnapshot()).entities).toHaveLength(4);
    expect(fetch.mock.calls.map(c => c[0])).toContain("https://example.test/storage/v1/object/public/test/projections/2026/w7/ros-test/ros.json");
  });
  it("reports a useful unavailable state for an older weekly snapshot", async () => {
    vi.stubEnv("VIZ_STORAGE_BASE_URL", "https://older.test/storage/v1/object/public/test");
    const pointer = { schemaVersion: 1, season: 2026, week: 7, snapshotId: "old", indexPath: "projections/2026/w7/old/index.json", manifestPath: "projections/2026/w7/old/manifest.json", generatedAt: document.generatedAt };
    const index = { ...pointer, trainedThrough: { season: 2026, week: 6 }, modelFamily: "crps_forest", modelVersion: "v1", scoringProfile: "ppr-v1", manifestPath: "manifest.json", xGrid: [0, 1], entities: [], scoringDescriptions: Object.fromEntries(["QB", "RB", "WR", "TE", "K", "DST"].map(p => [p, "test"])), positionModelStatus: Object.fromEntries(["QB", "RB", "WR", "TE", "K", "DST"].map(p => [p, "promoted"])) };
    vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith("current.json") ? pointer : index), { status: 200 })));
    await expect(loadRosSnapshot()).rejects.toMatchObject({ kind: "unavailable" });
  });
});
