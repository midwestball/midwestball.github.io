import React from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { HighlightsBrowser } from "./HighlightsBrowser";
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(location.search) }));
vi.mock("@/lib/ballnet-store", () => ({ fetchCurrentMeta: async () => null, fetchHighlightsBoard: async () => null, fetchLeagueWeeklyGroup: async () => null }));
afterEach(() => { cleanup(); history.replaceState(null, "", "/"); });
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
