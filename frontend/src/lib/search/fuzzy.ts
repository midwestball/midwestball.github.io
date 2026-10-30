export type SearchCandidate = { id: string; name: string; team?: string; position?: string; opponent?: string };

export function normalizeSearchText(text: string): string {
  return text.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
    .replace(/['’`]/g, "").replace(/[^a-z0-9]+/g, " ").trim().replace(/\s+/g, " ");
}

/** Bounded Levenshtein; transpositions cost two edits. */
export function boundedDistance(a: string, b: string, limit: number): number | null {
  if (Math.abs(a.length - b.length) > limit) return null;
  let previous = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const current = [i];
    for (let j = 1; j <= b.length; j++) current[j] = Math.min(
      previous[j] + 1, current[j - 1] + 1, previous[j - 1] + Number(a[i - 1] !== b[j - 1]));
    if (Math.min(...current) > limit) return null;
    previous = current;
  }
  return previous[b.length] <= limit ? previous[b.length] : null;
}

export function matchCandidate(candidate: SearchCandidate, query: string): { score: number } | null {
  const q = normalizeSearchText(query);
  if (!q) return { score: 0 };
  const name = normalizeSearchText(candidate.name);
  if (name === q || name.replaceAll(" ", "") === q.replaceAll(" ", "")) return { score: 0 };
  if (name.startsWith(q)) return { score: 1 };
  const fields = [candidate.team, candidate.position, candidate.opponent].map(s => normalizeSearchText(s ?? ""));
  const words = name.split(" ");
  let score = 0;
  for (const token of q.split(" ")) {
    if (fields.includes(token)) { score += 2; continue; }
    if (words.some(w => w.startsWith(token))) { score += 2; continue; }
    if (words.some(w => w.includes(token))) { score += 3; continue; }
    const limit = token.length >= 7 ? 2 : token.length >= 4 ? 1 : 0;
    if (!limit || !words.some(w => boundedDistance(token, w, limit) !== null)) return null;
    score += 6;
  }
  return { score };
}

export const matchesSearch = (candidate: SearchCandidate, query: string) => matchCandidate(candidate, query) !== null;
export function rankCandidates<T extends SearchCandidate>(rows: readonly T[], query: string): T[] {
  return rows.map((row, index) => ({ row, index, match: matchCandidate(row, query) }))
    .filter(item => item.match !== null)
    .sort((a, b) => a.match!.score - b.match!.score || a.index - b.index).map(item => item.row);
}
