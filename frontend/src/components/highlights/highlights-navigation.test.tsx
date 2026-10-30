import React from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { HighlightsBrowser } from "./HighlightsBrowser";
import { HighlightList } from "./HighlightList";
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(location.search) }));
vi.mock("@/lib/ballnet-store", () => ({ fetchCurrentMeta: async () => null, fetchHighlightsBoard: async () => null, fetchLeagueWeeklyGroup: async () => null }));
afterEach(() => { cleanup(); history.replaceState(null, "", "/"); });
it("opens a highlighted player in comparison for the highlighted season without expanding the row", () => {
  render(<HighlightList season={2025} weeklyByGroup={{}} rows={[{
    playerId: "athlete", name: "Highlight Player", position: "WR", team: "CHI", opponent: "GB", positionGroup: "pass_catcher",
    statId: "yards", statLabel: "Yards", value: 100, zScore: 2, peerN: 100, oneInN: 10, rank: 1,
  }]} />);
  const link = screen.getByRole("link", { name: "Highlight Player" });
  const target = new URL(link.getAttribute("href")!, "https://example.test");
  expect(target.pathname.replace(/\/$/, "")).toBe("/search");
  expect(target.searchParams.get("p")).toBe("athlete");
  expect(target.searchParams.get("season")).toBe("2025");
  fireEvent.keyDown(link, { key: "Enter" });
  expect(link.closest('[role="button"]')?.getAttribute("aria-expanded")).toBe("false");
});
it("preserves unrelated query keys and restores a home slice on navigation", async () => {
  history.replaceState(null, "", "/?season=2026&week=7&utm=kept");
  render(<HighlightsBrowser startSeason={2024} currentSeason={2026} currentWeek={8} initialSeason={2026} initialWeek={8} />);
  const week = screen.getByRole("combobox", { name: "Week" });
  expect((week as HTMLSelectElement).value).toBe("7");
  fireEvent.change(week, { target: { value: "6" } });
  expect(new URLSearchParams(location.search).get("utm")).toBe("kept");
  expect(new URLSearchParams(location.search).get("week")).toBe("6");
  act(() => { history.replaceState(null, "", "/?season=2025&week=99"); window.dispatchEvent(new PopStateEvent("popstate")); });
  await waitFor(() => expect((week as HTMLSelectElement).value).toBe("18"));
  expect((screen.getByRole("combobox", { name: "Season" }) as HTMLSelectElement).value).toBe("2025");
});
