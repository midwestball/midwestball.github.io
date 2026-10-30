"use client";

import { useRouter } from "next/navigation";

export function SeasonSelect({
  playerId,
  season,
  seasons,
}: {
  playerId: string;
  season: number;
  seasons: number[];
}) {
  const router = useRouter();

  return (
    <label className="flex items-center justify-between gap-4">
      <span className="text-sm text-text-secondary">Season</span>
      <select
        value={season}
        onChange={(event) => {
          router.push(playerId.startsWith("demo-")
            ? `/players/${encodeURIComponent(playerId)}/?season=${event.target.value}`
            : `/players/?id=${encodeURIComponent(playerId)}&season=${event.target.value}`);
        }}
        className="h-8 rounded-none border border-border bg-card px-2 text-sm text-foreground outline-none focus:border-ring"
      >
        {seasons.map((year) => (
          <option key={year} value={year}>
            {year}
          </option>
        ))}
      </select>
    </label>
  );
}
