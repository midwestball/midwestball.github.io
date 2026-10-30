import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ShareLinkButton } from "./ShareLinkButton";
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it("reports a successful copy locally", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  vi.stubGlobal("navigator", { clipboard: { writeText } });
  render(<ShareLinkButton getHref={() => "https://example.test/trades/?v=1"} />);
  fireEvent.click(screen.getByRole("button"));
  await waitFor(() => expect(screen.getByRole("status").textContent).toBe("Link copied"));
  expect(writeText).toHaveBeenCalledWith("https://example.test/trades/?v=1");
});
it("exposes an intact long URL and scenario text when clipboard is unavailable", async () => {
  vi.stubGlobal("navigator", {});
  const href = `https://example.test/trades/?v=1&r=${"a".repeat(1900)}`;
  render(<ShareLinkButton getHref={() => href} exportText='{"roster":[]}' />);
  fireEvent.click(screen.getByRole("button"));
  await waitFor(() => expect((screen.getByLabelText("Shareable URL") as HTMLInputElement).value).toBe(href));
  expect(screen.getByText(/No players were removed/)).toBeTruthy();
  expect((screen.getByLabelText("Scenario JSON") as HTMLTextAreaElement).value).toBe('{"roster":[]}');
});
