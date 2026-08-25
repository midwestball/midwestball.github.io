import Link from "next/link";
import type { HighlightRow } from "@/lib/payload";
import { STATS_BY_GROUP, type PositionGroup } from "@/lib/catalog";
import { formatStatValue } from "@/lib/catalog/format";

function formatHighlightValue(row: HighlightRow): string {
  const group = row.positionGroup as PositionGroup;
  const def = STATS_BY_GROUP[group]?.find((s) => s.id === row.statId);
  if (def) return formatStatValue(def.format, row.value);
  if (Number.isInteger(row.value)) return String(row.value);
  return row.value.toFixed(1);
}

function formatZ(z: number): string {
  const sign = z >= 0 ? "+" : "";
  return `${sign}${z.toFixed(2)}σ`;
}

type HighlightListProps = {
  rows: HighlightRow[];
  season: number;
  emptyLabel?: string;
};

export function HighlightList({
  rows,
  season,
  emptyLabel = "No highlights published for this week yet.",
}: HighlightListProps) {
  if (rows.length === 0) {
    return <p className="text-sm text-zinc-500">{emptyLabel}</p>;
  }

  return (
    <ul className="space-y-1">
      {rows.map((row) => (
        <li key={`${row.rank}-${row.playerId}-${row.statId}`}>
          <Link
            href={`/players/${row.playerId}?season=${season}`}
            className="flex items-center justify-between gap-3 rounded-none border border-zinc-200 bg-white px-3 py-2 hover:bg-zinc-50"
          >
            <div className="min-w-0">
              <p className="font-medium text-zinc-900">
                <span className="mr-2 text-xs tabular-nums text-zinc-400">
                  {row.rank}
                </span>
                {row.name}
              </p>
              <p className="truncate text-sm text-zinc-500">
                {row.position} · {row.team}
                {row.opponent ? ` vs ${row.opponent}` : ""} · {row.statLabel}
              </p>
            </div>
            <div className="shrink-0 text-right">
              <p className="text-sm font-semibold tabular-nums text-zinc-900">
                {formatHighlightValue(row)}
              </p>
              <p className="text-xs tabular-nums text-zinc-400">
                {formatZ(row.zScore)}
              </p>
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}
