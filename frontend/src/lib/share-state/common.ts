export function parseIdList(raw: string | null, max = 4): string[] {
  return [...new Set((raw ?? "").split(",").map(s => s.trim()).filter(Boolean))].slice(0, max);
}
export function patchQuery(current: Pick<URLSearchParams, "toString">, updates: Record<string, string | null>): URLSearchParams {
  const next = new URLSearchParams(current.toString());
  for (const [key, value] of Object.entries(updates)) {
    if (value === null || value === "") next.delete(key); else next.set(key, value);
  }
  return next;
}
export function finiteParam(raw: string | null): number | null {
  return raw !== null && raw.trim() !== "" && Number.isFinite(Number(raw)) ? Number(raw) : null;
}
