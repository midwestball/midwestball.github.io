import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { TremorDistribution } from "./TremorDistribution";
import { CompareOverlayChart } from "@/components/compare/CompareOverlayChart";
import type { StatPayload } from "@/lib/distribution";
import { percentileAt } from "@/lib/distribution";
import { playerKdeForStat } from "@/lib/player-kde";

afterEach(cleanup);

const stat: StatPayload = {
  id: "cpoe", label: "CPOE", section: "Efficiency", playerValue: 1, percentile: 75,
  higherIsBetter: true, xMin: 0, xMax: 3, yMax: 2, format: "one_decimal",
  availability: "ready", minN: 1, denom: "attempts", kind: "continuous", curve: [],
  bins: [{ lower: 0, upper: 1, count: 1 }, { lower: 1, upper: 2, count: 2 }],
  valueCounts: [{ value: 0, count: 1 }, { value: 1, count: 2 }],
};

it("uses the KDE chart for v2 player stats even when histogram bins are present", () => {
  const { container } = render(<TremorDistribution stat={stat} />);
  expect(container.querySelector(".recharts-responsive-container")).not.toBeNull();
  expect(screen.queryByText("Show histogram counts")).toBeNull();
});

it("uses the shared KDE and player legend for v2 compare stats", () => {
  render(<CompareOverlayChart markers={[{ playerId: "a", name: "Alex Player", color: "red", stat }]} fills={new Map()} />);
  expect(screen.getByText(/Hover or click a name to shade/)).toBeTruthy();
  expect(screen.getByRole("button", { name: /A\. Player/ })).toBeTruthy();
  expect(screen.queryByText("Show histogram counts")).toBeNull();
});

it("keeps empirical midranks and uses an existing legacy KDE verbatim", () => {
  expect(percentileAt(stat, 1)).toBeCloseTo(200 / 3);
  const curve = [{ x: 0, y: 1 }, { x: 1, y: 2 }];
  expect(playerKdeForStat({ ...stat, curve })?.curve).toBe(curve);
});
