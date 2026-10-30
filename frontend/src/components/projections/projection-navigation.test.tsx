import React from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ProjectionsPageClient } from "./ProjectionsPageClient";
import type { ProjectionEntitySummary } from "@/lib/projections";
import { loadProjectionSnapshot } from "@/lib/projections";
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(location.search) }));
vi.mock("./ProjectionOverlayChart", () => ({ THRESHOLD_COLOR: "#555555", ProjectionOverlayChart: () => <div>Projection chart</div> }));
vi.mock("@/lib/projections", async importOriginal => ({
  ...await importOriginal<typeof import("@/lib/projections")>(),
  loadProjectionSnapshot: vi.fn(async () => ({ pointer: { indexPath: "test/index.json" }, index: {
    season: 2026, week: 8, generatedAt: "2026-10-29T12:00:00Z", xGrid: [0, 10, 20], scoringProfile: "PPR", scoringDescriptions: {}, positionModelStatus: {},
    entities: ["a", "b"].map(key => ({ entityKey: key, playerId: `player-${key}`, name: `Player ${key}`, position: "QB", team: "CHI", opponent: "GB", expectedPoints: 10 })),
  } })),
  loadProjectionEntity: vi.fn(async (_path: string, _index: unknown, summary: ProjectionEntitySummary) => ({ entityKey: summary.entityKey, pdf: [0, 1, 0], cdf: [0, .5, 1], lowerBound: null })),
}));
afterEach(() => { cleanup(); history.replaceState(null, "", "/"); vi.clearAllMocks(); });
it("hydrates entity keys and points, restores history, and never reloads metadata for selection edits", async () => {
  history.replaceState(null, "", "/ballnet/?p=a&focus=a&points=12.5&utm=kept");
  render(<ProjectionsPageClient />);
  await waitFor(() => expect(screen.getByLabelText("Fantasy points threshold")).toBeTruthy());
  expect((screen.getByLabelText("Fantasy points threshold") as HTMLInputElement).value).toBe("12.5");
  fireEvent.focus(screen.getByLabelText("Add a projection"));
  fireEvent.click(screen.getByRole("option", { name: /Player b/ }));
  expect(new URLSearchParams(location.search).get("p")).toBe("a,b");
  expect(new URLSearchParams(location.search).get("utm")).toBe("kept");
  act(() => { history.replaceState(null, "", "/ballnet/?p=b&focus=b&points=8"); window.dispatchEvent(new PopStateEvent("popstate")); });
  await waitFor(() => expect((screen.getByLabelText("Fantasy points threshold") as HTMLInputElement).value).toBe("8.0"));
  expect(screen.queryByRole("button", { name: "Remove Player a" })).toBeNull();
  expect(loadProjectionSnapshot).toHaveBeenCalledTimes(1);
});
