"use client";
import type { useLeaderboardDiscovery } from "./useLeaderboardDiscovery";

const controlEnabled = "h-9 border border-border bg-card px-2 text-sm outline-none rounded-none text-foreground focus:border-ring";

export function PlayerSearchControls({ model, children }: {
  model: ReturnType<typeof useLeaderboardDiscovery>;
  children?: React.ReactNode;
}) {
  const { query, setQuery, season, setSeason, seasonOptions } = model;
  return (
    <div className="flex items-start gap-1.5">
      {children ?? (
        <input
          type="search"
          value={query}
          onChange={event => setQuery(event.target.value)}
          placeholder="Search players, positions, teams"
          className="h-9 min-w-0 flex-1 rounded-none border border-border bg-card px-2 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-ring"
        />
      )}
      <select
        value={season}
        onChange={event => setSeason(Number(event.target.value))}
        aria-label="Season"
        className={`${controlEnabled} shrink-0 ${children ? "mt-5" : ""}`}
      >
        {seasonOptions.map(row => <option key={row.season} value={row.season}>{row.season}</option>)}
      </select>
    </div>
  );
}
