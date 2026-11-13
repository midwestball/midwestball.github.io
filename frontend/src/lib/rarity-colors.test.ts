import { expect, it } from "vitest";
import { rarityTierColor, rarityTierShimmer } from "./distribution";

it("applies the new rarity colors at their thresholds and between tiers", () => {
  expect(rarityTierColor(19)).toBe("rgb(112, 168, 104)");
  expect(rarityTierColor(20)).toBe("rgb(173, 130, 80)");
  expect(rarityTierColor(50)).toBe("rgb(168, 169, 173)");
  expect(rarityTierColor(100)).toBe("rgb(168, 169, 173)");
  expect(rarityTierColor(500)).toBe("rgb(212, 175, 55)");
  expect(rarityTierColor(5_000)).toBe("rgb(126, 200, 227)");
  expect(rarityTierColor(50_000)).toBe("rgb(123, 94, 167)");
  expect(rarityTierColor(500_000)).toBe("rgb(168, 140, 210)");
  expect(rarityTierShimmer(19)).toBe(false);
  expect(rarityTierShimmer(20)).toBe(true);
});
