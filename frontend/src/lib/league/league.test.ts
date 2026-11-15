import { describe, expect, it } from "vitest";
import type { RosPlayer, RosPosition, RosSnapshot } from "@/lib/ros";
import { ESPN_JSON_LIMIT, normalizeEspn, parseEspnLeagueReference, parseEspnPaste } from "./espn";
import type { IdentityIndex } from "./identity";
import { projectLeague, replayThrough } from "./project";
import { EMPTY_LEAGUE_STORE, LEAGUE_STORAGE_KEY, loadLeagueStore, parseLeagueStore, saveLeagueStore, upsertLeague } from "./store";
import { normalizeSleeper } from "./sleeper";
import type { LeagueMatchup, SavedLeague } from "./types";

const identity: IdentityIndex = {
  bySleeperId: new Map([
    ["4046", { gsisId: "00-QB", name: "Pat", position: "QB", nflTeam: "KC" }],
    ["1", { gsisId: null, name: "Pat", position: "QB", nflTeam: "KC" }],
    ["KC", { gsisId: null, name: "Chiefs", position: "DEF", nflTeam: "KC" }],
  ]),
  byEspnId: new Map([["3139477", { gsisId: "00-QB", name: "Pat", position: "QB", nflTeam: "KC" }]]),
};

function player(playerId: string, position: RosPosition, mean: number, remainingTeamGames = 1): RosPlayer {
  return { playerId, name: playerId, position, team: "CHI", remainingTeamGames, mean, quantiles: [mean - 2, mean - 1, mean, mean + 1, mean + 2] };
}

function snapshot(entities: RosPlayer[], cutoffWeek = 1): RosSnapshot {
  return {
    schemaVersion: 1, kind: "ros", snapshotId: "snap", season: 2026, cutoffWeek, generatedAt: "2026-11-01T00:00:00Z",
    modelVersion: "test", scoringProfile: "ppr-v1", quantileLevels: [0.05, 0.25, 0.5, 0.75, 0.95], methodology: "test", entities,
  };
}

function league(matchups: LeagueMatchup[], extra?: Partial<SavedLeague>): SavedLeague {
  return {
    version: 1, id: "sleeper:10:2026", provider: "sleeper", providerLeagueId: "10", season: 2026, name: "Friends",
    importedAt: "2026-11-14T00:00:00Z", selectedTeamId: "1", selectionSource: "manual", asOfWeek: 10,
    receptionPoints: 1, playoffWeekStart: 3, notes: [], unsupportedSlots: [],
    rosterSettings: { QB: 1, RB: 0, WR: 0, TE: 0, FLEX: 0, SUPERFLEX: 0, bench: 0, ir: 1, K: 0, DST: 0 },
    teams: [
      { id: "1", name: "Alpha", manager: "A", wins: 9, losses: 0, ties: 0, points: 999, players: [{ providerPlayerId: "4046", name: "Pat", position: "QB", nflTeam: "KC", gsisId: "00-QB", ir: false, taxi: false }] },
      { id: "2", name: "Beta", manager: "B", wins: 0, losses: 9, ties: 0, points: 1, players: [{ providerPlayerId: "2", name: "Other", position: "QB", nflTeam: "CHI", gsisId: "00-OTHER", ir: false, taxi: false }] },
    ],
    matchups, ...extra,
  };
}

describe("league connections", () => {
  it("parses an ESPN link and rejects other hosts or conflicting ids", () => {
    expect(parseEspnLeagueReference("https://fantasy.espn.com/football/league?leagueId=123&seasonId=2026", 2026)).toEqual({ leagueId: "123" });
    expect(parseEspnLeagueReference(" 456 ", 2026)).toEqual({ leagueId: "456" });
    expect(() => parseEspnLeagueReference("https://fantasy.espn.com.evil.test/football/league?leagueId=1", 2026)).toThrow(/fantasy\.espn\.com/);
    expect(() => parseEspnLeagueReference("https://example.com/league?leagueId=1", 2026)).toThrow(/fantasy\.espn\.com/);
    expect(() => parseEspnLeagueReference("https://fantasy.espn.com/football/league?leagueId=1&leagueId=2", 2026)).toThrow(/one numeric/);
    expect(() => parseEspnLeagueReference("https://fantasy.espn.com/football/league?leagueId=1&seasonId=2025", 2026)).toThrow(/season/);
  });

  it("keeps a Sleeper roster, preselects the matching user, and does not match on name", () => {
    const saved = normalizeSleeper({
      league: { league_id: "99", name: "Home", season: "2026", roster_positions: ["QB", "SUPER_FLEX", "REC_FLEX", "BN", "K", "DEF", "DL"], scoring_settings: { rec: 0.5, bonus_rec_te: 0.5 }, settings: { playoff_week_start: 15, best_ball: 1 } },
      users: [{ user_id: "me", display_name: "Me", metadata: { team_name: "My Club" } }],
      rosters: [
        { roster_id: 1, owner_id: "me", players: ["4046", "1", "KC"], reserve: [], settings: { wins: 4, losses: 2, ties: 0, fpts: 10, fpts_decimal: 50 } },
        { roster_id: 2, owner_id: "them", co_owners: [], players: ["1"], settings: { wins: 1, losses: 5, ties: 0, fpts: 8, fpts_decimal: 0 } },
      ],
      weeks: [{ week: 1, rows: [{ roster_id: 1, matchup_id: 1, points: 100 }, { roster_id: 2, matchup_id: 1, points: 90 }, { roster_id: 1, matchup_id: null, points: 0 }] }],
      identity, linkedUserId: "me", asOfWeek: 10, importedAt: "2026-11-14T00:00:00Z",
    });
    expect(saved.selectedTeamId).toBe("1");
    expect(saved.selectionSource).toBe("sleeper-user");
    expect(saved.teams[0]).toMatchObject({ name: "My Club", points: 10.5 });
    expect(saved.teams[0]?.players.find((item) => item.providerPlayerId === "1")?.gsisId).toBeNull();
    expect(saved.rosterSettings).toMatchObject({ QB: 1, SUPERFLEX: 1, FLEX: 1, bench: 1, K: 1, DST: 1 });
    expect(saved.receptionPoints).toBe(0.5);
    expect(saved.unsupportedSlots).toEqual(["DL ×1"]);
    expect(saved.notes.join(" ")).toMatch(/Best-ball/);
    expect(JSON.stringify(saved)).not.toMatch(/espn_s2|swid/i);
  });

  it("imports ESPN teams without storing member ids", () => {
    const saved = normalizeEspn({
      id: 55, seasonId: 2026, scoringPeriodId: 8,
      settings: { name: "Office", rosterSettings: { lineupSlotCounts: { "0": 1, "23": 1, "17": 1, "8": 1 } }, scheduleSettings: { matchupPeriodCount: 14 }, scoringSettings: { scoringItems: [{ statId: 53, points: 1, isReverseItem: false }, { statId: 42, points: 0.1 }] } },
      members: [{ id: "{MEMBER-TOKEN-XYZ}", displayName: "Alex" }],
      teams: [
        { id: 1, name: "Alpha", primaryOwner: "{MEMBER-TOKEN-XYZ}", record: { overall: { wins: 3, losses: 1, ties: 0, pointsFor: 400.5 } }, roster: { entries: [{ playerId: 3139477, lineupSlotId: 0, playerPoolEntry: { player: { id: 3139477, fullName: "Pat", defaultPositionId: 1 } } }, { playerId: 9, lineupSlotId: 21, playerPoolEntry: { player: { id: 9, fullName: "Hurt", defaultPositionId: 2 } } }] } },
        { id: 2, name: "Beta", record: { overall: { wins: 1, losses: 3, ties: 0, pointsFor: 300 } }, roster: { entries: [{ playerId: "42", lineupSlotId: 2, playerPoolEntry: { player: { id: "42", fullName: "String Id", defaultPositionId: 2, proTeamId: 34 } } }] } },
      ],
      schedule: [{ matchupPeriodId: 1, home: { teamId: 1, totalPoints: 110 }, away: { teamId: 2, totalPoints: 90 } }],
    }, { leagueId: "55", season: 2026, identity, importedAt: "2026-11-14T00:00:00Z" });
    expect(saved.name).toBe("Office");
    expect(saved.teams[0]).toMatchObject({ manager: "Alex", points: 400.5 });
    expect(saved.teams[0]?.players[0]).toMatchObject({ gsisId: "00-QB", ir: false });
    expect(saved.teams[0]?.players[1]).toMatchObject({ name: "Hurt", ir: true, gsisId: null });
    expect(saved.teams[1]?.players[0]).toMatchObject({ providerPlayerId: "42", name: "String Id", position: "RB", nflTeam: "HOU", gsisId: null });
    expect(saved.playoffWeekStart).toBe(15);
    expect(saved.receptionPoints).toBe(1);
    expect(saved.rosterSettings).toMatchObject({ QB: 1, FLEX: 1, K: 1 });
    expect(saved.unsupportedSlots).toEqual(["ESPN slot 8 ×1"]);
    expect(saved.matchups).toEqual([
      { week: 1, matchupId: "p1-0", teamId: "1", points: 110 },
      { week: 1, matchupId: "p1-0", teamId: "2", points: 90 },
    ]);
    expect(JSON.stringify(saved)).not.toContain("MEMBER-TOKEN-XYZ");
  });

  it("accepts league JSON above the old paste cap and rejects anything past the shared cap", () => {
    const text = JSON.stringify({
      id: 55, seasonId: 2026, settings: { name: "Office" },
      teams: [
        { id: 1, name: "Alpha", roster: { entries: [] } },
        { id: 2, name: "Beta", roster: { entries: [] } },
      ],
      padding: "x".repeat(2_000_000),
    });
    expect(text.length).toBeGreaterThan(2_000_000);
    expect(text.length).toBeLessThanOrEqual(ESPN_JSON_LIMIT);
    expect(parseEspnPaste(`\n${text}\n`, { leagueId: "55", season: 2026, identity }).name).toBe("Office");
    expect(() => parseEspnPaste("x".repeat(ESPN_JSON_LIMIT + 1), { leagueId: "55", season: 2026, identity })).toThrow(/too large/);
  });

  it("saves a league locally and drops anything with a session secret", () => {
    localStorage.clear();
    const saved = league([]);
    expect(saveLeagueStore(upsertLeague(EMPTY_LEAGUE_STORE, saved))).toBe(true);
    expect(loadLeagueStore().activeId).toBe(saved.id);
    expect(localStorage.getItem(LEAGUE_STORAGE_KEY)).not.toMatch(/espn_s2|swid/i);
    expect(parseLeagueStore({ version: 1, activeId: null, leagues: [saved], espn_s2: "secret" })).toEqual(EMPTY_LEAGUE_STORE);
    expect(saveLeagueStore({ version: 1, activeId: null, leagues: [], espn_s2: "secret" } as unknown as typeof EMPTY_LEAGUE_STORE)).toBe(false);
  });
});

describe("league projection", () => {
  it("ignores an all-zero week and records a played game", () => {
    const replay = replayThrough([
      { week: 1, matchupId: "a", teamId: "1", points: 0 }, { week: 1, matchupId: "a", teamId: "2", points: 0 },
      { week: 2, matchupId: "b", teamId: "1", points: 20 }, { week: 2, matchupId: "b", teamId: "2", points: 10 },
      { week: 2, matchupId: null, teamId: "1", points: 0 },
    ], ["1", "2"], 2);
    expect(replay.skippedWeeks).toEqual([1]);
    expect(replay.through.get("1")).toMatchObject({ wins: 1, losses: 0, points: 20 });
    expect(replay.through.get("2")).toMatchObject({ wins: 0, losses: 1, points: 10 });
  });

  it("scales rest-of-season points to the fantasy games that remain", () => {
    const result = projectLeague(league([
      { week: 1, matchupId: "a", teamId: "1", points: 50 }, { week: 1, matchupId: "a", teamId: "2", points: 40 },
      { week: 2, matchupId: "b", teamId: "1", points: 0 }, { week: 2, matchupId: "b", teamId: "2", points: 0 },
    ]), snapshot([player("00-QB", "QB", 100, 10), player("00-OTHER", "QB", 50, 10)], 1), { sims: 20, seed: 1 });
    const alpha = result.teams.find((team) => team.teamId === "1")!;
    expect(result.mode).toBe("simulated");
    expect(alpha.through).toMatchObject({ wins: 1, points: 50 });
    expect(alpha.rosMean).toBeCloseTo(10);
    expect(alpha.projectedPoints).toBeCloseTo(60);
  });

  it("gives the stronger lineup the better record and points-title chances", () => {
    const result = projectLeague(league([
      { week: 1, matchupId: "a", teamId: "1", points: 10 }, { week: 1, matchupId: "a", teamId: "2", points: 9 },
      { week: 2, matchupId: "b", teamId: "1", points: 0 }, { week: 2, matchupId: "b", teamId: "2", points: 0 },
    ]), snapshot([player("00-QB", "QB", 400), player("00-OTHER", "QB", 40)]), { sims: 400, seed: 2 });
    const alpha = result.teams.find((team) => team.teamId === "1")!;
    const beta = result.teams.find((team) => team.teamId === "2")!;
    expect(alpha.pBestRecord!).toBeGreaterThan(0.9);
    expect(alpha.pMostPoints!).toBeGreaterThan(beta.pMostPoints!);
    expect(alpha.records.length).toBeGreaterThan(0);
    expect(result.caveats.join(" ")).toMatch(/full-PPR/);
    expect(result.caveats.join(" ")).toMatch(/playoff bracket/);
    expect(projectLeague(league([]), snapshot([player("00-QB", "QB", 10)])).mode).not.toBe("simulated");
  });

  it("leaves kickers, IR, and nameless matches out of the lineup", () => {
    const result = projectLeague(league([
      { week: 1, matchupId: "a", teamId: "1", points: 5 }, { week: 1, matchupId: "a", teamId: "2", points: 4 },
      { week: 2, matchupId: "b", teamId: "1", points: 0 }, { week: 2, matchupId: "b", teamId: "2", points: 0 },
    ], {
      playoffWeekStart: 3,
      rosterSettings: { QB: 0, RB: 1, WR: 0, TE: 0, FLEX: 1, SUPERFLEX: 0, bench: 2, ir: 1, K: 1, DST: 1 },
      teams: [
        { id: "1", name: "Alpha", manager: "A", wins: 1, losses: 0, ties: 0, points: 5, players: [
          { providerPlayerId: "q", name: "Starter", position: "QB", nflTeam: "KC", gsisId: "00-QB", ir: false, taxi: false },
          { providerPlayerId: "r", name: "Back", position: "RB", nflTeam: "KC", gsisId: "00-RB", ir: false, taxi: false },
          { providerPlayerId: "w", name: "Flex", position: "WR", nflTeam: "KC", gsisId: "00-WR", ir: false, taxi: false },
          { providerPlayerId: "i", name: "Hurt", position: "RB", nflTeam: "KC", gsisId: "00-IR", ir: true, taxi: false },
          { providerPlayerId: "k", name: "Boot", position: "K", nflTeam: "KC", gsisId: null, ir: false, taxi: false },
          { providerPlayerId: "n", name: "Unlisted Player", position: "TE", nflTeam: "KC", gsisId: null, ir: false, taxi: false },
        ] },
        { id: "2", name: "Beta", manager: "B", wins: 0, losses: 1, ties: 0, points: 4, players: [] },
      ],
    }), snapshot([player("00-QB", "QB", 10), player("00-RB", "RB", 100), player("00-WR", "WR", 90), player("00-IR", "RB", 500), player("00-NAME", "TE", 80)], 1), { sims: 5, seed: 1 });
    const alpha = result.teams[0]!;
    expect(result.mode).toBe("simulated");
    expect(alpha.rosMedianSum).toBe(190);
    expect(alpha.heldOut.map((item) => item.name)).toEqual(["Hurt"]);
    expect(alpha.unmapped.map((item) => item.name)).toEqual(["Boot", "Unlisted Player"]);
    expect(alpha.unmapped.map((item) => item.detail)).toEqual(["Kickers and defenses are not projected.", "No rest-of-season projection."]);
  });

  it("matches a roster name to the one projected player with that name and position", () => {
    const chase = player("00-CHASE", "WR", 80);
    chase.name = "Ja'Marr Chase";
    const sharedA = player("00-A", "QB", 10);
    sharedA.name = "Josh Johnson";
    sharedA.team = "BAL";
    const sharedB = player("00-B", "QB", 30);
    sharedB.name = "Josh Johnson";
    sharedB.team = "WAS";
    const result = projectLeague(league([
      { week: 1, matchupId: "a", teamId: "1", points: 5 }, { week: 1, matchupId: "a", teamId: "2", points: 4 },
    ], {
      playoffWeekStart: 3,
      rosterSettings: { QB: 1, RB: 0, WR: 1, TE: 0, FLEX: 0, SUPERFLEX: 0, bench: 0, ir: 0, K: 0, DST: 0 },
      teams: [
        { id: "1", name: "Alpha", manager: "A", wins: 0, losses: 0, ties: 0, points: 0, players: [
          { providerPlayerId: "c", name: "Ja Marr Chase Jr.", position: "WR", nflTeam: "", gsisId: null, ir: false, taxi: false },
          { providerPlayerId: "j", name: "Josh Johnson", position: "QB", nflTeam: "WAS", gsisId: null, ir: false, taxi: false },
          { providerPlayerId: "s", name: "Nobody Special", position: "QB", nflTeam: "", gsisId: "missing", ir: false, taxi: false },
        ] },
        { id: "2", name: "Beta", manager: "B", wins: 0, losses: 0, ties: 0, points: 0, players: [
          { providerPlayerId: "u", name: "Josh Johnson", position: "QB", nflTeam: "", gsisId: null, ir: false, taxi: false },
        ] },
      ],
    }), snapshot([chase, sharedA, sharedB], 1), { sims: 5, seed: 1 });
    const alpha = result.teams[0]!;
    const beta = result.teams[1]!;
    expect(alpha.lineup.map((spot) => spot.player?.playerId)).toEqual(["00-B", "00-CHASE"]);
    expect(alpha.unmapped.map((item) => item.detail)).toEqual(["No rest-of-season projection."]);
    expect(beta.unmapped.map((item) => item.detail)).toEqual(["Several projected players share this name and position."]);
    expect(alpha.rosSd).toBeGreaterThan(0);
  });

  it("does not estimate a league from another season", () => {
    const result = projectLeague(league([], { season: 2025, id: "sleeper:10:2025" }), snapshot([player("00-QB", "QB", 10)]));
    expect(result.mode).toBe("blocked");
    expect(result.reason).toMatch(/2026/);
  });
});
