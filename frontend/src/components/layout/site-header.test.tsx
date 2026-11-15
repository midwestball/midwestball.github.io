import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SiteHeader } from "./SiteHeader";

afterEach(cleanup);

describe("site header", () => {
  it("keeps the league lab off the navigation bar", () => {
    render(<SiteHeader />);
    const hrefs = screen.getAllByRole("link").map((link) => link.getAttribute("href"));
    expect(hrefs).toEqual(["/", "/", "/search", "/ballnet", "/trades"]);
    expect(screen.queryByRole("link", { name: "League" })).toBeNull();
  });
});
