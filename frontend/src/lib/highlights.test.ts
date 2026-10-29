import { expect, it } from "vitest";
import { collapseHighlightsByPlayer } from "./highlights";
import type { HighlightRow } from "./payload";

it("orders empirical highlights by observed rarity rather than legacy z score", () => {
  const base: HighlightRow = { playerId: "p", name: "Player", position: "RB", team: "T", opponent: "O", positionGroup: "backfield", statId: "a", statLabel: "A", value: 1, zScore: 10, peerN: 100, oneInN: 2, rarityScore: .5, rarityMethod: "empirical-inclusive-v2", rank: 1 };
  const rare = { ...base, statId: "b", statLabel: "B", zScore: 1, rarityScore: .99, oneInN: 100 };
  const result = collapseHighlightsByPlayer([base, rare]);
  expect(result[0]?.statId).toBe("b");
  expect(result[0]?.also?.[0]?.statId).toBe("a");
});
