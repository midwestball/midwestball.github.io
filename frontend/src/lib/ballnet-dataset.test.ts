import { expect, it, vi } from "vitest";
import { createDatasetBaseResolver } from "./ballnet-dataset";

it("pins all Ballnet requests to the selected revision for a page load", async () => {
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ schemaVersion: 1, prefix: "migrations/ballnet-v2-20261029" })));
  const resolve = createDatasetBaseResolver("https://example.test/storage", fetcher);
  expect(await resolve()).toBe("https://example.test/storage/migrations/ballnet-v2-20261029");
  expect(await resolve()).toBe("https://example.test/storage/migrations/ballnet-v2-20261029");
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(fetcher).toHaveBeenCalledWith("https://example.test/storage/index/ballnet-dataset.json", { cache: "no-store" });
});

it("supports legacy installations and explicit rollback", async () => {
  const missing = createDatasetBaseResolver("https://example.test", vi.fn().mockResolvedValue(new Response(null, { status: 404 })));
  const rollback = createDatasetBaseResolver("https://example.test", vi.fn().mockResolvedValue(new Response(JSON.stringify({ schemaVersion: 1, prefix: "" }))));
  const missingSupabase = createDatasetBaseResolver("https://example.test", vi.fn().mockResolvedValue(new Response(JSON.stringify({ code: "NoSuchKey" }), { status: 400 })));
  expect(await missing()).toBe("https://example.test");
  expect(await rollback()).toBe("https://example.test");
  expect(await missingSupabase()).toBe("https://example.test");
});

it("fails closed for an unsafe pointer and retries after a transient failure", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ schemaVersion: 1, prefix: "../bad" }))).mockResolvedValueOnce(new Response(JSON.stringify({ schemaVersion: 1, prefix: "migrations/good" })));
  const resolve = createDatasetBaseResolver("https://example.test", fetcher);
  expect(await resolve()).toBeNull();
  expect(await resolve()).toBe("https://example.test/migrations/good");
});
