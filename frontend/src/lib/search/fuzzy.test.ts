import { describe, expect, it } from "vitest";
import { searchPlayers } from "@/lib/player-index";
const chase = { id: "c", name: "Ja’Marr Chase", team: "CIN", position: "WR", seasons: [2026] };
const brown = { id: "b", name: "Amon-Ra St. Brown", team: "DET", position: "WR", seasons: [2026] };
describe("conservative player search", () => {
  it.each(["jamar chase", "ja marr chase", "CHASE", "cin", "wr"])("matches punctuation and fields: %s", q => {
    expect(searchPlayers([chase], q)).toEqual([chase]);
  });
  it("requires all query tokens", () => expect(searchPlayers([chase], "chase nonsense")).toEqual([]));
  it("does not approximate abbreviations", () => expect(searchPlayers([chase], "qb")).toEqual([]));
  it("preserves default order and handles diacritics", () => {
    const accented = { ...brown, name: "Amón-Ra St. Brown" };
    expect(searchPlayers([chase, accented], "")).toEqual([chase, accented]);
    expect(searchPlayers([accented], "amon ra brown")).toEqual([accented]);
  });
});
