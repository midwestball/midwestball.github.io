import { expect, it } from "vitest";
import { playerKdeFromCounts } from "./player-kde";

it("reproduces the original reflected SciPy KDE from exact peer counts", () => {
  // Reference values from scipy.stats.gaussian_kde with Scott bandwidth,
  // reflection at 0 and 4, a 512-point grid, and trapezoidal normalization.
  const result = playerKdeFromCounts(
    [{ value: 0, count: 1 }, { value: 1, count: 2 }, { value: 2, count: 1 }, { value: 4, count: 1 }],
    { xMin: 0, xMax: 10, lowerBound: 0, upperBound: 4 },
  );
  expect(result?.curve).toHaveLength(512);
  expect(result?.xMin).toBe(0);
  expect(result?.xMax).toBe(4);
  expect(result?.yMax).toBeCloseTo(0.36517715720522154, 12);
  expect(result?.curve[128]?.y).toBeCloseTo(0.3219946318496333, 12);
  expect(result?.curve[256]?.y).toBeCloseTo(0.22740080094110415, 12);
  expect(result?.curve[511]?.y).toBeCloseTo(0.18021966158001465, 12);
});

it("handles a constant sample like the original and refuses invalid counts", () => {
  const constant = playerKdeFromCounts([{ value: 2, count: 3 }], { xMin: 0, xMax: 10 });
  expect(constant?.xMin).toBe(2);
  expect(constant?.xMax).toBe(2.1);
  expect(constant?.curve[0]?.y).toBeCloseTo(5110, 8);
  expect(constant?.curve[1]?.y).toBe(0);
  expect(playerKdeFromCounts([], { xMin: 0, xMax: 1 })).toBeNull();
  expect(playerKdeFromCounts([{ value: 1, count: -1 }], { xMin: 0, xMax: 1 })).toBeNull();
  expect(playerKdeFromCounts([{ value: NaN, count: 1 }], { xMin: 0, xMax: 1 })).toBeNull();
});
