import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { PlayHighlightList } from "./PlayHighlightList";
import type { PlayHighlightRow } from "@/lib/payload";

afterEach(() => {
  cleanup();
});

function completionRow(
  overrides: Partial<PlayHighlightRow> = {},
): PlayHighlightRow {
  return {
    playerId: "qb1",
    name: "J.Allen → S.Diggs",
    position: "WR",
    positionGroup: "pass_catcher",
    team: "BUF",
    opponent: "MIA",
    playClass: "completion",
    statId: "completion_yards",
    statLabel: "yard pass",
    value: 55,
    gameId: "g1",
    playId: 42,
    quarter: 2,
    clock: "04:12",
    gameClock: "Q2 04:12",
    touchdown: true,
    down: 2,
    distance: 7,
    yardline100: 75,
    yardline: "BUF 25",
    airYards: 40,
    yardsAfterCatch: 15,
    zScore: 3,
    peerN: 100,
    peerKey: "reception|pos:WR",
    passerId: "qb1",
    passerName: "J.Allen",
    passerPosition: "QB",
    receiverId: "wr1",
    receiverName: "S.Diggs",
    receiverPosition: "WR",
    favorableCount: 2,
    oneInN: 50,
    rarityTier: 50,
    rank: 1,
    ...overrides,
  };
}

it("shows situation and pass outcome above the histogram when expanded", () => {
  render(
    <PlayHighlightList
      season={2026}
      shapes={null}
      emptyLabel="empty"
      rows={[completionRow()]}
    />,
  );

  expect(screen.queryByTestId("play-summary")).toBeNull();

  fireEvent.click(screen.getByRole("button"));

  const summary = screen.getByTestId("play-summary");
  expect(summary.textContent).toContain("2nd & 7 from BUF 25");
  expect(summary.textContent).toContain("55 yd pass");
  expect(summary.textContent).toContain("40 air");
  expect(summary.textContent).toContain("15 YAC");
  expect(summary.textContent).toContain("Q2 04:12");
});
