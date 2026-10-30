import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PlayerSearch } from "./PlayerSearch";
import { SearchPageClient } from "./SearchPageClient";

vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(window.location.search), useRouter: () => ({ push: (href: string) => window.history.pushState(null, "", href) }) }));
vi.mock("@/components/compare/CompareBoard", () => ({ CompareBoard: () => <div>Comparison board</div> }));

const players = [
  { id: "wr", name: "Wide Receiver", position: "WR", team: "CHI", seasons: [2026] },
  { id: "te", name: "Tight End", position: "TE", team: "GB", seasons: [2026] },
];
vi.mock("@/lib/ballnet-store", () => ({
  fetchPlayersIndex: async () => null, fetchSeasonsMeta: async () => null, fetchCurrentMeta: async () => null,
  loadHydratedPlayerSnapshots: async () => ({ page: null, snapshots: [] }),
  fetchLeaderboard: async () => ({ schemaVersion: 1, season: 2026, asOfWeek: 8, completedWeek: 7,
    stats: { receiving_yards: players.map((p, i) => ({ playerId: p.id, ...p, value: 300 - i, percentile: 90 - i,
      denomYtd: 40, qualified: true, fantasyPosRank: i + 1, fantasyPosRankKind: "finish" })) } }),
}));
afterEach(cleanup);
describe("published discovery filters", () => {
  it("hydrates canonical selections and preserves them across discovery filters", async () => {
    window.history.replaceState(null, "", "/search/?p=wr&season=2026&pos=wr&stat=fantasy_pos_rank&utm=kept");
    const props = { players, seasons: [{ season: 2026, asOfWeek: 8 }], initialSeason: 2026 };
    const { rerender } = render(<SearchPageClient {...props} />);
    await waitFor(() => expect(screen.getByText("Comparison board")).toBeTruthy());
    fireEvent.change(screen.getByLabelText("Position"), { target: { value: "te" } });
    rerender(<SearchPageClient {...props} />);
    expect(new URLSearchParams(location.search).get("p")).toBe("wr");
    expect(new URLSearchParams(location.search).get("utm")).toBe("kept");
    expect(new URLSearchParams(location.search).has("stat")).toBe(false);
    expect(screen.getByRole("button", { name: "Remove Wide Receiver" })).toBeTruthy();
    window.history.replaceState(null, "", "/");
  });
  it("splits WR and TE from the same board without losing profile links", async () => {
    render(<PlayerSearch players={players} seasons={[{ season: 2026, asOfWeek: 8, completedWeek: 7 }]} initialSeason={2026} />);
    fireEvent.change(screen.getByLabelText("Position"), { target: { value: "wr" } });
    await waitFor(() => expect(screen.queryByText("Tight End")).toBeNull());
    expect(screen.getByRole("link", { name: /Wide Receiver/ }).getAttribute("href")).toContain("season=2026");
    fireEvent.change(screen.getByLabelText("Position"), { target: { value: "te" } });
    await waitFor(() => expect(screen.getByText("Tight End")).toBeTruthy());
    expect(screen.queryByText("Wide Receiver")).toBeNull();
  });
  it("uses published fantasy ranks and keeps volume disabled", async () => {
    render(<PlayerSearch players={players} seasons={[{ season: 2026, asOfWeek: 8 }]} initialSeason={2026} />);
    fireEvent.change(screen.getByLabelText("Position"), { target: { value: "wr" } });
    fireEvent.change(screen.getByLabelText("Stat"), { target: { value: "fantasy_pos_rank" } });
    await waitFor(() => expect(screen.getByText("PPR finish")).toBeTruthy());
    expect(screen.getByLabelText(/Minimum .* value/).hasAttribute("disabled")).toBe(true);
  });
});
