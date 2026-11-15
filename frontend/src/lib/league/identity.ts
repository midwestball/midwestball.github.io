import { LeagueConnectError, asRecord, clipText } from "./types";

export type IdentityHit = { gsisId: string | null; name: string; position: string; nflTeam: string };
export type IdentityIndex = { bySleeperId: Map<string, IdentityHit>; byEspnId: Map<string, IdentityHit> };

const PLAYERS_URL = "https://api.sleeper.app/v1/players/nfl";
let directoryPromise: Promise<IdentityIndex> | null = null;

export function indexSleeperPlayers(raw: unknown): IdentityIndex {
  const source = asRecord(raw);
  if (!source) throw new LeagueConnectError("INVALID", "The player directory was not a player map.");
  const bySleeperId = new Map<string, IdentityHit>();
  const byEspnId = new Map<string, IdentityHit>();
  for (const [id, value] of Object.entries(source)) {
    const player = asRecord(value);
    if (!player || id.length > 40) continue;
    const first = typeof player.first_name === "string" ? player.first_name : "";
    const last = typeof player.last_name === "string" ? player.last_name : "";
    const name = clipText(player.full_name, 80, `${first} ${last}`.trim() || id);
    const hit: IdentityHit = {
      gsisId: typeof player.gsis_id === "string" && player.gsis_id.trim() ? player.gsis_id.trim() : null,
      name,
      position: typeof player.position === "string" ? player.position : "",
      nflTeam: typeof player.team === "string" ? player.team : "",
    };
    bySleeperId.set(id, hit);
    const espn = player.espn_id;
    const espnId = typeof espn === "number" && Number.isFinite(espn) ? String(espn) : typeof espn === "string" && /^\d+$/.test(espn) ? espn : "";
    if (espnId) byEspnId.set(espnId, hit);
  }
  return { bySleeperId, byEspnId };
}

/** One shared download per page load. A failure is not cached, so a later attempt can retry. */
export function loadPlayerDirectory(): Promise<IdentityIndex> {
  if (!directoryPromise) {
    directoryPromise = fetchDirectory().catch((error: unknown) => {
      directoryPromise = null;
      throw error;
    });
  }
  return directoryPromise;
}

async function fetchDirectory(): Promise<IdentityIndex> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 60_000);
  try {
    const response = await fetch(PLAYERS_URL, { signal: controller.signal, headers: { accept: "application/json" } });
    if (!response.ok) throw new LeagueConnectError("UNAVAILABLE", "The Sleeper player directory didn't load. Try again.");
    const index = indexSleeperPlayers(await response.json());
    if (index.bySleeperId.size < 100) throw new LeagueConnectError("INVALID", "The player directory did not include the NFL player list.");
    return index;
  } catch (error) {
    if (error instanceof LeagueConnectError) throw error;
    throw new LeagueConnectError("NETWORK", "The Sleeper player directory didn't load. Try again.");
  } finally {
    clearTimeout(timer);
  }
}
