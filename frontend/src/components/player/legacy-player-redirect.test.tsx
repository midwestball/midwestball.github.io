import React from "react";
import { cleanup, render } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import PlayersPage from "@/app/players/page";
import LegacyPlayerPage from "@/app/players/[id]/page";
const { replace, router } = vi.hoisted(() => {
  const replace = vi.fn(); return { replace, router: { replace } };
});
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(location.search), useRouter: () => router }));
afterEach(() => { cleanup(); vi.clearAllMocks(); history.replaceState(null, "", "/"); });
it("replaces a runtime player URL with a preselected comparison while preserving season and hash", () => {
  history.replaceState(null, "", "/players/?id=new-player&season=2025&utm=kept#stat");
  render(<PlayersPage />);
  expect(replace).toHaveBeenCalledWith("/search/?season=2025&utm=kept&p=new-player#stat", { scroll: false });
});
it("replaces static player routes with the same selected comparison", async () => {
  history.replaceState(null, "", "/players/athlete/?season=2024");
  render(await LegacyPlayerPage({ params: Promise.resolve({ id: "athlete" }) }));
  expect(replace).toHaveBeenCalledWith("/search/?season=2024&p=athlete", { scroll: false });
});
it("opens Search when a legacy link has no player", () => {
  render(<PlayersPage />);
  expect(replace).toHaveBeenCalledWith("/search/", { scroll: false });
});
