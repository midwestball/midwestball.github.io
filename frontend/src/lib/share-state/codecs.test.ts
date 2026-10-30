import { describe, expect, it } from "vitest";
import { patchQuery, parseIdList } from "./common";
import { decodeSearch, encodeSearch } from "./search";
import { decodeProjection } from "./projections";
import { decodeTradeShare, encodeTradeShare, type TradeShareState } from "./trades";
import { DEFAULT_SETTINGS } from "@/lib/trades";
describe("share contracts", () => {
  it("patches owned keys and deduplicates ordered selections", () => {
    expect(parseIdList("a,b,a,c,d,e")).toEqual(["a", "b", "c", "d"]);
    expect(patchQuery(new URLSearchParams("utm=x&p=a"), { p: null }).toString()).toBe("utm=x");
  });
  it("validates search dependencies and round trips filters", () => {
    const s = decodeSearch(new URLSearchParams("p=a,b,a&season=2026&pos=wr&stat=fantasy_pos_rank&min=5&sort=worst&q=chase"), [2026], 2026);
    expect(decodeSearch(new URLSearchParams(Object.entries(encodeSearch(s)).filter((p): p is [string,string] => p[1] !== null)), [2026], 2026)).toEqual(s);
    expect(decodeSearch(new URLSearchParams("pos=oops&stat=oops&season=9999"), [2026], 2026)).toMatchObject({ season: 2026, pos: null, statId: null });
  });
  it("keeps projection keys distinct and clamps thresholds", () => {
    expect(decodeProjection(new URLSearchParams("p=entity,missing&focus=missing&points=99"), new Set(["entity"]), [0, 50])).toEqual({ selected: ["entity"], focus: "entity", stale: 1, points: 50 });
  });
  const state: TradeShareState = { mode: "roster", settings: { ...DEFAULT_SETTINGS, SUPERFLEX: 1 }, roster: [{ playerId: "qb", ir: false }, { playerId: "wr", ir: true }], give: ["qb"], receive: ["rb"], drops: ["wr"] };
  it("round trips custom slots, IR, and ordered trade lists", () => {
    expect(decodeTradeShare(encodeTradeShare(state)).state).toEqual(state);
    expect(decodeTradeShare(encodeTradeShare(state), new Set(["qb"])).warnings).toHaveLength(2);
  });
  it.each(["v=2", "r=a", "v=1&r=", "v=1&g=", "v=1&r=a,~a", "v=1&r=a,,b", "v=1&r=a&g=b", "v=1&mode=packages&r=a", "v=1&a=a&g=a", "v=1&s=QB99"])("rejects malformed scenarios: %s", raw => expect(decodeTradeShare(new URLSearchParams(raw)).fatal).toBeTruthy());
  it("omits default slots and never truncates a full roster", () => {
    const full = { ...state, settings: DEFAULT_SETTINGS, roster: Array.from({ length: 44 }, (_, i) => ({ playerId: `00-00000${i}`, ir: false })), give: [], receive: [], drops: [] };
    const encoded = encodeTradeShare(full);
    expect(encoded.has("s")).toBe(false);
    expect(decodeTradeShare(encoded).state?.roster).toHaveLength(44);
    expect(encoded.toString().length).toBeLessThan(1800);
  });
});
