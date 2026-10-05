import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ExpandableStatRow } from "./ExpandableStatRow";
import { STAT_DESCRIPTIONS, statDescription } from "@/lib/catalog/stat-descriptions";
import { STATS_BY_GROUP } from "@/lib/catalog";
import type { StatPayload } from "@/lib/distribution";

afterEach(cleanup);

const theme = {
  shell: "",
  header: "",
  name: "",
  value: "",
  meta: "",
  chartWrap: "",
};

function payload(overrides: Partial<StatPayload> = {}): StatPayload {
  return {
    id: "cpoe",
    label: "CPOE",
    section: "Efficiency",
    playerValue: 4.2,
    percentile: 88,
    higherIsBetter: true,
    xMin: -25,
    xMax: 25,
    yMax: 0.04,
    format: "percent_pts",
    availability: "ready",
    minN: 28,
    denom: "attempts",
    curve: [
      { x: -25, y: 0.001 },
      { x: 0, y: 0.02 },
      { x: 25, y: 0.001 },
    ],
    kind: "continuous",
    ...overrides,
  };
}

describe("stat descriptions", () => {
  it("looks a description up by stat id", () => {
    expect(statDescription("cpoe")).toBe(STAT_DESCRIPTIONS.cpoe);
    expect(statDescription("cpoe")).toMatch(/Completion/i);
  });

  it("returns undefined for an unknown id instead of throwing", () => {
    expect(statDescription("not_a_real_stat")).toBeUndefined();
  });

  it("covers every stat id in the catalog", () => {
    const missing = Object.values(STATS_BY_GROUP)
      .flat()
      .filter((stat) => !STAT_DESCRIPTIONS[stat.id])
      .map((stat) => stat.id);
    expect(missing).toEqual([]);
  });

  it("has no entries for ids the catalog does not define", () => {
    const known = new Set(
      Object.values(STATS_BY_GROUP)
        .flat()
        .map((stat) => stat.id),
    );
    const orphans = Object.keys(STAT_DESCRIPTIONS).filter(
      (id) => !known.has(id),
    );
    expect(orphans).toEqual([]);
  });

  it("keeps every description non-empty and inside the render budget", () => {
    for (const [id, text] of Object.entries(STAT_DESCRIPTIONS)) {
      expect(text.length, id).toBeGreaterThan(0);
      expect(text.length, id).toBeLessThanOrEqual(240);
      expect(text, id).not.toMatch(/[<>]/);
    }
  });
});

describe("ExpandableStatRow", () => {
  it("hides the description until the row is expanded", () => {
    render(
      <ExpandableStatRow
        stat={payload()}
        theme={theme}
        chart={<div>chart</div>}
      />,
    );
    expect(screen.queryByTestId("stat-description")).toBeNull();
  });

  it("shows the description above the standing sentence when expanded", () => {
    render(
      <ExpandableStatRow
        stat={payload()}
        theme={theme}
        chart={<div>chart</div>}
      />,
    );
    fireEvent.click(screen.getByText("CPOE"));
    const description = screen.getByTestId("stat-description");
    expect(description.textContent).toBe(STAT_DESCRIPTIONS.cpoe);
    expect(description.textContent).toMatch(/Completion/i);
  });

  it("omits the description when the stat id has no entry", () => {
    render(
      <ExpandableStatRow
        stat={payload({ id: "unmapped_stat", label: "Unmapped" })}
        theme={theme}
        chart={<div>chart</div>}
      />,
    );
    fireEvent.click(screen.getByText("Unmapped"));
    expect(screen.queryByTestId("stat-description")).toBeNull();
  });

  it("offers a click hint on the collapsed label", () => {
    render(
      <ExpandableStatRow
        stat={payload()}
        theme={theme}
        chart={<div>chart</div>}
      />,
    );
    expect(screen.getByText("CPOE").getAttribute("title")).toBe(
      "Click for more info",
    );
  });

  it("flips the hint once the row is open", () => {
    render(
      <ExpandableStatRow
        stat={payload()}
        theme={theme}
        chart={<div>chart</div>}
      />,
    );
    fireEvent.click(screen.getByText("CPOE"));
    expect(screen.getByText("CPOE").getAttribute("title")).toBe(
      "Click to collapse",
    );
  });
});
