import type { HighlightRow } from "@/lib/payload";

/**
 * One primary row per player (highest zScore); nest the rest as `also`.
 * Safe on already-collapsed boards (flattens existing `also` then re-nests).
 */
export function collapseHighlightsByPlayer(
  rows: HighlightRow[],
): HighlightRow[] {
  if (rows.length === 0) return rows;

  const flat: HighlightRow[] = [];
  for (const row of rows) {
    const { also, rank: _rank, ...primary } = row;
    flat.push(primary as HighlightRow);
    for (const secondary of also ?? []) {
      const { also: _a, rank: _r, ...rest } = secondary;
      flat.push(rest as HighlightRow);
    }
  }

  flat.sort((a, b) => b.zScore - a.zScore);

  const byPlayer = new Map<string, HighlightRow[]>();
  const order: string[] = [];
  for (const row of flat) {
    const pid = row.playerId;
    if (!byPlayer.has(pid)) {
      byPlayer.set(pid, []);
      order.push(pid);
    }
    byPlayer.get(pid)!.push(row);
  }

  return order.map((pid, index) => {
    const group = byPlayer.get(pid)!;
    const head = group[0]!;
    const primary: HighlightRow = { ...head, rank: index + 1 };
    const alsoRows = group.slice(1).map((row) => {
      const { also: _a, rank: _r, ...rest } = row;
      return rest as HighlightRow;
    });
    if (alsoRows.length > 0) primary.also = alsoRows;
    else delete primary.also;
    return primary;
  });
}
