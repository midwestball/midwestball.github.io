import { rosMedian, type RosPlayer, type RosPosition } from "./ros";

export const SLOT_TYPES = ["QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX"] as const;
export type SlotType = (typeof SLOT_TYPES)[number];
export type RosterSettings = Record<SlotType, number> & { bench: number; ir: number; K: number; DST: number };
export type RosterEntry = { playerId: string; ir: boolean };
export const DEFAULT_SETTINGS: RosterSettings = { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, SUPERFLEX: 0, bench: 6, ir: 1, K: 1, DST: 1 };
export const eligible = (slot: SlotType, pos: RosPosition) => slot === "SUPERFLEX" || slot === pos || (slot === "FLEX" && pos !== "QB");
export const activeCapacity = (s: RosterSettings) => SLOT_TYPES.reduce((n, slot) => n + s[slot], 0) + s.bench;
export const validSettings = (s: RosterSettings) =>
  [...SLOT_TYPES, "bench", "ir", "K", "DST"].every(k => Number.isInteger(s[k as keyof RosterSettings]) && s[k as keyof RosterSettings] >= 0 && s[k as keyof RosterSettings] <= 12) &&
  SLOT_TYPES.reduce((n, k) => n + s[k], 0) > 0 && SLOT_TYPES.reduce((n, k) => n + s[k], 0) <= 16 && activeCapacity(s) <= 32;

export type Lineup = { total: number; assignments: { slot: SlotType; player: RosPlayer | null }[] };

/** Maximum-weight player/slot matching. Residual edges let a FLEX move to RB so
 * another player can fill FLEX; a greedy assignment can miss the best lineup. */
export function optimizeLineup(players: RosPlayer[], settings: RosterSettings): Lineup {
  if (!validSettings(settings)) throw new Error("Invalid lineup settings");
  const unique = [...new Map(players.map(p => [p.playerId, p])).values()];
  const slots = SLOT_TYPES.flatMap(s => Array<SlotType>(settings[s]).fill(s));
  const source = 0, playerStart = 1, slotStart = playerStart + unique.length, sink = slotStart + slots.length;
  type Edge = { to: number; reverse: number; capacity: number; cost: number };
  const graph: Edge[][] = Array.from({ length: sink + 1 }, () => []);
  function edge(from: number, to: number, cost: number) {
    const forward = { to, reverse: graph[to].length, capacity: 1, cost };
    graph[from].push(forward);
    graph[to].push({ to: from, reverse: graph[from].length - 1, capacity: 0, cost: -cost });
    return forward;
  }
  const candidates: { player: RosPlayer; slot: number; edge: Edge }[] = [];
  unique.forEach((p, i) => {
    edge(source, playerStart + i, 0);
    slots.forEach((slot, j) => {
      if (eligible(slot, p.position)) candidates.push({ player: p, slot: j, edge: edge(playerStart + i, slotStart + j, -rosMedian(p)) });
    });
  });
  slots.forEach((_, j) => { edge(source, slotStart + j, 0); edge(slotStart + j, sink, 0); });
  for (let flow = 0; flow < slots.length; flow++) {
    const dist = Array<number>(graph.length).fill(Infinity), parent = Array<number>(graph.length).fill(-1), via = [...parent];
    dist[source] = 0;
    for (let step = 0; step < graph.length - 1; step++) {
      let changed = false;
      graph.forEach((edges, from) => edges.forEach((e, i) => {
        if (e.capacity && dist[e.to] > dist[from] + e.cost + 1e-8) {
          dist[e.to] = dist[from] + e.cost; parent[e.to] = from; via[e.to] = i; changed = true;
        }
      }));
      if (!changed) break;
    }
    for (let node = sink; node !== source;) {
      const from = parent[node], e = graph[from][via[node]];
      e.capacity--; graph[node][e.reverse].capacity++; node = from;
    }
  }
  const assignments = slots.map((slot, j) => ({ slot, player: candidates.find(c => c.slot === j && c.edge.capacity === 0)?.player ?? null }));
  return { assignments, total: assignments.reduce((sum, a) => sum + (a.player ? rosMedian(a.player) : 0), 0) };
}

export function evaluateTrade(players: RosPlayer[], roster: RosterEntry[], give: string[], receive: string[], drops: string[], settings: RosterSettings) {
  if (!validSettings(settings)) throw new Error("Choose valid lineup settings.");
  if (!give.length && !receive.length) throw new Error("Select players to give or receive.");
  const byId = new Map(players.map(p => [p.playerId, p]));
  const own = new Set(roster.map(p => p.playerId));
  if (own.size !== roster.length || [...give, ...receive, ...drops].some(id => !byId.has(id))) throw new Error("A selected player is unavailable in this projection snapshot.");
  if ([give, receive, drops].some(ids => new Set(ids).size !== ids.length)) throw new Error("Select each player only once.");
  if (give.some(id => !own.has(id)) || drops.some(id => !own.has(id) || give.includes(id)) || receive.some(id => own.has(id))) throw new Error("Players given or dropped must be on your roster; received players must be outside it.");
  const after = roster.filter(p => !give.includes(p.playerId) && !drops.includes(p.playerId)).concat(receive.map(playerId => ({ playerId, ir: false })));
  const check = (entries: RosterEntry[]) => {
    if (entries.some(p => !byId.has(p.playerId))) throw new Error("Remove unavailable roster players before evaluating.");
    if (entries.filter(p => !p.ir).length > activeCapacity(settings)) throw new Error("The roster exceeds its player limit. Add a drop or increase bench slots.");
    if (entries.filter(p => p.ir).length > settings.ir) throw new Error("The roster exceeds its IR limit.");
  };
  check(roster); check(after);
  const lineup = (entries: RosterEntry[]) => optimizeLineup(entries.filter(p => !p.ir).map(p => byId.get(p.playerId)!), settings);
  const beforeLineup = lineup(roster), afterLineup = lineup(after);
  const sum = (ids: string[]) => ids.reduce((n, id) => n + rosMedian(byId.get(id)!), 0);
  return {
    before: beforeLineup, after: afterLineup,
    lineupDelta: afterLineup.total - beforeLineup.total,
    packageDelta: sum(receive) - sum(give),
    rosterDelta: sum(receive) - sum(give) - sum(drops),
  };
}

export function restoreRoster(raw: unknown): { settings: RosterSettings; roster: RosterEntry[] } | null {
  if (!raw || typeof raw !== "object") return null;
  const v = raw as { version?: unknown; settings: RosterSettings; roster: RosterEntry[] };
  if (v.version !== 1 || !v.settings || !validSettings(v.settings) || !Array.isArray(v.roster) || v.roster.length > 44 ||
      !v.roster.every(p => p && typeof p.playerId === "string" && typeof p.ir === "boolean") ||
      new Set(v.roster.map(p => p.playerId)).size !== v.roster.length) return null;
  return { settings: v.settings, roster: v.roster };
}
