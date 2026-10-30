"use client";
import type { useLeaderboardDiscovery } from "./useLeaderboardDiscovery";
import { FILTER_OPTIONS, FANTASY_RANK_BOARD_GROUPS, FANTASY_RANK_STAT_ID, type SearchPositionFilter } from "@/lib/search/leaderboards";
const controlBase = "h-9 border border-zinc-200 bg-white px-2 text-sm outline-none rounded-none";
const controlEnabled = `${controlBase} text-zinc-900 focus:border-zinc-400`;
const controlDisabled = `${controlBase} cursor-not-allowed border-zinc-100 bg-zinc-50 text-zinc-400`;
export function PlayerLeaderboardFilters({ model, children }: { model: ReturnType<typeof useLeaderboardDiscovery>; children?: React.ReactNode }) {
  const { query, setQuery, season, setSeason, seasonOptions, group, onSelectGroup, statId, onSelectStat, statEnabled, sortEnabled, boardGroup, statOptions, sortMode, setSortMode, volumeInteractive, volumeVisible, hasVolumeData, boardStatus, volumeMax, floor, volumeLabel, sliderMax, sliderValue, setVolume, volumeDraft, setVolumeChoice, volumeKey, clampVolume, minVolume, commitVolumeDraft } = model;
  return <>      <div className="flex items-center gap-1.5">
        {children ?? (
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search players, positions, teams"
          className="h-9 min-w-0 flex-1 rounded-none border border-zinc-200 bg-white px-2 text-sm text-zinc-900 outline-none placeholder:text-zinc-400 focus:border-zinc-400"
        />
        )}
        <select
          value={season}
          onChange={(event) => { setSeason(Number(event.target.value)); }}
          aria-label="Season"
          className={`${controlEnabled} shrink-0`}
        >
          {seasonOptions.map((row) => (
            <option key={row.season} value={row.season}>
              {row.season}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-wrap items-center gap-x-1.5 gap-y-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="shrink-0 text-xs font-semibold tracking-[0.15em] text-zinc-500 uppercase">
            Filter
          </span>
          <select
            value={group ?? ""}
            onChange={(event) =>
              onSelectGroup(event.target.value as SearchPositionFilter | "")
            }
            aria-label="Position"
            className={controlEnabled}
          >
            <option value="">Position</option>
            {FILTER_OPTIONS.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.label}
              </option>
            ))}
          </select>
          <select
            value={statId ?? ""}
            onChange={(event) => onSelectStat(event.target.value)}
            aria-label="Stat"
            disabled={!statEnabled}
            className={`min-w-0 max-w-[9rem] truncate ${statEnabled ? controlEnabled : controlDisabled}`}
          >
            <option value="">Stat</option>
            {boardGroup && FANTASY_RANK_BOARD_GROUPS.includes(boardGroup) ? (
              <option value={FANTASY_RANK_STAT_ID}>Fantasy Rank</option>
            ) : null}
            {statOptions.map((stat) => (
              <option key={stat.id} value={stat.id}>
                {stat.label}
              </option>
            ))}
          </select>
          <div className="flex shrink-0">
            <button
              type="button"
              disabled={!sortEnabled}
              onClick={() => setSortMode("best")}
              className={`h-9 border px-2 text-sm rounded-none ${
                !sortEnabled
                  ? "cursor-not-allowed border-zinc-100 bg-zinc-50 text-zinc-400"
                  : sortMode === "best"
                    ? "border-zinc-900 bg-zinc-900 text-white"
                    : "border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50"
              }`}
            >
              Best
            </button>
            <button
              type="button"
              disabled={!sortEnabled}
              onClick={() => setSortMode("worst")}
              className={`h-9 border border-l-0 px-2 text-sm rounded-none ${
                !sortEnabled
                  ? "cursor-not-allowed border-zinc-100 bg-zinc-50 text-zinc-400"
                  : sortMode === "worst"
                    ? "border-zinc-900 bg-zinc-900 text-white"
                    : "border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50"
              }`}
            >
              Worst
            </button>
          </div>
        </div>

        <div
          className={`flex min-w-0 grow basis-[12rem] items-center gap-1 ${
            volumeInteractive ? "" : "opacity-40"
          }`}
          title={
            !volumeVisible
              ? undefined
              : !hasVolumeData && boardStatus === "ready"
                ? "Volume not available for this stat"
                : volumeMax <= 0
                  ? "No volume data for this stat yet"
                  : `Min ${volumeLabel} (default ${floor}; 0–${Math.round(volumeMax)})`
          }
        >
          <label
            htmlFor="min-volume"
            className="shrink-0 text-xs text-zinc-500 whitespace-nowrap"
          >
            Min Volume
          </label>
          <input
            id="min-volume"
            type="range"
            min={0}
            max={sliderMax}
            step={1}
            value={volumeVisible ? sliderValue : 0}
            disabled={!volumeInteractive}
            onChange={(event) => setVolume(Number(event.target.value))}
            className="h-9 min-w-0 flex-1 cursor-pointer accent-zinc-900 disabled:cursor-not-allowed"
            aria-label={`Minimum ${volumeLabel}`}
          />
          <input
            type="number"
            inputMode="numeric"
            min={0}
            max={sliderMax}
            step={1}
            value={volumeVisible ? volumeDraft : ""}
            disabled={!volumeInteractive}
            onChange={(event) => {
              const raw = event.target.value;
              const parsed = Number(raw);
              setVolumeChoice({key: volumeKey, value: raw.trim() !== "" && Number.isFinite(parsed) ? clampVolume(parsed) : minVolume, draft: raw});
            }}
            onBlur={commitVolumeDraft}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.currentTarget.blur();
              }
            }}
            className={`h-9 w-11 shrink-0 rounded-none border px-0.5 text-right text-sm tabular-nums outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none ${
              volumeInteractive
                ? "border-zinc-200 bg-white text-zinc-900 focus:border-zinc-400"
                : "cursor-not-allowed border-zinc-100 bg-zinc-50 text-zinc-400"
            }`}
            aria-label={`Minimum ${volumeLabel} value`}
          />
        </div>
      </div>

</>;
}
