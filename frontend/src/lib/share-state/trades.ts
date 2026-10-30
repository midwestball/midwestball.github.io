import { DEFAULT_SETTINGS, validSettings, type RosterEntry, type RosterSettings } from "@/lib/trades";
export const TRADE_KEYS = ["v", "r", "s", "mode", "g", "a", "d"] as const;
const SETTINGS = [["QB", "QB"], ["RB", "RB"], ["WR", "WR"], ["TE", "TE"], ["F", "FLEX"], ["S", "SUPERFLEX"], ["B", "bench"], ["I", "ir"], ["K", "K"], ["D", "DST"]] as const;
export type TradeShareState = { mode: "roster" | "packages"; settings: RosterSettings; roster: RosterEntry[]; give: string[]; receive: string[]; drops: string[] };
export function decodeTradeShare(params: URLSearchParams, available?: ReadonlySet<string>): { state: TradeShareState | null; warnings: string[]; fatal?: string } {
  if (!TRADE_KEYS.some(k => params.has(k))) return { state: null, warnings: [] };
  try {
    if (params.toString().length > 16000) throw new Error("Shared scenario is too large.");
    if (params.get("v") !== "1") throw new Error("Unsupported trade link version.");
    if (TRADE_KEYS.some(k => params.getAll(k).length > 1)) throw new Error("Duplicate trade fields.");
    const list = (key: string, roster = false) => {
      const raw = params.get(key);
      if (raw === null || raw === "") return [];
      const ids = raw.split(",");
      if (ids.length > 44 || ids.some(id => !(roster ? /^~?[A-Za-z0-9_-]{1,128}$/ : /^[A-Za-z0-9_-]{1,128}$/).test(id)) ||
        new Set(ids.map(id => id.replace(/^~/, ""))).size !== ids.length) throw new Error(`Invalid ${key} player list.`);
      return ids;
    };
    const mode = params.get("mode");
    if (mode !== null && mode !== "packages") throw new Error("Invalid trade mode.");
    const settings = { ...DEFAULT_SETTINGS };
    const rawSettings = params.get("s");
    if (rawSettings !== null) {
      const tokens = rawSettings.split(".");
      if (tokens.length !== SETTINGS.length) throw new Error("Invalid lineup settings.");
      SETTINGS.forEach(([token, key], i) => {
        const match = tokens[i].match(new RegExp(`^${token}(\\d{1,2})$`));
        if (!match) throw new Error("Invalid lineup settings.");
        settings[key] = Number(match[1]);
      });
      if (!validSettings(settings)) throw new Error("Invalid lineup capacity.");
    }
    const roster = list("r", true).map(id => ({ playerId: id.replace(/^~/, ""), ir: id.startsWith("~") }));
    const give = list("g"), receive = list("a"), drops = list("d");
    const owned = new Set(roster.map(p => p.playerId));
    if (give.some(id => receive.includes(id) || drops.includes(id)) || receive.some(id => drops.includes(id))) throw new Error("Trade lists overlap.");
    if (mode === "packages") {
      if (["r", "s", "d"].some(k => params.has(k))) throw new Error("Package links cannot contain a roster, drops or settings.");
    } else if (give.some(id => !owned.has(id)) || drops.some(id => !owned.has(id)) || receive.some(id => owned.has(id))) throw new Error("Trade ownership is inconsistent.");
    const ids = [...owned, ...give, ...receive, ...drops];
    const missing = available ? [...new Set(ids)].filter(id => !available.has(id)) : [];
    return { state: { mode: mode ?? "roster", settings, roster, give, receive, drops }, warnings: missing.map(id => `Unavailable player: ${id}`) };
  } catch (error) { return { state: null, warnings: [], fatal: error instanceof Error ? error.message : "Invalid shared trade." }; }
}
export function encodeTradeShare(s: TradeShareState): URLSearchParams {
  const p = new URLSearchParams({ v: "1" });
  if (s.mode === "packages") p.set("mode", "packages");
  else {
    if (s.roster.length) p.set("r", s.roster.map(r => `${r.ir ? "~" : ""}${r.playerId}`).join(","));
    if (SETTINGS.some(([, key]) => s.settings[key] !== DEFAULT_SETTINGS[key])) p.set("s", SETTINGS.map(([token, key]) => `${token}${s.settings[key]}`).join("."));
    if (s.drops.length) p.set("d", s.drops.join(","));
  }
  if (s.give.length) p.set("g", s.give.join(","));
  if (s.receive.length) p.set("a", s.receive.join(","));
  const parsed = decodeTradeShare(p);
  if (parsed.fatal) throw new Error(parsed.fatal);
  return p;
}
