import { finiteParam, parseIdList } from "./common";
export function decodeProjection(params: URLSearchParams, available: ReadonlySet<string>, grid?: readonly number[]) {
  const requested = parseIdList(params.get("p"));
  const selected = requested.filter(id => available.has(id));
  const focus = params.get("focus");
  const points = finiteParam(params.get("points"));
  return { selected, focus: focus && selected.includes(focus) ? focus : selected[0] ?? null,
    stale: requested.length - selected.length,
    points: points === null ? null : grid?.length ? Math.min(Math.max(points, grid[0]), grid[grid.length - 1]) : points };
}
