import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LEAGUE_STORAGE_KEY, upsertLeague, EMPTY_LEAGUE_STORE } from "@/lib/league/store";
import type { SavedLeague } from "@/lib/league/types";
import type { RosSnapshot } from "@/lib/ros";
import { LeagueLabClient } from "./LeagueLabClient";

const snapshot: RosSnapshot = {
  schemaVersion: 1, kind: "ros", snapshotId: "snap", season: 2026, cutoffWeek: 1,
  generatedAt: "2026-11-01T00:00:00Z", modelVersion: "test", scoringProfile: "ppr-v1",
  quantileLevels: [0.05, 0.25, 0.5, 0.75, 0.95], methodology: "Test",
  entities: ["QB", "RB", "WR", "TE"].map((position) => ({
    playerId: position, name: `Player ${position}`, position: position as "QB", team: "CHI",
    remainingTeamGames: 1, mean: position === "QB" ? 40 : 10, quantiles: [1, 2, 3, 4, 5],
  })),
};
vi.mock("@/components/projections/useRos", () => ({ useRos: () => ({ snapshot, error: "", retry: vi.fn() }) }));

const saved: SavedLeague = {
  version: 1, id: "sleeper:10:2026", provider: "sleeper", providerLeagueId: "10", season: 2026, name: "Saved Friends",
  importedAt: "2026-11-14T00:00:00Z", selectedTeamId: null, selectionSource: null, asOfWeek: 10, receptionPoints: 0.5,
  playoffWeekStart: 3, notes: [], unsupportedSlots: [],
  rosterSettings: { QB: 1, RB: 0, WR: 0, TE: 0, FLEX: 0, SUPERFLEX: 0, bench: 1, ir: 0, K: 0, DST: 0 },
  teams: [
    { id: "1", name: "Alpha", manager: "A", wins: 1, losses: 0, ties: 0, points: 10, players: [{ providerPlayerId: "q", name: "Player QB", position: "QB", nflTeam: "CHI", gsisId: "QB", ir: false, taxi: false }] },
    { id: "2", name: "Beta", manager: "B", wins: 0, losses: 1, ties: 0, points: 9, players: [] },
  ],
  matchups: [
    { week: 1, matchupId: "a", teamId: "1", points: 10 }, { week: 1, matchupId: "a", teamId: "2", points: 9 },
    { week: 2, matchupId: "b", teamId: "1", points: 0 }, { week: 2, matchupId: "b", teamId: "2", points: 0 },
  ],
};

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("offline"); }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("league lab page", () => {
  it("restores a saved league, remembers the chosen team, and unlinks it", async () => {
    localStorage.setItem(LEAGUE_STORAGE_KEY, JSON.stringify(upsertLeague(EMPTY_LEAGUE_STORE, saved)));
    render(<LeagueLabClient />);
    expect(await screen.findByRole("heading", { name: "Saved Friends" })).toBeTruthy();
    expect(screen.getByText(/0\.5 points per reception/)).toBeTruthy();
    expect(screen.getByText(/playoff bracket/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Your team"), { target: { value: "1" } });
    await waitFor(() => expect(JSON.parse(localStorage.getItem(LEAGUE_STORAGE_KEY)!).leagues[0].selectedTeamId).toBe("1"));
    expect(localStorage.getItem(LEAGUE_STORAGE_KEY)).not.toMatch(/espn_s2|swid/i);
    fireEvent.click(screen.getByRole("button", { name: "Unlink league" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm unlink" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Find leagues" })).toBeTruthy());
    expect(JSON.parse(localStorage.getItem(LEAGUE_STORAGE_KEY)!).leagues).toEqual([]);
  });
});
