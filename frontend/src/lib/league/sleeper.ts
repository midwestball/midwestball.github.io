import type { IdentityIndex } from "./identity";
import {
  LeagueConnectError, asRecord, blankSettings, clipText, fantasyPosition, finiteNumber, leagueStorageId, wholeNumber,
  type LeagueMatchup, type LeaguePlayer, type LeagueTeam, type SavedLeague,
} from "./types";

const ROOT = "https://api.sleeper.app/v1";

export type SleeperLeagueSummary = { id: string; name: string; season: number; teams: number; status: string };

async function sleeperGet(path: string, signal?: AbortSignal): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(`${ROOT}${path}`, { signal, headers: { accept: "application/json" } });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new LeagueConnectError("NETWORK", "Could not reach Sleeper. Try again.");
  }
  if (response.status === 404) return null;
  if (!response.ok) throw new LeagueConnectError("UNAVAILABLE", `Sleeper request failed (${response.status}).`);
  try {
    return await response.json();
  } catch {
    throw new LeagueConnectError("INVALID", "Sleeper returned a response that was not JSON.");
  }
}

export function validSeason(season: number): boolean {
  return Number.isInteger(season) && season >= 2017 && season <= 2035;
}

export async function discoverSleeperLeagues(username: string, season: number, signal?: AbortSignal): Promise<{ userId: string; displayName: string; leagues: SleeperLeagueSummary[] }> {
  const trimmed = username.trim();
  if (!trimmed || trimmed.length > 50 || /[/?#\\\s]/.test(trimmed)) throw new LeagueConnectError("INVALID", "Enter a Sleeper username.");
  if (!validSeason(season)) throw new LeagueConnectError("INVALID", "Enter a season between 2017 and 2035.");
  const user = asRecord(await sleeperGet(`/user/${encodeURIComponent(trimmed)}`, signal));
  if (!user || typeof user.user_id !== "string") throw new LeagueConnectError("NOT_FOUND", "We couldn't find that Sleeper username.");
  const leagues = await sleeperGet(`/user/${encodeURIComponent(user.user_id)}/leagues/nfl/${season}`, signal);
  if (!Array.isArray(leagues)) throw new LeagueConnectError("INVALID", "Sleeper didn't return a league list.");
  return {
    userId: user.user_id,
    displayName: clipText(user.display_name, 80, trimmed),
    leagues: leagues.flatMap((entry) => {
      const league = asRecord(entry);
      const id = league && typeof league.league_id === "string" ? league.league_id : "";
      if (!league || !/^\d{1,25}$/.test(id)) return [];
      const teams = wholeNumber(league.total_rosters) ?? 0;
      return [{ id, name: clipText(league.name, 80, "Sleeper league"), season, teams, status: clipText(league.status, 40, "") }];
    }),
  };
}

const SLOT_MAP: Record<string, keyof ReturnType<typeof blankSettings> | "note-rec" | "note-wrrb"> = {
  QB: "QB", RB: "RB", WR: "WR", TE: "TE", FLEX: "FLEX",
  REC_FLEX: "note-rec", WRRB_FLEX: "note-wrrb",
  SUPER_FLEX: "SUPERFLEX", SUPERFLEX: "SUPERFLEX",
  BN: "bench", IR: "ir", K: "K", DEF: "DST", DST: "DST",
};

export function normalizeSleeper(input: {
  league: unknown;
  users: unknown;
  rosters: unknown;
  weeks: { week: number; rows: unknown }[];
  identity: IdentityIndex;
  linkedUserId: string | null;
  asOfWeek: number | null;
  importedAt?: string;
}): SavedLeague {
  const league = asRecord(input.league);
  const leagueId = league && typeof league.league_id === "string" ? league.league_id : "";
  const season = Number(league?.season);
  if (!league || !/^\d{1,25}$/.test(leagueId) || !validSeason(season)) throw new LeagueConnectError("INVALID", "Sleeper league details were incomplete.");
  const settings = blankSettings();
  const notes: string[] = [];
  const unsupported: string[] = [];
  const positions = Array.isArray(league.roster_positions) ? league.roster_positions : [];
  const unsupportedCounts = new Map<string, number>();
  for (const slot of positions) {
    if (typeof slot !== "string") continue;
    const mapped = SLOT_MAP[slot];
    if (mapped === "note-rec") { settings.FLEX += 1; notes.push("REC_FLEX slots are treated as FLEX, so a running back can fill them."); }
    else if (mapped === "note-wrrb") { settings.FLEX += 1; notes.push("WRRB_FLEX slots are treated as FLEX, so a tight end can fill them."); }
    else if (mapped) settings[mapped] += 1;
    else unsupportedCounts.set(slot, (unsupportedCounts.get(slot) ?? 0) + 1);
  }
  for (const [slot, count] of unsupportedCounts) unsupported.push(`${slot} ×${count}`);
  const scoring = asRecord(league.scoring_settings);
  const reception = scoring ? finiteNumber(scoring.rec) : null;
  const teBonus = scoring ? finiteNumber(scoring.bonus_rec_te) : null;
  if (teBonus) notes.push("A tight-end reception bonus is not applied to the projections.");
  const leagueSettings = asRecord(league.settings);
  if (leagueSettings?.best_ball === 1) notes.push("Best-ball scoring still uses one fixed lineup here, not the best score of each week.");
  const playoff = wholeNumber(leagueSettings?.playoff_week_start);
  const users = new Map<string, Record<string, unknown>>();
  if (!Array.isArray(input.users)) throw new LeagueConnectError("INVALID", "Sleeper didn't return league managers.");
  for (const entry of input.users) {
    const user = asRecord(entry);
    if (user && typeof user.user_id === "string") users.set(user.user_id, user);
  }
  if (!Array.isArray(input.rosters) || input.rosters.length < 1) throw new LeagueConnectError("INVALID", "Sleeper didn't return rosters.");
  const teams: LeagueTeam[] = [];
  let selectedTeamId: string | null = null;
  let ownerMatches = 0;
  for (const entry of input.rosters) {
    const roster = asRecord(entry);
    const rosterId = roster ? wholeNumber(roster.roster_id) : null;
    if (!roster || rosterId === null) throw new LeagueConnectError("INVALID", "A Sleeper roster was missing its id.");
    const ownerId = typeof roster.owner_id === "string" ? roster.owner_id : "";
    const coOwners = Array.isArray(roster.co_owners) ? roster.co_owners.filter((id): id is string => typeof id === "string") : [];
    if (input.linkedUserId && (ownerId === input.linkedUserId || coOwners.includes(input.linkedUserId))) {
      ownerMatches += 1;
      selectedTeamId = String(rosterId);
    }
    const user = users.get(ownerId);
    const metadata = asRecord(user?.metadata);
    const rosterSettings = asRecord(roster.settings);
    const fpts = finiteNumber(rosterSettings?.fpts) ?? 0;
    const decimal = finiteNumber(rosterSettings?.fpts_decimal) ?? 0;
    const reserve = new Set(Array.isArray(roster.reserve) ? roster.reserve.map(String) : []);
    const taxi = new Set(Array.isArray(roster.taxi) ? roster.taxi.map(String) : []);
    const playerIds = Array.isArray(roster.players) ? roster.players.map(String) : [];
    teams.push({
      id: String(rosterId),
      name: clipText(metadata?.team_name, 80, clipText(user?.display_name, 80, `Team ${rosterId}`)),
      manager: clipText(user?.display_name, 80, "Manager"),
      wins: wholeNumber(rosterSettings?.wins) ?? 0,
      losses: wholeNumber(rosterSettings?.losses) ?? 0,
      ties: wholeNumber(rosterSettings?.ties) ?? 0,
      points: fpts + decimal / 100,
      players: playerIds.map((providerPlayerId) => playerFromIdentity(providerPlayerId, input.identity, reserve.has(providerPlayerId), taxi.has(providerPlayerId))),
    });
  }
  if (ownerMatches !== 1) selectedTeamId = null;
  const known = new Set(teams.map((team) => team.id));
  const matchups: LeagueMatchup[] = [];
  for (const week of input.weeks) {
    if (!Array.isArray(week.rows)) continue;
    for (const entry of week.rows) {
      const row = asRecord(entry);
      const rosterId = row ? wholeNumber(row.roster_id) : null;
      const points = row ? finiteNumber(row.points) : null;
      if (rosterId === null || points === null || !known.has(String(rosterId))) continue;
      const matchupId = row && (typeof row.matchup_id === "number" || typeof row.matchup_id === "string") ? String(row.matchup_id) : null;
      matchups.push({ week: week.week, matchupId, teamId: String(rosterId), points });
    }
  }
  return {
    version: 1,
    id: leagueStorageId("sleeper", leagueId, season),
    provider: "sleeper",
    providerLeagueId: leagueId,
    season,
    name: clipText(league.name, 80, "Sleeper league"),
    importedAt: input.importedAt ?? new Date().toISOString(),
    selectedTeamId,
    selectionSource: selectedTeamId ? "sleeper-user" : null,
    asOfWeek: input.asOfWeek,
    receptionPoints: reception,
    playoffWeekStart: playoff !== null && playoff >= 2 && playoff <= 22 ? playoff : null,
    notes: [...new Set(notes)],
    unsupportedSlots: unsupported,
    rosterSettings: settings,
    teams,
    matchups,
  };
}

function playerFromIdentity(providerPlayerId: string, identity: IdentityIndex, ir: boolean, taxi: boolean): LeaguePlayer {
  const hit = identity.bySleeperId.get(providerPlayerId);
  return {
    providerPlayerId,
    name: hit?.name || `Player ${providerPlayerId}`,
    position: fantasyPosition(hit?.position || (providerPlayerId.length <= 3 ? "DST" : "")),
    nflTeam: hit?.nflTeam || "",
    gsisId: hit?.gsisId ?? null,
    ir,
    taxi,
  };
}

export async function importSleeperLeague(leagueId: string, linkedUserId: string | null, identity: IdentityIndex, signal?: AbortSignal): Promise<SavedLeague> {
  if (!/^\d{1,25}$/.test(leagueId)) throw new LeagueConnectError("INVALID", "That Sleeper league id is not numeric.");
  const [league, users, rosters, state] = await Promise.all([
    sleeperGet(`/league/${leagueId}`, signal),
    sleeperGet(`/league/${leagueId}/users`, signal),
    sleeperGet(`/league/${leagueId}/rosters`, signal),
    sleeperGet("/state/nfl", signal),
  ]);
  if (!asRecord(league)) throw new LeagueConnectError("NOT_FOUND", "Sleeper didn't return that league.");
  const stateRecord = asRecord(state);
  const asOfWeek = wholeNumber(stateRecord?.week);
  const weeks = await Promise.all(Array.from({ length: 18 }, (_, index) => index + 1).map(async (week) => {
    try {
      const rows = await sleeperGet(`/league/${leagueId}/matchups/${week}`, signal);
      return { week, rows };
    } catch (error) {
      if (error instanceof LeagueConnectError && error.code === "NETWORK") throw error;
      return { week, rows: null };
    }
  }));
  if (weeks.filter((week) => week.rows === null).length > 9) throw new LeagueConnectError("UNAVAILABLE", "Sleeper matchups didn't load. Try again.");
  return normalizeSleeper({ league, users, rosters, weeks: weeks.flatMap((week) => week.rows === null ? [] : [{ week: week.week, rows: week.rows }]), identity, linkedUserId, asOfWeek });
}
