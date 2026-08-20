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
      <span className="text-sm text-zinc-600">Season</span>
      <select
        value={season}
        onChange={(event) => {
          router.push(`/players/${playerId}?season=${event.target.value}`);
        }}
        className="h-8 rounded-none border border-zinc-200 bg-white px-2 text-sm text-zinc-900 outline-none focus:border-zinc-400"
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
