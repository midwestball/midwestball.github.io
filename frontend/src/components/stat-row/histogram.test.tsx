import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { HistogramChart } from "./HistogramChart";
import { percentileAt, type StatPayload } from "@/lib/distribution";

afterEach(cleanup);

it("shows observed bin counts in an accessible table", () => {
  render(<HistogramChart label="Yards" format="yards" bins={[{ lower: -1, upper: 0, count: 1 }, { lower: 0, upper: 1, count: 2 }]} />);
  expect(screen.getByRole("img").getAttribute("aria-label")).toContain("number of observations");
  expect(screen.getByRole("table").textContent).toContain("2");
});

it("shows observed and cumulative shares immediately on hover and keyboard focus", () => {
  render(<HistogramChart label="Yards" format="yards" interactive shadeColor="red" bins={[{ lower: 0, upper: 1, count: 1 }, { lower: 1, upper: 2, count: 2 }, { lower: 2, upper: 3, count: 0 }]} />);
  const bars = screen.getAllByRole("button");
  fireEvent.mouseEnter(bars[0]);
  expect(screen.getByRole("status").textContent).toContain("0 to under 1 · 1 performance");
  expect(screen.getByRole("status").textContent).toContain("33.3% of performances in this range · 33.3% below 1");
  fireEvent.focus(bars[1]);
  expect(screen.getByRole("status").textContent).toContain("66.7% of performances in this range · 100.0% below 2");
  fireEvent.focus(bars[2]);
  expect(screen.getByRole("status").textContent).toContain("2 to 3 · 0 performances");
  expect(screen.getByRole("status").textContent).toContain("0.0% of performances in this range · 100.0% at or below 3");
});

it("distinguishes silver shaded bars and reveals the player line on hover and focus", () => {
  render(<HistogramChart label="yards" format="yards" interactive shadeColor="rgb(168, 169, 173)" bins={[{ lower: 0, upper: 1, count: 1 }, { lower: 1, upper: 2, count: 2 }]} markers={[{ name: "Alex", value: 1, color: "silver" }]} />);
  const buttons = screen.getAllByRole("button");
  fireEvent.mouseEnter(buttons[1]);
  expect(buttons[0].previousElementSibling?.getAttribute("fill")).toBe("rgb(168, 169, 173)");
  expect(buttons[0].previousElementSibling?.getAttribute("fill-opacity")).toBe("1");
  expect(buttons[1].previousElementSibling?.getAttribute("fill")).toBe("#626367");
  const marker = screen.getByRole("button", { name: /Alex: 1 yards; player result line/ });
  fireEvent.mouseEnter(marker);
  expect(screen.getByRole("status").textContent).toContain("Alex: 1 yards");
  expect(screen.getByRole("status").textContent).toContain("The line marks this player’s result.");
  fireEvent.focus(marker);
  expect(screen.getByRole("status").textContent).toContain("Alex: 1 yards");
});

it("calculates exact midranks from value counts, not histogram bins", () => {
  const stat: StatPayload = { id: "x", label: "X", section: "Stats", playerValue: 2, percentile: 50, higherIsBetter: true, xMin: 0, xMax: 6, yMax: 2, format: "count", availability: "ready", minN: 1, denom: "games", kind: "discrete", valueCounts: [{ value: 1, count: 1 }, { value: 2, count: 2 }, { value: 5, count: 1 }], curve: [] };
  expect(percentileAt(stat, 2)).toBe(50);
  expect(percentileAt({ ...stat, higherIsBetter: false }, 1)).toBe(87.5);
});
