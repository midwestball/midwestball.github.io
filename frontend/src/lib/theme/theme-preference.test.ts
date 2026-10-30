import { beforeEach, describe, expect, it } from "vitest";
import { parseThemePreference, resolveTheme, THEME_BOOTSTRAP, THEME_KEY } from "./theme-preference";
beforeEach(() => { localStorage.clear(); delete document.documentElement.dataset.theme; });
describe("automatic theme contract", () => {
  it("accepts only explicit known overrides", () => {
    expect(parseThemePreference("light")).toBe("light"); expect(parseThemePreference("dark")).toBe("dark");
    for (const value of [null, "system", "invalid", "<script>"]) expect(parseThemePreference(value)).toBe("system");
  });
  it("follows positive light detection and otherwise uses charcoal", () => {
    expect(resolveTheme("system", true, false)).toBe("light");
    expect(resolveTheme("system", false, true)).toBe("dark");
    expect(resolveTheme("system", false, false)).toBe("dark");
    expect(resolveTheme("dark", true, false)).toBe("dark");
  });
  it("bootstraps an override without writing storage and synchronizes other tabs", () => {
    localStorage.setItem(THEME_KEY, "light"); window.eval(THEME_BOOTSTRAP);
    expect(document.documentElement.dataset.theme).toBe("light");
    localStorage.setItem(THEME_KEY, "system"); window.dispatchEvent(new StorageEvent("storage", { key: THEME_KEY }));
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
    expect(localStorage.getItem(THEME_KEY)).toBe("system");
  });
});
