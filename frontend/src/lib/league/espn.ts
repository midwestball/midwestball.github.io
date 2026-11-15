import type { IdentityIndex } from "./identity";
import {
  LeagueConnectError, asRecord, blankSettings, clipText, fantasyPosition, finiteNumber, leagueStorageId, wholeNumber,
  type LeagueMatchup, type LeaguePlayer, type LeagueTeam, type SavedLeague,
} from "./types";

const HOST = "https://lm-api-reads.fantasy.espn.com";
const VIEWS = ["mSettings", "mTeam", "mRoster", "mMatchup"];

/** ESPN slot ids used by the unofficial league payload. Unlisted ids stay unsupported. */
const ESPN_SLOT: Record<number, keyof ReturnType<typeof blankSettings> | "flex-note" | "superflex"> = {
  0: "QB", 2: "RB", 4: "WR", 6: "TE", 23: "FLEX",
  3: "flex-note", 5: "flex-note", 7: "superflex",
  16: "DST", 17: "K", 20: "bench", 21: "ir",
};

const ESPN_POSITION: Record<number, string> = { 1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DST" };

export function espnLeagueUrl(leagueId: string, season: number): string {
  return `${HOST}/apis/v3/games/ffl/seasons/${season}/segments/0/leagues/${leagueId}?${VIEWS.map((view) => `view=${view}`).join("&")}`;
}

export function parseEspnLeagueReference(input: string, season: number): { leagueId: string } {
  const trimmed = input.trim();
  if (/^\d{1,12}$/.test(trimmed)) return { leagueId: trimmed };
  let url: URL;
  try {
    url = new URL(trimmed);
  } catch {
    throw new LeagueConnectError("INVALID", "Enter an ESPN league URL or a numeric league ID.");
  }
  if (url.protocol !== "https:" || url.hostname !== "fantasy.espn.com") {
    throw new LeagueConnectError("INVALID", "Only https://fantasy.espn.com league links are accepted.");
  }
  const ids = url.searchParams.getAll("leagueId").filter(Boolean);
  if (ids.length !== 1 || !/^\d{1,12}$/.test(ids[0]!)) throw new LeagueConnectError("INVALID", "That link needs one numeric leagueId.");
  const seasons = [...url.searchParams.getAll("seasonId"), ...url.searchParams.getAll("season")].filter(Boolean);
  if (seasons.some((value) => Number(value) !== season)) throw new LeagueConnectError("INVALID", "The link's season doesn't match the season you entered.");
  return { leagueId: ids[0]! };
}

function receptionPoints(settings: Record<string, unknown> | null): number | null {
  const scoring = asRecord(settings?.scoringSettings);
  const items = Array.isArray(scoring?.scoringItems) ? scoring.scoringItems : [];
  const points = new Map<number, number>();
  for (const entry of items) {
    const item = asRecord(entry);
    const statId = item ? wholeNumber(item.statId) : null;
    const value = item ? finiteNumber(item.points) : null;
    if (!item || item.isReverseItem === true || statId === null || value === null || (statId !== 53 && statId !== 41)) continue;
    points.set(statId, value);
  }
  const modern = points.get(53), legacy = points.get(41);
  if (modern === undefined && legacy === undefined) return null;
  if (modern !== undefined && legacy !== undefined && modern !== legacy) return null;
  return modern ?? legacy ?? null;
}

export function normalizeEspn(raw: unknown, request: { leagueId: string; season: number; identity: IdentityIndex; importedAt?: string }): SavedLeague {
  const league = asRecord(raw);
  if (!league) throw new LeagueConnectError("INVALID", "ESPN did not return league JSON.");
  if (String(league.id ?? "") !== request.leagueId) throw new LeagueConnectError("INVALID", "That response is for a different league id.");
  const payloadSeason = wholeNumber(league.seasonId);
  if (payloadSeason !== null && payloadSeason !== request.season) throw new LeagueConnectError("INVALID", "That response is for a different season.");
  const settings = asRecord(league.settings);
  const rosterSettings = blankSettings();
  const notes: string[] = [];
  const unsupported: string[] = [];
  const counts = asRecord(asRecord(settings?.rosterSettings)?.lineupSlotCounts);
  let flexNote = false;
  for (const [slot, count] of Object.entries(counts ?? {})) {
    const slotId = Number(slot);
    const n = wholeNumber(count);
    if (!n) continue;
    const mapped = ESPN_SLOT[slotId];
    if (mapped === "flex-note") { rosterSettings.FLEX += n; flexNote = true; }
    else if (mapped === "superflex") rosterSettings.SUPERFLEX += n;
    else if (mapped) rosterSettings[mapped] += n;
    else unsupported.push(`ESPN slot ${slotId} ×${n}`);
  }
  if (flexNote) notes.push("A WR/TE or RB/WR slot is treated as FLEX, so the extra position can fill it.");
  const scheduleSettings = asRecord(settings?.scheduleSettings);
  const periods = wholeNumber(scheduleSettings?.matchupPeriodCount);
  const managers = new Map<string, string>();
  for (const entry of Array.isArray(league.members) ? league.members : []) {
    const member = asRecord(entry);
    const name = member ? clipText(member.displayName, 80, "") : "";
    if (member && typeof member.id === "string" && name) managers.set(member.id, name);
  }
  const teamsRaw = Array.isArray(league.teams) ? league.teams : [];
  if (teamsRaw.length < 2) throw new LeagueConnectError("INVALID", "ESPN did not return this league's teams.");
  const teams: LeagueTeam[] = teamsRaw.map((entry) => {
    const team = asRecord(entry);
    const id = team ? wholeNumber(team.id) : null;
    if (!team || id === null) throw new LeagueConnectError("INVALID", "An ESPN team was missing its id.");
    const record = asRecord(asRecord(team.record)?.overall);
    const rosterRecord = asRecord(team.roster);
    const roster = Array.isArray(rosterRecord?.entries) ? rosterRecord.entries as unknown[] : [];
    const ownerId = typeof team.primaryOwner === "string" ? team.primaryOwner : "";
    return {
      id: String(id),
      name: clipText(team.name, 80, `Team ${id}`),
      manager: managers.get(ownerId) || "Manager",
      wins: wholeNumber(record?.wins) ?? 0,
      losses: wholeNumber(record?.losses) ?? 0,
      ties: wholeNumber(record?.ties) ?? 0,
      points: finiteNumber(record?.pointsFor) ?? finiteNumber(team.points) ?? 0,
      players: roster.flatMap((item) => espnPlayer(item, request.identity)),
    };
  });
  const known = new Set(teams.map((team) => team.id));
  const matchups: LeagueMatchup[] = [];
  const schedule = Array.isArray(league.schedule) ? league.schedule : [];
  schedule.forEach((entry, index) => {
    const game = asRecord(entry);
    const week = game ? wholeNumber(game.matchupPeriodId) : null;
    if (!game || week === null) return;
    const sides = [asRecord(game.home), asRecord(game.away)].filter((side): side is Record<string, unknown> => side !== null && wholeNumber(side.teamId) !== null);
    const matchupId = sides.length === 2 ? `p${week}-${index}` : null;
    for (const side of sides) {
      const teamId = String(wholeNumber(side.teamId));
      if (!known.has(teamId)) continue;
      matchups.push({ week, matchupId, teamId, points: finiteNumber(side.totalPoints) ?? 0 });
    }
  });
  const status = asRecord(league.status);
  return {
    version: 1,
    id: leagueStorageId("espn", request.leagueId, request.season),
    provider: "espn",
    providerLeagueId: request.leagueId,
    season: request.season,
    name: clipText(settings?.name, 80, "ESPN league"),
    importedAt: request.importedAt ?? new Date().toISOString(),
    selectedTeamId: null,
    selectionSource: null,
    asOfWeek: wholeNumber(status?.latestScoringPeriod) ?? wholeNumber(league.scoringPeriodId),
    receptionPoints: receptionPoints(settings),
    playoffWeekStart: periods !== null && periods >= 1 && periods <= 21 ? periods + 1 : null,
    notes,
    unsupportedSlots: unsupported,
    rosterSettings,
    teams,
    matchups,
  };
}

function espnPlayer(entry: unknown, identity: IdentityIndex): LeaguePlayer[] {
  const row = asRecord(entry);
  if (!row) return [];
  const pool = asRecord(asRecord(row.playerPoolEntry)?.player);
  const id = wholeNumber(row.playerId) ?? wholeNumber(pool?.id);
  if (id === null) return [];
  const hit = identity.byEspnId.get(String(id));
  const positionId = wholeNumber(pool?.defaultPositionId);
  return [{
    providerPlayerId: String(id),
    name: clipText(pool?.fullName, 80, hit?.name || `Player ${id}`),
    position: fantasyPosition(ESPN_POSITION[positionId ?? -1] || hit?.position || ""),
    nflTeam: hit?.nflTeam || "",
    gsisId: hit?.gsisId ?? null,
    ir: wholeNumber(row.lineupSlotId) === 21,
    taxi: false,
  }];
}

async function readEspn(url: string, credentials: RequestCredentials, signal?: AbortSignal): Promise<{ status: number; body: unknown; html: boolean }> {
  let response: Response;
  try {
    response = await fetch(url, { signal, credentials, headers: { accept: "application/json" } });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new LeagueConnectError("NETWORK", "Could not reach ESPN from this page. You can paste the league JSON instead.");
  }
  const text = await response.text();
  const html = text.trimStart().startsWith("<") || (response.headers.get("content-type") ?? "").includes("html");
  if (html) return { status: response.status, body: null, html: true };
  try {
    return { status: response.status, body: text ? JSON.parse(text) : null, html: false };
  } catch {
    throw new LeagueConnectError("INVALID", "ESPN returned a response that was not league JSON.");
  }
}

function authDenied(status: number, body: unknown): boolean {
  if (status === 401 || status === 403) return true;
  const record = asRecord(body);
  const details = Array.isArray(record?.details) ? record.details : [];
  return details.some((detail) => asRecord(detail)?.type === "AUTH_LEAGUE_NOT_VISIBLE");
}

/**
 * Public read first. If ESPN refuses, retry with the browser's existing ESPN session.
 * Pasted SWID and espn_s2 values are never accepted: this page cannot attach them,
 * and they are account session credentials rather than a league-only key.
 */
export async function fetchEspnLeague(leagueId: string, season: number, signal?: AbortSignal): Promise<unknown> {
  const url = espnLeagueUrl(leagueId, season);
  const pub = await readEspn(url, "omit", signal);
  if (pub.html) throw new LeagueConnectError("AUTH_REQUIRED", "ESPN returned a login page instead of league data.");
  if (pub.status === 404) throw new LeagueConnectError("NOT_FOUND", "ESPN didn't find that league for that season.");
  if (authDenied(pub.status, pub.body)) {
    const session = await readEspn(url, "include", signal);
    if (!session.html && session.status >= 200 && session.status < 300 && asRecord(session.body)?.teams) return session.body;
    if (session.status === 404) throw new LeagueConnectError("NOT_FOUND", "ESPN didn't find that league for that season.");
    throw new LeagueConnectError("AUTH_REQUIRED", "This ESPN league isn't publicly readable, and the browser session couldn't open it.");
  }
  if (pub.status >= 500) throw new LeagueConnectError("UNAVAILABLE", "ESPN didn't answer. Try again later.");
  if (pub.status < 200 || pub.status >= 300 || !asRecord(pub.body)) throw new LeagueConnectError("INVALID", "ESPN returned an unexpected league response.");
  return pub.body;
}

export function parseEspnPaste(text: string, request: { leagueId: string; season: number; identity: IdentityIndex }): SavedLeague {
  const trimmed = text.trim();
  if (!trimmed) throw new LeagueConnectError("INVALID", "Paste the league JSON first.");
  if (trimmed.length > 2_000_000) throw new LeagueConnectError("INVALID", "That paste is too large.");
  if (trimmed.startsWith("<")) throw new LeagueConnectError("AUTH_REQUIRED", "That paste is a login page, not league JSON.");
  let body: unknown;
  try {
    body = JSON.parse(trimmed);
  } catch {
    throw new LeagueConnectError("INVALID", "That paste isn't league JSON.");
  }
  return normalizeEspn(body, request);
}
