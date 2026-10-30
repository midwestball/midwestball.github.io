import { expect, it } from "vitest";
import { legacyPlayerComparisonHref, playerComparisonHref } from "./player-navigation";
it("selects stable player IDs and preserves optional season", () => {
  const url = new URL(playerComparisonHref("id with & punctuation", 2025), "https://example.test");
  expect(url.pathname).toBe("/search/");
  expect(url.searchParams.get("p")).toBe("id with & punctuation");
  expect(url.searchParams.get("season")).toBe("2025");
  expect(playerComparisonHref("a")).toBe("/search/?p=a");
});
it("converts legacy runtime and static profile links without losing context", () => {
  expect(legacyPlayerComparisonHref(new URLSearchParams("id=a&season=2025&utm=kept"))).toBe("/search/?season=2025&utm=kept&p=a");
  expect(legacyPlayerComparisonHref(new URLSearchParams("season=2024"), "b")).toBe("/search/?season=2024&p=b");
  expect(legacyPlayerComparisonHref(new URLSearchParams())).toBe("/search/");
});
