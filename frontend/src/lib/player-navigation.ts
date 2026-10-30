/** Stable Ballnet player IDs, never projection entity keys, select comparison columns. */
export function playerComparisonHref(playerId: string, season?: number): string {
  const params = new URLSearchParams({ p: playerId });
  if (season !== undefined && Number.isInteger(season)) params.set("season", String(season));
  return `/search/?${params}`;
}

/** Translate either legacy player URL form while retaining unrelated query fields. */
export function legacyPlayerComparisonHref(params: URLSearchParams, pathId?: string): string {
  const next = new URLSearchParams(params);
  const id = pathId ?? next.get("id");
  next.delete("id");
  if (id) next.set("p", id); else next.delete("p");
  return `/search/${next.size ? `?${next}` : ""}`;
}
