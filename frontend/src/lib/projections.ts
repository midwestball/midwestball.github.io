import { vizStorageBase } from "@/lib/viz-config";

export const PROJECTION_POSITIONS = ["QB", "RB", "WR", "TE", "K", "DST"] as const;
export type ProjectionPosition = (typeof PROJECTION_POSITIONS)[number];
export type PositionModelStatus = "promoted" | "promoted_with_calibration_note" | "initial_deployment";
export type ProjectionPointer = { schemaVersion: 1; season: number; week: number; snapshotId: string; indexPath: string; manifestPath: string; generatedAt: string };
export type ProjectionEntitySummary = { entityKey: string; entityType: "player" | "defense"; playerId: string | null; name: string; position: ProjectionPosition; team: string; opponent: string; expectedPoints: number; path: string; availability?: string };
export type ProjectionIndex = { schemaVersion: 1; season: number; week: number; snapshotId: string; generatedAt: string; trainedThrough: { season: number; week: number }; modelFamily: string; modelVersion: string; scoringProfile: string; scoringDescriptions: Record<ProjectionPosition, string>; positionModelStatus: Record<ProjectionPosition, PositionModelStatus>; manifestPath: string; xGrid: number[]; entities: ProjectionEntitySummary[] };
export type ProjectionEntityDistribution = { schemaVersion: 1; snapshotId: string; entityKey: string; expectedPoints: number; yMax: number; pdf: number[]; cdf: number[]; lowerBound: number | null; bandwidth: number; nModelDraws: number };
export type ProjectionManifest = { schemaVersion: 1; snapshotId: string; [key: string]: unknown };

const object = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const text = (v: unknown): v is string => typeof v === "string" && v.length > 0;
const finiteArray = (v: unknown): v is number[] => Array.isArray(v) && v.every(finite);
const position = (v: unknown): v is ProjectionPosition => typeof v === "string" && (PROJECTION_POSITIONS as readonly string[]).includes(v);
const safeRelativePath = (v: unknown) => text(v) && !v.startsWith("/") && !v.includes("\\") && !v.split("/").some((part) => part === ".." || part === "." || part === "");

export function isProjectionPointer(v: unknown, prefix = "projections"): v is ProjectionPointer {
  if (!object(v) || v.schemaVersion !== 1 || !finite(v.season) || !finite(v.week) || !text(v.snapshotId) || !safeRelativePath(v.indexPath) || !safeRelativePath(v.manifestPath) || !text(v.generatedAt)) return false;
  if (!/^[a-z0-9-]+$/.test(prefix)) return false;
  const base = `${prefix}/${v.season}/w${v.week}/${v.snapshotId}`;
  return v.indexPath === `${base}/index.json` && v.manifestPath === `${base}/manifest.json`;
}
export function isProjectionEntity(v: unknown): v is ProjectionEntityDistribution { return object(v) && v.schemaVersion === 1 && text(v.snapshotId) && text(v.entityKey) && finite(v.expectedPoints) && finite(v.yMax) && finiteArray(v.pdf) && finiteArray(v.cdf) && (v.lowerBound === null || finite(v.lowerBound)) && finite(v.bandwidth) && v.bandwidth > 0 && finite(v.nModelDraws) && v.nModelDraws > 0 && v.pdf.length === v.cdf.length && v.pdf.length >= 2 && v.pdf.every((x) => x >= 0) && v.cdf.every((x, i, a) => x >= 0 && x <= 1 && (i === 0 || x >= a[i - 1]!)); }
export function isProjectionIndex(v: unknown): v is ProjectionIndex {
  if (!object(v) || v.schemaVersion !== 1 || !finite(v.season) || !finite(v.week) || !text(v.snapshotId) || !text(v.generatedAt) || !object(v.trainedThrough) || !finite(v.trainedThrough.season) || !finite(v.trainedThrough.week) || !text(v.modelFamily) || !text(v.modelVersion) || !text(v.scoringProfile) || !object(v.scoringDescriptions) || !object(v.positionModelStatus) || !safeRelativePath(v.manifestPath) || !finiteArray(v.xGrid) || v.xGrid.length < 2 || !v.xGrid.every((x,i,a)=>i===0 || x>a[i-1]!) || !Array.isArray(v.entities)) return false;
  for (const p of PROJECTION_POSITIONS) if (!text(v.scoringDescriptions[p]) || !text(v.positionModelStatus[p])) return false;
  const keys = new Set<string>();
  return v.entities.every((e) => object(e) && text(e.entityKey) && !keys.has(e.entityKey) && !!keys.add(e.entityKey) && (e.entityType === "player" || e.entityType === "defense") && (e.playerId === null || text(e.playerId)) && text(e.name) && position(e.position) && text(e.team) && text(e.opponent) && finite(e.expectedPoints) && safeRelativePath(e.path));
}

export class ProjectionLoadError extends Error { constructor(public kind: "unavailable" | "network" | "invalid", message: string) { super(message); } }
const immutableCache = new Map<string, Promise<unknown>>();
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
/** A single connection hiccup must not replace the page with an error screen. */
export const NETWORK_ATTEMPTS = 3;
const NETWORK_BACKOFF_MS = [250, 750];
/** Guards a shared immutable request so a hung response is not cached forever. */
const SHARED_TIMEOUT_MS = 15000;

function abortError(): Error {
  const err = new Error("The request was aborted.");
  err.name = "AbortError";
  return err;
}
function isAbort(cause: unknown): boolean {
  return cause instanceof Error && cause.name === "AbortError";
}
function readTimeout(ms: number, url: string): Promise<never> {
  return new Promise((_, reject) => setTimeout(() => reject(new ProjectionLoadError("network", `Projection request timed out for ${url}.`)), ms));
}

/** One HTTP round trip, with transport failures normalised to ProjectionLoadError. */
async function requestOnce(url: string, signal?: AbortSignal | null): Promise<Response> {
  let response: Response;
  try { response = await fetch(url, signal ? { signal } : undefined); }
  catch (cause) {
    if (isAbort(cause) || signal?.aborted) throw cause;
    throw new ProjectionLoadError("network", "Could not reach projection storage.");
  }
  if (response.status === 404) throw new ProjectionLoadError("unavailable", "No projection snapshot is published.");
  if (!response.ok) throw new ProjectionLoadError("network", `Projection request failed (${response.status}).`);
  return response;
}

async function parseBody(response: Response): Promise<unknown> {
  try { return await response.json(); }
  catch (cause) {
    // Aborting mid-body rejects json(). Reporting that as invalid JSON turned a
    // routine teardown into a red "Projection JSON is invalid." banner.
    if (isAbort(cause)) throw cause;
    throw new ProjectionLoadError("invalid", "Projection JSON is invalid.");
  }
}

/** A truncated or transient body is worth one more try; a bad contract is not. */
function isRetriable(error: unknown, attempt: number): boolean {
  if (!(error instanceof ProjectionLoadError) || attempt + 1 >= NETWORK_ATTEMPTS) return false;
  return error.kind === "network" || error.kind === "invalid";
}

/**
 * An immutable revision object is shared by every caller through `immutableCache`,
 * so its request must NOT be bound to any one caller's AbortSignal. Binding it is
 * what produced the intermittent red banner: React tears down the effect that
 * started a fetch and immediately starts another for the new selection, the second
 * caller reuses the first caller's doomed promise from the cache, and the abort
 * belonging to a dead effect surfaced as a live error. Callers instead race their
 * own signal against this shared, signal-free request.
 */
async function sharedJson(url: string): Promise<unknown> {
  for (let attempt = 0; ; attempt++) {
    try {
      // The shared request carries no caller signal, so it can only be torn down by a
      // browser-level event. It races a timeout instead, which is purgeable.
      const response = await Promise.race([requestOnce(url), readTimeout(SHARED_TIMEOUT_MS, url)]);
      return await parseBody(response);
    } catch (error) {
      if (isAbort(error)) throw error;
      if (!isRetriable(error, attempt)) throw error;
      await sleep(NETWORK_BACKOFF_MS[attempt] ?? 1500);
    }
  }
}

/** Let a caller walk away from a shared request without disturbing the other callers. */
function raceAbort(shared: Promise<unknown>, signal?: AbortSignal | null): Promise<unknown> {
  if (!signal) return shared;
  if (signal.aborted) return Promise.reject(abortError());
  return new Promise<unknown>((resolve, reject) => {
    const onAbort = () => reject(abortError());
    signal.addEventListener("abort", onAbort, { once: true });
    shared.then(
      (value) => { signal.removeEventListener("abort", onAbort); resolve(value); },
      (error) => { signal.removeEventListener("abort", onAbort); reject(error); },
    );
  });
}

async function json(url: string, init?: RequestInit, cache = false): Promise<unknown> {
  if (cache) {
    let shared = immutableCache.get(url);
    if (!shared) {
      shared = sharedJson(url);
      immutableCache.set(url, shared);
      // Never let a failed shared request linger in the cache.
      void shared.catch(() => { if (immutableCache.get(url) === shared) immutableCache.delete(url); });
    }
    return raceAbort(shared, init?.signal);
  }
  // Uncached (the pointer is always revalidated) stays bound to its caller.
  for (let attempt = 0; ; attempt++) {
    try {
      return await parseBody(await requestOnce(url, init?.signal));
    } catch (error) {
      if (isAbort(error) || init?.signal?.aborted) throw error;
      if (!isRetriable(error, attempt)) throw error;
      await sleep(NETWORK_BACKOFF_MS[attempt] ?? 1500);
    }
  }
}
function storageUrl(path: string) { const base = vizStorageBase(); if (!base) throw new ProjectionLoadError("unavailable", "Projection storage is not configured."); return `${base.replace(/\/$/, "")}/${path}`; }
function resolveRevisionPath(indexPath: string, child: string) { if (!safeRelativePath(child)) throw new ProjectionLoadError("invalid", "Snapshot contains an unsafe object path."); const slash = indexPath.lastIndexOf("/"); const full = `${indexPath.slice(0, slash + 1)}${child}`; if (!safeRelativePath(full)) throw new ProjectionLoadError("invalid", "Snapshot contains an unsafe object path."); return full; }
export async function loadProjectionSnapshot(signal?: AbortSignal): Promise<{ pointer: ProjectionPointer; index: ProjectionIndex }> { const prefix = process.env.NEXT_PUBLIC_PROJECTION_PREFIX?.trim() || "projections"; const rawPointer = await json(storageUrl(`${prefix}/current.json`), { cache: "no-store", signal }); if (!isProjectionPointer(rawPointer, prefix)) throw new ProjectionLoadError("invalid", "The projection pointer failed validation."); const rawIndex = await json(storageUrl(rawPointer.indexPath), { signal }, true); if (!isProjectionIndex(rawIndex) || rawIndex.snapshotId !== rawPointer.snapshotId) throw new ProjectionLoadError("invalid", "The projection index failed validation."); return { pointer: rawPointer, index: rawIndex }; }
export async function loadProjectionEntity(indexPath: string, index: ProjectionIndex, summary: ProjectionEntitySummary, signal?: AbortSignal): Promise<ProjectionEntityDistribution> { const raw = await json(storageUrl(resolveRevisionPath(indexPath, summary.path)), { signal }, true); if (!isProjectionEntity(raw) || raw.snapshotId !== index.snapshotId || raw.entityKey !== summary.entityKey || raw.pdf.length !== index.xGrid.length || raw.expectedPoints !== summary.expectedPoints) throw new ProjectionLoadError("invalid", `Distribution for ${summary.name} failed validation.`); return raw; }
export async function loadProjectionManifest(indexPath: string, index: ProjectionIndex): Promise<ProjectionManifest> { const raw = await json(storageUrl(resolveRevisionPath(indexPath, index.manifestPath)), undefined, true); if (!object(raw) || raw.schemaVersion !== 1 || raw.snapshotId !== index.snapshotId) throw new ProjectionLoadError("invalid", "Projection manifest failed validation."); return raw as ProjectionManifest; }
export function parseProjectionSelection(search: string, available: Set<string>) { const params = new URLSearchParams(search); const requested = (params.get("p") ?? "").split(",").filter(Boolean); const unique = [...new Set(requested)].slice(0, 4); const selected = unique.filter((id) => available.has(id)); const requestedFocus = params.get("focus"); return { selected, focus: requestedFocus && selected.includes(requestedFocus) ? requestedFocus : selected[0] ?? null, stale: unique.length - selected.length }; }
