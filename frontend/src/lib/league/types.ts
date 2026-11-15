import type { RosterSettings } from "@/lib/trades";

export type LeagueProvider = "sleeper" | "espn";
export type SelectionSource = "sleeper-user" | "manual";

export type LeaguePlayer = {
  providerPlayerId: string;
  name: string;
  position: string;
  nflTeam: string;
  gsisId: string | null;
  ir: boolean;
  taxi: boolean;
};

export type LeagueTeam = {
  id: string;
  name: string;
  manager: string;
  wins: number;
  losses: number;
  ties: number;
  /** Provider season points. Display only; the projection baseline comes from matchups. */
  points: number;
  players: LeaguePlayer[];
};

export type LeagueMatchup = {
  week: number;
  /** Null is a bye. Paired teams share a week and id. */
  matchupId: string | null;
  teamId: string;
  points: number;
};

/** League snapshot saved in this browser. Session cookies are not part of this object. */
export type SavedLeague = {
  version: 1;
  id: string;
  provider: LeagueProvider;
  providerLeagueId: string;
  season: number;
  name: string;
  importedAt: string;
  selectedTeamId: string | null;
  selectionSource: SelectionSource | null;
  asOfWeek: number | null;
  /** Points per reception when the provider states them. Null when they were not identified. */
  receptionPoints: number | null;
  /** First playoff week. Weeks at or after this are not regular-season games. */
  playoffWeekStart: number | null;
  notes: string[];
  unsupportedSlots: string[];
  rosterSettings: RosterSettings;
  teams: LeagueTeam[];
  matchups: LeagueMatchup[];
};

export class LeagueConnectError extends Error {
  constructor(
    public code: "NOT_FOUND" | "AUTH_REQUIRED" | "UNAVAILABLE" | "INVALID" | "NETWORK",
    message: string,
  ) {
    super(message);
    this.name = "LeagueConnectError";
  }
}

export const SECRET_KEY = /^(swid|espn_s2|cookie|cookies|password|token|authorization)$/i;

export function hasSecretKey(value: unknown): boolean {
  if (!value || typeof value !== "object") return false;
  for (const [key, child] of Object.entries(value)) {
    if (SECRET_KEY.test(key) || hasSecretKey(child)) return true;
  }
  return false;
}

export function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

export function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function wholeNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) ? value : null;
}

export function clipText(value: unknown, max: number, fallback: string): string {
  const text = typeof value === "string" ? value.trim() : "";
  return (text || fallback).slice(0, max);
}

export function blankSettings(): RosterSettings {
  return { QB: 0, RB: 0, WR: 0, TE: 0, FLEX: 0, SUPERFLEX: 0, bench: 0, ir: 0, K: 0, DST: 0 };
}

export function leagueStorageId(provider: LeagueProvider, providerLeagueId: string, season: number): string {
  return `${provider}:${providerLeagueId}:${season}`;
}

const POSITION = /^(QB|RB|WR|TE|K|DST)$/;

export function fantasyPosition(raw: string): string {
  const position = raw.trim().toUpperCase();
  if (position === "DEF" || position === "D/ST" || position === "D") return "DST";
  return POSITION.test(position) ? position : position.slice(0, 12);
}
