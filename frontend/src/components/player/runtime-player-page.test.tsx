import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams("id=new-player") }));
vi.mock("@/lib/ballnet-store", () => ({
  fetchPlayersIndex: async () => ({ players: [{ id: "new-player", name: "New Player", position: "WR", team: "T", seasons: [2026] }] }),
  fetchCurrentMeta: async () => ({ season: 2026 }),
}));
vi.mock("./PlayerPageClient", () => ({ PlayerPageClient: ({ player }: { player: { name: string } }) => <div>{player.name}</div> }));
import { RuntimePlayerPage } from "./RuntimePlayerPage";

afterEach(cleanup);

it("loads a player from the live index without a pre-generated player route", async () => {
  render(<RuntimePlayerPage />);
  expect(await screen.findByText("New Player")).toBeTruthy();
});
