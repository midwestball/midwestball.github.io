import React from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { loadHydratedPlayerSnapshots } from "@/lib/ballnet-store";
import { useLeaderboardDiscovery } from "./useLeaderboardDiscovery";
import { PlayerSearchControls } from "./PlayerSearchControls";
import { PlayerLeaderboardFilters } from "./PlayerLeaderboardFilters";
import { PlayerDiscoveryResults } from "./PlayerDiscoveryResults";
export function PlayerSearch(props: Parameters<typeof useLeaderboardDiscovery>[0]) {
  const model = useLeaderboardDiscovery(props);
  return <div className="space-y-2"><PlayerSearchControls model={model} /><PlayerLeaderboardFilters model={model} /><PlayerDiscoveryResults model={model} /></div>;
}

import { SearchPageClient } from "./SearchPageClient";

vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(window.location.search), useRouter: () => ({ push: (href: string) => window.history.pushState(null, "", href) }) }));
vi.mock("@/components/compare/CompareBoard", () => ({ CompareBoard: () => <div>Comparison board</div> }));

const players = [
  { id: "wr", name: "Wide Receiver", position: "WR", team: "CHI", seasons: [2026] },
  { id: "te", name: "Tight End", position: "TE", team: "GB", seasons: [2026] },
  { id: "rb", name: "Running Back", position: "RB", team: "CHI", seasons: [2026] },
];
vi.mock("@/lib/ballnet-store", () => ({
  fetchPlayersIndex: async () => null, fetchSeasonsMeta: async () => null, fetchCurrentMeta: async () => null,
  loadHydratedPlayerSnapshots: vi.fn(async () => ({ page: null, snapshots: [] })),
  fetchLeaderboard: async () => ({ schemaVersion: 1, season: 2026, asOfWeek: 8, completedWeek: 7,
    stats: { receiving_yards: players.map((p, i) => ({ playerId: p.id, ...p, value: 300 - i, percentile: 90 - i,
      denomYtd: 40, qualified: true, fantasyPosRank: i + 1, fantasyPosRankKind: "finish" })) } }),
}));
afterEach(() => { cleanup(); history.replaceState(null, "", "/"); vi.clearAllMocks(); });
describe("published discovery filters", () => {
  it.each(["", "wr"])("places comparison between search controls and the grouped filter results: %s", async selected => {
    history.replaceState(null, "", `/search/?season=2026&p=${selected}`);
    render(<SearchPageClient players={players} seasons={[{ season: 2026, asOfWeek: 8 }]} initialSeason={2026} />);
    const results = screen.getByRole("region", { name: "Filter results" });
    expect(results.contains(screen.getByLabelText("Position"))).toBe(true);
    expect(results.contains(screen.getByRole("heading", { name: "Filter results" }))).toBe(true);
    expect(screen.getByLabelText("Search players").compareDocumentPosition(results) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getAllByLabelText("Season")).toHaveLength(1);
    if (selected) {
      await waitFor(() => expect(screen.getByText("Comparison board")).toBeTruthy());
      const board = screen.getByText("Comparison board");
      expect(screen.getByLabelText("Search players").compareDocumentPosition(board) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      expect(board.compareDocumentPosition(results) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
    expect(screen.queryByRole("heading", { name: "Discovery results" })).toBeNull();
  });
  it.each(["", "&pos=backfield&stat=fantasy_pos_rank"])("hides incompatible discovery rows until the selection is removed: %s", async filters => {
    history.replaceState(null, "", `/search/?season=2026${filters}`);
    render(<SearchPageClient players={players} seasons={[{ season: 2026, asOfWeek: 8 }]} initialSeason={2026} />);
    await waitFor(() => expect(screen.getByRole("link", { name: /Running Back/ })).toBeTruthy());
    act(() => { history.replaceState(null, "", `/search/?season=2026&p=wr${filters}`); window.dispatchEvent(new PopStateEvent("popstate")); });
    await waitFor(() => expect(screen.queryByRole("link", { name: /Running Back/ })).toBeNull());
    expect(screen.getByRole("button", { name: "Remove Wide Receiver" })).toBeTruthy();
    if (!filters) expect(screen.getByRole("link", { name: /Tight End/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Remove Wide Receiver" }));
    await waitFor(() => expect(screen.getByRole("link", { name: /Running Back/ })).toBeTruthy());
  });
  it("keeps comparison failures local and supports retry", async () => {
    vi.mocked(loadHydratedPlayerSnapshots).mockRejectedValueOnce(new Error("offline"));
    history.replaceState(null, "", "/search/?p=wr&season=2026");
    render(<SearchPageClient players={players} seasons={[{ season: 2026, asOfWeek: 8 }]} initialSeason={2026} />);
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("Could not load comparison"));
    expect(screen.getByLabelText("Position")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Retry comparison" }));
    await waitFor(() => expect(screen.getByText("Comparison board")).toBeTruthy());
  });
  it("hydrates canonical selections and preserves them across discovery filters", async () => {
    window.history.replaceState(null, "", "/search/?p=wr&season=2026&pos=wr&stat=fantasy_pos_rank&utm=kept");
    const props = { players, seasons: [{ season: 2026, asOfWeek: 8 }], initialSeason: 2026 };
    const { rerender } = render(<SearchPageClient {...props} />);
    await waitFor(() => expect(screen.getByText("Comparison board")).toBeTruthy());
    const calls = vi.mocked(loadHydratedPlayerSnapshots).mock.calls.length;
    fireEvent.change(screen.getByLabelText("Search players"), { target: { value: "end" } });
    expect(vi.mocked(loadHydratedPlayerSnapshots).mock.calls).toHaveLength(calls);
    fireEvent.change(screen.getByLabelText("Position"), { target: { value: "te" } });
    rerender(<SearchPageClient {...props} />);
    expect(new URLSearchParams(location.search).get("p")).toBe("wr");
    expect(new URLSearchParams(location.search).get("utm")).toBe("kept");
    expect(new URLSearchParams(location.search).has("stat")).toBe(false);
    expect(screen.getByRole("button", { name: "Remove Wide Receiver" })).toBeTruthy();
    act(() => { window.history.replaceState(null, "", "/search/?p=te&season=2026"); window.dispatchEvent(new PopStateEvent("popstate")); });
    expect(screen.getByRole("button", { name: "Remove Tight End" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Remove Wide Receiver" })).toBeNull();
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
