import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
const css = readFileSync("src/app/globals.css", "utf8");
function luminance(hex: string) {
  const rgb = hex.match(/[a-f\d]{2}/gi)!.map(v => parseInt(v, 16) / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4);
  return .2126 * rgb[0] + .7152 * rgb[1] + .0722 * rgb[2];
}
function contrast(a: string, b: string) { const x = luminance(a), y = luminance(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); }
describe("semantic token contrast", () => {
  for (const [mode, selector] of [["charcoal", ":root {"], ["light", ':root[data-theme="light"] {']]) {
    it(`${mode} text and focus meet representative contrast targets`, () => {
      const block = css.slice(css.indexOf(selector)).split("}")[0];
      const tokens = Object.fromEntries([...block.matchAll(/--([\w-]+): (#[a-f\d]{6});/g)].map(m => [m[1], m[2]]));
      for (const surface of ["background", "card", "muted", "popover"]) {
        for (const ink of ["foreground", "muted-foreground", "text-secondary"]) expect(contrast(tokens[ink], tokens[surface]), `${ink} on ${surface}`).toBeGreaterThanOrEqual(4.5);
      }
      expect(contrast(tokens.ring, tokens.card)).toBeGreaterThanOrEqual(3);
      expect(contrast(tokens.border, tokens.card)).toBeGreaterThanOrEqual(3);
      expect(contrast(tokens["warning-foreground"], tokens["warning-surface"])).toBeGreaterThanOrEqual(4.5);
      expect(contrast(tokens.destructive, tokens["error-surface"])).toBeGreaterThanOrEqual(4.5);
    });
  }
});
