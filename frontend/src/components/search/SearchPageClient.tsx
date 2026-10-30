"use client";
import { useMemo } from "react";
import { useBrowserQuery, writeBrowserQuery } from "@/components/share/browser-query";
import { isPositionCode, positionGroupOf } from "@/lib/catalog";
import { parseIdList, patchQuery } from "@/lib/share-state/common";
import { searchPlayers } from "@/lib/player-index";
import { CompareBoard } from "@/components/compare/CompareBoard";
import { useCompareSelection } from "@/components/compare/useCompareSelection";
import { useLeaderboardDiscovery } from "./useLeaderboardDiscovery";
import { PlayerLeaderboardFilters } from "./PlayerLeaderboardFilters";
import { PlayerDiscoveryResults } from "./PlayerDiscoveryResults";
import { PlayerCombobox } from "./PlayerCombobox";
export function SearchPageClient(props: Parameters<typeof useLeaderboardDiscovery>[0]) {
  const raw = useBrowserQuery();
  const params = new URLSearchParams(raw);
  function navigate(updates: Record<string, string | null>, replace = false) {
    const next = patchQuery(new URLSearchParams(window.location.search), updates);
    writeBrowserQuery(next, replace);
  }
  const model = useLeaderboardDiscovery({ ...props, url: params.toString(), navigate });
  const rawIds = params.get("p");
  const ids = useMemo(() => parseIdList(rawIds), [rawIds]);
  const compare = useCompareSelection(model.livePlayers, ids, model.season);
  const missing = ids.filter(id => !model.livePlayers.some(p => p.id === id && p.seasons.includes(model.season)));
  function reason(id: string) {
    const bio = model.livePlayers.find(p => p.id === id);
    if (ids.includes(id)) return "Selected";
    if (ids.length >= 4) return "Four selected";
    if (!compare.sameGroup) return "Different stat group";
    if (!bio || !bio.seasons.includes(model.season) || !isPositionCode(bio.position)) return "Unavailable";
    if (compare.positionGroup && positionGroupOf(bio.position) !== compare.positionGroup) return "Different stat group";
    return null;
  }
  function add(id: string) { if (!reason(id)) navigate({ p: [...ids, id].join(",") }); }
  const suggestions = searchPlayers(model.livePlayers.filter(p => !reason(p.id)), model.query).slice(0, 8);
  return <main className="mx-auto max-w-6xl space-y-3 px-4 py-5">
    <header><h1 className="text-3xl font-semibold tracking-tight">Search</h1>
      <p className="text-sm text-muted-foreground">Discover players and compare up to four from the same stat group.</p></header>
    <PlayerLeaderboardFilters model={model}>
      <PlayerCombobox label="Search players" query={model.query} onQueryChange={model.setQuery} onPick={add}
        disabled={ids.length >= 4} showWhenEmpty={ids.length === 0}
        emptyMessage={ids.length >= 4 ? "Maximum four selected. Remove a player to add another." : "No eligible matching players for this season and stat group."}
        items={suggestions.map(p => ({ key: p.id, primary: p.name, secondary: `${p.position} / ${p.team}` }))} />
    </PlayerLeaderboardFilters>
    {model.directoryReady && ((params.has("pos") && params.get("pos") !== model.group) || (params.has("stat") && params.get("stat") !== model.statId) || (params.has("season") && Number(params.get("season")) !== model.season)) &&
      <p role="status" className="text-sm text-warning-foreground">Some shared filters are unavailable. <button className="underline" onClick={() => navigate({ pos: model.group, stat: model.statId, season: String(model.season), min: null }, true)}>Clear invalid filters</button></p>}
    <p className="text-xs text-muted-foreground">Published season {model.season}, through week {model.asOfWeek}. Filters apply to discovery; selected comparison columns stay selected.</p>
    <div className="flex flex-wrap gap-1">{ids.map(id => <button key={id} onClick={() => navigate({ p: ids.filter(p => p !== id).join(",") })}
      className="border border-border bg-card px-2 py-1 text-sm" aria-label={`Remove ${model.livePlayers.find(p => p.id === id)?.name ?? id}`}>
      {model.livePlayers.find(p => p.id === id)?.name ?? id} {missing.includes(id) ? "(unavailable this season)" : ""} ×</button>)}</div>
    {missing.length > 0 && <p role="status" className="text-sm text-muted-foreground">Some shared players are unavailable for this season. Remove them to change the comparison.</p>}
    {!compare.sameGroup ? <p role="alert">Comparison requires the same stat group. Remove an incompatible player.</p> : compare.loading ?
      <div role="status" className="min-h-32 border border-border p-3">Loading comparison…</div> : compare.displayedColumns.length > 0 &&
      <div className="border border-border bg-card max-md:-mx-4 max-md:border-x-0"><CompareBoard columns={compare.displayedColumns} /></div>}
    <section aria-label="Discovery results" className="min-h-32 space-y-1">
      <h2 className="text-sm font-semibold">Discovery results</h2>
      <PlayerDiscoveryResults model={model} addAction={(id, name) => <button aria-label={`Add ${name} to comparison`}
        disabled={!!reason(id)} title={reason(id) ?? "Add to comparison"} onClick={() => add(id)}
        className="border border-border bg-card px-2 text-xs disabled:text-muted-foreground">{reason(id) ?? "Add"}</button>} />
    </section>
  </main>;
}
