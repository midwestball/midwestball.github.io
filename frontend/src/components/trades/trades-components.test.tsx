import React from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TradesPageClient } from "./TradesPageClient";
import { RosProjections } from "../projections/RosProjections";
import { DEFAULT_SETTINGS } from "@/lib/trades";
import type { RosSnapshot } from "@/lib/ros";

const fixture: RosSnapshot = {
  schemaVersion: 1, kind: "ros", snapshotId: "test", season: 2026, cutoffWeek: 6,
  generatedAt: "2026-10-20T12:00:00Z", modelVersion: "test", scoringProfile: "ppr-v1",
  quantileLevels: [.05, .25, .5, .75, .95], methodology: "Test methodology",
  entities: ["QB", "RB", "WR", "TE"].map((position, i) => ({
    playerId: position, position: position as "QB" | "RB" | "WR" | "TE", name: `Player ${position}`,
    team: "CHI", remainingTeamGames: 11, mean: 110 + i, quantiles: [0, 50, 100 + i, 150, 200],
  })),
};
const state = { snapshot: fixture as RosSnapshot | null, error: "", retry: vi.fn() };
vi.mock("../projections/useRos", () => ({ useRos: () => state }));
beforeEach(() => { window.history.replaceState(null, "", "/trades/"); localStorage.clear(); state.snapshot = fixture; state.error = ""; });
afterEach(cleanup);

describe("ROS and roster controls", () => {
  it("restores shared trade history and personal state without accidental storage writes", async () => {
    const saved = JSON.stringify({ version: 1, settings: DEFAULT_SETTINGS, roster: [{ playerId: "QB", ir: false }] });
    localStorage.setItem("midwestball-trade-roster-v1", saved);
    history.replaceState(null, "", "/trades/?v=1&r=RB&g=RB&a=WR");
    render(<TradesPageClient />);
    await waitFor(() => expect(screen.getByLabelText("Status for Player RB")).toBeTruthy());
    act(() => { history.replaceState(null, "", "/trades/?v=1&r=TE&a=WR"); window.dispatchEvent(new PopStateEvent("popstate")); });
    expect(screen.getByLabelText("Status for Player TE")).toBeTruthy();
    expect(localStorage.getItem("midwestball-trade-roster-v1")).toBe(saved);
    act(() => { history.replaceState(null, "", "/trades/"); window.dispatchEvent(new PopStateEvent("popstate")); });
    await waitFor(() => expect(screen.getByLabelText("Status for Player QB")).toBeTruthy());
    expect(localStorage.getItem("midwestball-trade-roster-v1")).toBe(saved);
  });
  it("opens and edits a shared roster without overwriting personal storage, then explicitly saves", async () => {
    const saved = JSON.stringify({ version: 1, settings: DEFAULT_SETTINGS, roster: [{ playerId: "QB", ir: false }] });
    localStorage.setItem("midwestball-trade-roster-v1", saved);
    window.history.replaceState(null, "", "/trades/?v=1&r=RB,~TE&g=RB&a=WR");
    render(<TradesPageClient />);
    await waitFor(() => expect(screen.getByText(/Viewing a shared trade/)).toBeTruthy());
    expect(screen.getByLabelText("Status for Player TE")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Status for Player TE"), { target: { value: "active" } });
    expect(localStorage.getItem("midwestball-trade-roster-v1")).toBe(saved);
    fireEvent.click(screen.getByRole("button", { name: "Save this roster" }));
    expect(JSON.parse(localStorage.getItem("midwestball-trade-roster-v1")!).roster).toEqual([{ playerId: "RB", ir: false }, { playerId: "TE", ir: false }]);
  });
  it("rejects invalid shares without touching storage and restores the personal roster", async () => {
    const saved = JSON.stringify({ version: 1, settings: DEFAULT_SETTINGS, roster: [{ playerId: "QB", ir: false }] });
    localStorage.setItem("midwestball-trade-roster-v1", saved);
    window.history.replaceState(null, "", "/trades/?v=99&r=RB");
    render(<TradesPageClient />);
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("version"));
    expect(localStorage.getItem("midwestball-trade-roster-v1")).toBe(saved);
    fireEvent.click(screen.getByRole("button", { name: "Return to my saved roster" }));
    await waitFor(() => expect(screen.getByLabelText("Status for Player QB")).toBeTruthy());
  });
  it("shows the five ROS quantiles and mean for a selected player", () => {
    render(<RosProjections />);
    fireEvent.focus(screen.getByLabelText("Add a ROS projection"));
    fireEvent.click(screen.getByRole("button", { name: /Player WR/ }));
    expect(screen.getByRole("columnheader", { name: "Median" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "5%" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "95%" })).toBeTruthy();
    expect(screen.getByText("112.0")).toBeTruthy();
  });
  it("creates and saves a roster, supports superflex, and selects outgoing players", async () => {
    render(<TradesPageClient />);
    await waitFor(() => expect(localStorage.getItem("midwestball-trade-roster-v1")).not.toBeNull());
    fireEvent.click(screen.getByText("Lineup settings"));
    fireEvent.click(screen.getByRole("button", { name: "Superflex" }));
    expect((screen.getByLabelText("SUPERFLEX slots") as HTMLInputElement).value).toBe("1");
    fireEvent.focus(screen.getByLabelText("Add to your roster"));
    fireEvent.click(screen.getByRole("button", { name: /Player RB/ }));
    fireEvent.change(screen.getByLabelText("Trade action for Player RB"), { target: { value: "give" } });
    fireEvent.focus(screen.getByLabelText("Add a player to receive"));
    fireEvent.click(screen.getByRole("button", { name: /Player WR/ }));
    expect(screen.getByText("Starting lineup difference")).toBeTruthy();
    await waitFor(() => expect(JSON.parse(localStorage.getItem("midwestball-trade-roster-v1")!).roster).toEqual([{ playerId: "RB", ir: false }]));
  });
  it("supports package-only analysis without creating a roster", () => {
    render(<TradesPageClient />);
    fireEvent.click(screen.getByRole("button", { name: "Player packages" }));
    fireEvent.focus(screen.getByLabelText("Add a player to give"));
    fireEvent.click(screen.getByRole("button", { name: /Player RB/ }));
    fireEvent.focus(screen.getByLabelText("Add a player to receive"));
    fireEvent.click(screen.getByRole("button", { name: /Player WR/ }));
    expect(screen.getByText("Player package difference")).toBeTruthy();
    expect(screen.queryByText("Starting lineup difference")).toBeNull();
  });
  it("retains and identifies saved players absent from the new snapshot", async () => {
    localStorage.setItem("midwestball-trade-roster-v1", JSON.stringify({ version: 1, settings: DEFAULT_SETTINGS, roster: [{ playerId: "missing", ir: true }] }));
    render(<TradesPageClient />);
    await waitFor(() => expect(screen.getByText(/Unavailable in this snapshot/)).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Remove missing from roster" }));
    expect(screen.queryByText(/Unavailable in this snapshot/)).toBeNull();
  });
  it("shows a useful message and retry for snapshots without ROS", () => {
    state.snapshot = null; state.error = "Rest-of-season projections have not been published for this snapshot yet.";
    render(<RosProjections />);
    expect(screen.getByRole("status").textContent).toContain("not been published");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(state.retry).toHaveBeenCalled();
  });
});
