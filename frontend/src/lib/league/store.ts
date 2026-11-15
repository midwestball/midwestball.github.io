import { validSettings, type RosterSettings } from "@/lib/trades";
import { hasSecretKey, asRecord, finiteNumber, wholeNumber, type LeagueMatchup, type LeaguePlayer, type LeagueTeam, type SavedLeague } from "./types";

export const LEAGUE_STORAGE_KEY = "midwestball-league-lab-v1";
export type LeagueStore = { version: 1; activeId: string | null; leagues: SavedLeague[] };
export const EMPTY_LEAGUE_STORE: LeagueStore = { version: 1, activeId: null, leagues: [] };

const SLOT_KEYS = ["QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX", "bench", "ir", "K", "DST"] as const;

function settings(value: unknown): RosterSettings | null {
  const record = asRecord(value);
  if (!record) return null;
  const next = {} as RosterSettings;
  for (const key of SLOT_KEYS) {
    const count = wholeNumber(record[key]);
    if (count === null || count < 0 || count > 20) return null;
    next[key] = count;
  }
  return next;
}

function player(value: unknown): LeaguePlayer | null {
  const record = asRecord(value);
  if (!record || typeof record.providerPlayerId !== "string" || typeof record.name !== "string" || typeof record.position !== "string") return null;
  if (typeof record.ir !== "boolean" || typeof record.taxi !== "boolean") return null;
  if (!(record.gsisId === null || typeof record.gsisId === "string")) return null;
  return {
    providerPlayerId: record.providerPlayerId.slice(0, 40),
    name: record.name.slice(0, 80),
    position: record.position.slice(0, 12),
    nflTeam: typeof record.nflTeam === "string" ? record.nflTeam.slice(0, 8) : "",
    gsisId: typeof record.gsisId === "string" ? record.gsisId.slice(0, 40) : null,
    ir: record.ir,
    taxi: record.taxi,
  };
}

function team(value: unknown): LeagueTeam | null {
  const record = asRecord(value);
  if (!record || typeof record.id !== "string" || typeof record.name !== "string" || typeof record.manager !== "string") return null;
  const wins = wholeNumber(record.wins), losses = wholeNumber(record.losses), ties = wholeNumber(record.ties), points = finiteNumber(record.points);
  if (wins === null || losses === null || ties === null || points === null || !Array.isArray(record.players) || record.players.length > 40) return null;
  const players: LeaguePlayer[] = [];
  for (const entry of record.players) {
    const parsed = player(entry);
    if (!parsed) return null;
    players.push(parsed);
  }
  return { id: record.id.slice(0, 40), name: record.name.slice(0, 80), manager: record.manager.slice(0, 80), wins, losses, ties, points, players };
}

function matchup(value: unknown): LeagueMatchup | null {
  const record = asRecord(value);
  if (!record || typeof record.teamId !== "string") return null;
  const week = wholeNumber(record.week), points = finiteNumber(record.points);
  if (week === null || week < 1 || week > 22 || points === null) return null;
  if (!(record.matchupId === null || typeof record.matchupId === "string")) return null;
  return { week, points, teamId: record.teamId.slice(0, 40), matchupId: typeof record.matchupId === "string" ? record.matchupId.slice(0, 40) : null };
}

function textList(value: unknown): string[] | null {
  if (!Array.isArray(value) || value.length > 20 || value.some((item) => typeof item !== "string" || item.length > 200)) return null;
  return value;
}

export function parseSavedLeague(value: unknown): SavedLeague | null {
  const record = asRecord(value);
  if (!record || record.version !== 1 || (record.provider !== "sleeper" && record.provider !== "espn")) return null;
  if (typeof record.providerLeagueId !== "string" || !/^\d{1,25}$/.test(record.providerLeagueId)) return null;
  const season = wholeNumber(record.season);
  if (season === null || season < 2017 || season > 2035 || typeof record.name !== "string" || typeof record.importedAt !== "string") return null;
  const id = `${record.provider}:${record.providerLeagueId}:${season}`;
  if (record.id !== id) return null;
  const rosterSettings = settings(record.rosterSettings);
  const notes = textList(record.notes), unsupportedSlots = textList(record.unsupportedSlots);
  if (!rosterSettings || !notes || !unsupportedSlots || !Array.isArray(record.teams) || record.teams.length < 1 || record.teams.length > 32) return null;
  if (!Array.isArray(record.matchups) || record.matchups.length > 800) return null;
  const asOfWeek = record.asOfWeek === null ? null : wholeNumber(record.asOfWeek);
  const playoffWeekStart = record.playoffWeekStart === null ? null : wholeNumber(record.playoffWeekStart);
  const receptionPoints = record.receptionPoints === null ? null : finiteNumber(record.receptionPoints);
  if (asOfWeek === null && record.asOfWeek !== null) return null;
  if (playoffWeekStart === null && record.playoffWeekStart !== null) return null;
  if (receptionPoints === null && record.receptionPoints !== null) return null;
  const selectionSource = record.selectionSource;
  if (selectionSource !== null && selectionSource !== "sleeper-user" && selectionSource !== "manual") return null;
  if (!(record.selectedTeamId === null || typeof record.selectedTeamId === "string")) return null;
  const teams: LeagueTeam[] = [];
  for (const entry of record.teams) {
    const parsed = team(entry);
    if (!parsed) return null;
    teams.push(parsed);
  }
  if (new Set(teams.map((item) => item.id)).size !== teams.length) return null;
  const known = new Set(teams.map((item) => item.id));
  const matchups: LeagueMatchup[] = [];
  for (const entry of record.matchups) {
    const parsed = matchup(entry);
    if (!parsed || !known.has(parsed.teamId)) return null;
    matchups.push(parsed);
  }
  const selectedTeamId = typeof record.selectedTeamId === "string" && known.has(record.selectedTeamId) ? record.selectedTeamId : null;
  return {
    version: 1, id, provider: record.provider, providerLeagueId: record.providerLeagueId, season, name: record.name.slice(0, 80),
    importedAt: record.importedAt, selectedTeamId, selectionSource: selectedTeamId ? selectionSource : null, asOfWeek, receptionPoints,
    playoffWeekStart, notes, unsupportedSlots, rosterSettings, teams, matchups,
  };
}

export function parseLeagueStore(value: unknown): LeagueStore {
  if (hasSecretKey(value)) return EMPTY_LEAGUE_STORE;
  const record = asRecord(value);
  if (!record || record.version !== 1 || !Array.isArray(record.leagues)) return EMPTY_LEAGUE_STORE;
  const leagues = record.leagues.map(parseSavedLeague).filter((league): league is SavedLeague => league !== null);
  const activeId = typeof record.activeId === "string" && leagues.some((league) => league.id === record.activeId) ? record.activeId : leagues[0]?.id ?? null;
  return { version: 1, activeId, leagues };
}

export function loadLeagueStore(): LeagueStore {
  try {
    const raw = localStorage.getItem(LEAGUE_STORAGE_KEY);
    return raw ? parseLeagueStore(JSON.parse(raw)) : EMPTY_LEAGUE_STORE;
  } catch {
    return EMPTY_LEAGUE_STORE;
  }
}

export function saveLeagueStore(store: LeagueStore): boolean {
  if (hasSecretKey(store)) return false;
  try {
    localStorage.setItem(LEAGUE_STORAGE_KEY, JSON.stringify(store));
    return true;
  } catch {
    return false;
  }
}

export function upsertLeague(store: LeagueStore, league: SavedLeague): LeagueStore {
  return { version: 1, activeId: league.id, leagues: [...store.leagues.filter((item) => item.id !== league.id), league] };
}

export function removeLeague(store: LeagueStore, id: string): LeagueStore {
  const leagues = store.leagues.filter((league) => league.id !== id);
  const activeId = store.activeId === id ? leagues[0]?.id ?? null : store.activeId;
  return { version: 1, activeId, leagues };
}

export function leagueSettingsLabel(settingsValue: RosterSettings): string {
  const slots = (["QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX"] as const).filter((slot) => settingsValue[slot] > 0).map((slot) => `${settingsValue[slot]} ${slot}`);
  return `${slots.join(", ") || "No skill slots"}${validSettings(settingsValue) ? "" : " (lineup shape isn't supported)"}`;
}
