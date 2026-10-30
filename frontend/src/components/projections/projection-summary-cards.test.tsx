import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProjectionSummaryCards } from "./ProjectionSummaryCards";
import type { ProjectionEntitySummary } from "@/lib/projections";
import { teamPrimaryColor, teamSecondaryColor } from "@/lib/team-colors";

afterEach(cleanup);

const entity = (over: Partial<ProjectionEntitySummary> = {}): ProjectionEntitySummary => ({
  entityKey: "chi-qb-1",
  entityType: "player",
  playerId: "p-1",
  name: "Example QB",
  position: "QB",
  team: "CHI",
  opponent: "GB",
  expectedPoints: 20.4,
  path: "entities/chi-qb-1.json",
  ...over,
});

/** The TeamAbbr swatch carries the primary/secondary gradient on an inline style. */
function swatchStyles(): string[] {
  return Array.from(document.querySelectorAll<HTMLElement>("span[style]"))
    .map((el) => el.getAttribute("style") ?? "")
    .filter((style) => style.includes("linear-gradient"));
}

describe("ProjectionSummaryCards", () => {
  it("links the player name using the stable player ID while keeping projection focus separate", () => {
    const onFocus = vi.fn();
    render(<ProjectionSummaryCards entities={[entity()]} season={2025} focus={null} onFocus={onFocus} onRemove={() => {}} />);
    const link = screen.getByRole("link", { name: "Example QB" });
    const url = new URL(link.getAttribute("href")!, "https://example.test");
    expect(url.pathname.replace(/\/$/, "")).toBe("/search");
    expect(url.searchParams.get("p")).toBe("p-1");
    expect(url.searchParams.get("season")).toBe("2025");
    expect(link.closest("button")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Focus projection for Example QB" }));
    expect(onFocus).toHaveBeenCalledWith("chi-qb-1");
  });
  it("does not invent a player link for a defense entity", () => {
    render(<ProjectionSummaryCards entities={[entity({ playerId: null, entityType: "defense", position: "DST" })]} focus={null} onFocus={() => {}} onRemove={() => {}} />);
    expect(screen.queryByRole("link")).toBeNull();
  });
  it("renders the team color swatch next to the player name", () => {
    render(
      <ProjectionSummaryCards
        entities={[entity()]}
        focus={null}
        onFocus={() => {}}
        onRemove={() => {}}
      />,
    );
    const styles = swatchStyles();
    const expected = teamPrimaryColor("CHI");
    const expectedSecondary = teamSecondaryColor("CHI");
    expect(styles.length).toBeGreaterThan(0);
    expect(
      styles.some(
        (style) => style.includes(expected) && style.includes(expectedSecondary),
      ),
    ).toBe(true);
    // The swatch sits inside the card, before the "QB · CHI vs GB" detail line.
    const detail = screen.getByText(/QB · CHI vs GB/);
    const swatch = document.querySelector<HTMLElement>("span[style*='linear-gradient']");
    expect(swatch).not.toBeNull();
    expect(
      swatch!.compareDocumentPosition(detail) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("exposes a Remove button labelled with the player name", () => {
    render(
      <ProjectionSummaryCards
        entities={[entity()]}
        focus={null}
        onFocus={() => {}}
        onRemove={() => {}}
      />,
    );
    const remove = screen.getByRole("button", { name: "Remove Example QB" });
    expect(remove.tagName).toBe("BUTTON");
    expect(remove.textContent).toBe("Remove");
  });

  it("gives the Remove button a hover and focus highlight", () => {
    render(
      <ProjectionSummaryCards
        entities={[entity()]}
        focus={null}
        onFocus={() => {}}
        onRemove={() => {}}
      />,
    );
    const className = screen
      .getByRole("button", { name: "Remove Example QB" })
      .getAttribute("class") ?? "";
    const classes = className.split(/\s+/);
    expect(classes).toContain("border");
    expect(classes.some((c) => c.startsWith("hover:bg-"))).toBe(true);
    expect(classes.some((c) => c.startsWith("hover:text-"))).toBe(true);
    expect(classes.some((c) => c.startsWith("focus:bg-"))).toBe(true);
    // Keyboard focus keeps a visible ring.
    expect(classes.some((c) => c.startsWith("focus:outline"))).toBe(true);
  });

  it("calls onRemove with the entity key when Remove is clicked", () => {
    const onRemove = vi.fn();
    render(
      <ProjectionSummaryCards
        entities={[entity(), entity({ entityKey: "gb-wr-2", name: "Second WR", position: "WR", team: "GB" })]}
        focus={null}
        onFocus={() => {}}
        onRemove={onRemove}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Remove Second WR" }));
    expect(onRemove).toHaveBeenCalledTimes(1);
    expect(onRemove).toHaveBeenCalledWith("gb-wr-2");
  });
});
