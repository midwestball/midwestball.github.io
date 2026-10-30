"use client";

import Link from "next/link";
import { PlayerComparisonLink } from "@/components/PlayerComparisonLink";
import { useBrowserQuery, writeBrowserQuery } from "@/components/share/browser-query";
import { decodeProjection } from "@/lib/share-state/projections";
import { patchQuery } from "@/lib/share-state/common";
import { RosPlayerPicker } from "./RosPlayerPicker";
import { useRos } from "./useRos";

export function RosProjections() {
  const { snapshot, error, retry } = useRos();
  const raw = useBrowserQuery();
  const parsed = decodeProjection(new URLSearchParams(raw), new Set(snapshot?.entities.map(p => p.playerId) ?? []));
  const selected = parsed.selected;
  function setSelected(update: (ids: string[]) => string[]) {
    writeBrowserQuery(patchQuery(new URLSearchParams(location.search), { p: update(selected).join(",") }));
  }
  if (!snapshot) return <div role="status" className="mx-auto max-w-5xl border border-border p-4 text-sm">{error || "Loading rest-of-season projections…"}{error && <button onClick={retry} className="ml-3 font-semibold underline">Retry</button>}</div>;
  const players = selected.map(id => snapshot.entities.find(p => p.playerId === id)).filter(p => p !== undefined);
  return <div>
    <header className="border-b border-border bg-card"><div className="mx-auto max-w-5xl px-4 py-5">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Rest of season · {snapshot.season} · through week {snapshot.cutoffWeek}</p>
      <h1 className="text-3xl font-semibold tracking-tight">Projections</h1>
      <p className="mt-2 border border-warning-border bg-warning-surface p-2 text-sm text-warning-foreground"><strong>Experimental:</strong> Rest-of-season forecasts have not passed a separate ROS validation gate. Current injury news is not an input.</p>
      <p className="mt-1 text-sm text-text-secondary">Remaining regular-season fantasy points, including missed-game risk. Full PPR. Updated <time dateTime={snapshot.generatedAt}>{new Date(snapshot.generatedAt).toLocaleString()}</time>.</p>
    </div></header>
    <main className="mx-auto max-w-5xl space-y-4 px-4 py-4">
      {parsed.stale > 0 && <p role="status" className="text-sm text-muted-foreground">{parsed.stale} shared players are unavailable in this snapshot.</p>}
      <RosPlayerPicker players={snapshot.entities} excluded={selected} label="Add a ROS projection" disabled={selected.length >= 4} onAdd={id => setSelected(ids => [...ids, id].slice(0, 4))} />
      {players.length ? <div className="overflow-x-auto"><table className="w-full border-collapse bg-card text-left text-sm">
        <caption className="pb-2 text-left text-xs text-muted-foreground">Compare up to four players. Percentiles describe each player’s possible ROS total.</caption>
        <thead><tr>{["Player", "Games left", "5%", "25%", "Median", "75%", "95%", "Mean", ""].map((h, i) => <th key={i} scope="col" className="border border-border px-2 py-2">{h}</th>)}</tr></thead>
        <tbody>{players.map(p => <tr key={p.playerId}><th scope="row" className="border border-border p-2"><span className="block whitespace-nowrap"><PlayerComparisonLink playerId={p.playerId} season={snapshot.season}>{p.name}</PlayerComparisonLink></span><span className="text-xs font-normal text-muted-foreground">{p.position} · {p.team}</span></th>
          <td className="border border-border p-2 tabular-nums">{p.remainingTeamGames}</td>{p.quantiles.map((q, i) => <td key={i} className={`border border-border p-2 tabular-nums ${i === 2 ? "bg-muted font-semibold" : ""}`}>{q.toFixed(1)}</td>)}
          <td className="border border-border p-2 tabular-nums">{p.mean.toFixed(1)}</td><td className="border border-border p-2"><button onClick={() => setSelected(ids => ids.filter(id => id !== p.playerId))} aria-label={`Remove ${p.name}`} className="text-xs underline">Remove</button></td>
        </tr>)}</tbody>
      </table></div> : <p className="border border-border bg-card p-4 text-sm text-text-secondary">Search above to compare rest-of-season projections.</p>}
      <Link href="/trades/" className="inline-block border border-ring bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary">Analyze a trade →</Link>
      <details className="border border-border p-3 text-sm"><summary className="cursor-pointer font-semibold">Scoring and methodology</summary><p className="mt-2 text-text-secondary">{snapshot.methodology}</p><p className="mt-2 text-text-secondary">QB: 0.04/pass yard + 4/pass TD − 2/INT + rushing points. RB/WR/TE: 1/reception + 0.1/scrimmage yard + 6/TD. Fumbles and two-point conversions are excluded. K and DST are not modeled.</p></details>
    </main>
  </div>;
}
