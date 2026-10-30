import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { PlayerCombobox } from "./PlayerCombobox";
afterEach(cleanup);
it("opens on focus, navigates, picks, collapses, and reopens", () => {
  const pick = vi.fn();
  render(<PlayerCombobox label="Player" items={[{ key: "a", primary: "Alpha", secondary: "WR" }, { key: "b", primary: "Beta", secondary: "TE" }]} onPick={pick} />);
  const input = screen.getByRole("combobox");
  fireEvent.focus(input); fireEvent.keyDown(input, { key: "ArrowDown" });
  expect(document.getElementById(input.getAttribute("aria-activedescendant")!)?.textContent).toContain("Beta");
  fireEvent.keyDown(input, { key: "Enter" }); expect(pick).toHaveBeenCalledWith("b");
  expect(screen.queryByRole("listbox")).toBeNull();
  fireEvent.focus(input); fireEvent.keyDown(input, { key: "Escape" });
  fireEvent.keyDown(input, { key: "Enter" }); expect(pick).toHaveBeenCalledTimes(1);
});
it("hides suggestions and prevents picks when disabled", () => {
  const pick = vi.fn(); render(<PlayerCombobox label="Player" items={[{ key: "a", primary: "Alpha", secondary: "" }]} onPick={pick} disabled showWhenEmpty />);
  expect(screen.queryByRole("listbox")).toBeNull(); fireEvent.keyDown(screen.getByRole("combobox"), { key: "Enter" }); expect(pick).not.toHaveBeenCalled();
});
