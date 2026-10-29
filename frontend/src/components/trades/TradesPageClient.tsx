"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { RosPlayerPicker } from "@/components/projections/RosPlayerPicker";
import { useRos } from "@/components/projections/useRos";
import { rosMedian, type RosPlayer } from "@/lib/ros";
import { activeCapacity, DEFAULT_SETTINGS, evaluateTrade, restoreRoster, SLOT_TYPES, validSettings, type Lineup, type RosterEntry, type RosterSettings } from "@/lib/trades";

const STORAGE_KEY = "midwestball-trade-roster-v1";
const control = "border border-zinc-300 bg-white px-2 py-1 text-sm";
const signed = (n: number) => `${n > 0 ? "+" : ""}${n.toFixed(1)}`;

export function TradesPageClient() {
  const { snapshot, error, retry } = useRos();
  const [settings, setSettings] = useState<RosterSettings>({ ...DEFAULT_SETTINGS });
  const [roster, setRoster] = useState<RosterEntry[]>([]);
  const [ready, setReady] = useState(false);
  const [storageNote, setStorageNote] = useState("");
  const [rosterAware, setRosterAware] = useState(true);
  const [give, setGive] = useState<string[]>([]);
  const [receive, setReceive] = useState<string[]>([]);
  const [drops, setDrops] = useState<string[]>([]);
  useEffect(() => {
    let cancelled = false;
    // Restore after hydration; storage is external to the server-rendered page.
    queueMicrotask(() => {
      if (cancelled) return;
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (raw) {
          const saved = restoreRoster(JSON.parse(raw));
          if (saved) { setSettings(saved.settings); setRoster(saved.roster); }
          else setStorageNote("The saved roster could not be restored. Build a new roster below.");
        }
      } catch { setStorageNote("Browser storage is unavailable. Your roster will last for this visit."); }
      setReady(true);
    });
    return () => { cancelled = true; };
  }, []);
  useEffect(() => {
    if (!ready) return;
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, settings, roster })); }
    catch { /* Roster editing still works when browser storage is full or disabled. */ }
  }, [ready, settings, roster]);

  const players = useMemo(() => snapshot?.entities ?? [], [snapshot]);
  const byId = useMemo(() => new Map(players.map(p => [p.playerId, p])), [players]);
  const calculation = useMemo(() => {
    if (!give.length && !receive.length) return null;
    if (!rosterAware) {
      if ([...give, ...receive].some(id => !byId.has(id))) return { error: "A selected player is unavailable. Select the trade again." };
      const sum = (ids: string[]) => ids.reduce((n, id) => n + rosMedian(byId.get(id)!), 0);
      return { packageDelta: sum(receive) - sum(give) };
    }
    try { return evaluateTrade(players, roster, give, receive, drops, settings); }
    catch (cause) { return { error: cause instanceof Error ? cause.message : "Check your roster." }; }
  }, [players, byId, roster, give, receive, drops, settings, rosterAware]);

  function remove(id: string) {
    setRoster(rows => rows.filter(p => p.playerId !== id));
    setGive(ids => ids.filter(p => p !== id)); setDrops(ids => ids.filter(p => p !== id));
  }
  function changeMode(value: boolean) { setRosterAware(value); setGive([]); setReceive([]); setDrops([]); }
  function preset(name: string) {
    setSettings({ ...DEFAULT_SETTINGS, ...(name === "superflex" ? { SUPERFLEX: 1 } : name === "two-qb" ? { QB: 2 } : {}) });
  }
  if (!snapshot) return <main className="mx-auto max-w-5xl px-4 py-5"><h1 className="text-3xl font-semibold">Trade analysis</h1><p role="status" className="mt-4 border border-zinc-200 p-4 text-sm">{error || "Loading rest-of-season projections…"}{error && <button onClick={retry} className="ml-3 underline">Retry</button>}</p></main>;

  return <main className="mx-auto max-w-5xl space-y-4 px-4 py-5">
    <header><p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">{snapshot.season} · ROS through week {snapshot.cutoffWeek} · Full PPR</p>
      <h1 className="text-3xl font-semibold tracking-tight">Trade analysis</h1>
      <p className="mt-2 border border-amber-300 bg-amber-50 p-2 text-sm text-amber-900"><strong>Experimental:</strong> Rest-of-season forecasts have not passed a separate ROS validation gate. Current injury news is not an input. Updated <time dateTime={snapshot.generatedAt}>{new Date(snapshot.generatedAt).toLocaleString()}</time>.</p>
      <p className="mt-1 max-w-3xl text-sm text-zinc-600">Compare remaining regular-season points using each player’s median projection. Add your roster to see how a trade changes your best starting lineup.</p>
    </header>
    <div role="group" aria-label="Trade comparison mode" className="flex gap-1">{[true, false].map(value => <button key={String(value)} onClick={() => changeMode(value)} aria-pressed={rosterAware === value} className={`border px-3 py-2 text-sm font-semibold ${rosterAware === value ? "border-zinc-900 bg-zinc-900 text-white" : "border-zinc-300 bg-white text-zinc-600"}`}>{value ? "My roster" : "Player packages"}</button>)}</div>

    {rosterAware && <section className="border border-zinc-200 bg-white" aria-labelledby="roster-title">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-200 px-3 py-2"><h2 id="roster-title" className="font-semibold">Your roster</h2>
        <p className="text-xs text-zinc-500">{roster.filter(p => !p.ir).length}/{activeCapacity(settings)} modeled players · {roster.filter(p => p.ir).length}/{settings.ir} IR</p></div>
      <div className="space-y-3 p-3">
        <details><summary className="cursor-pointer text-sm font-semibold">Lineup settings</summary>
          <div className="mt-2 flex flex-wrap gap-1">{[["standard", "Standard"], ["superflex", "Superflex"], ["two-qb", "Two QB"]].map(([key, label]) => <button key={key} className={control} onClick={() => preset(key)}>{label}</button>)}</div>
          <div className="mt-2 grid grid-cols-3 gap-2 sm:grid-cols-5">{[...SLOT_TYPES, "bench", "ir", "K", "DST"].map(key => <label key={key} className="text-xs font-semibold">{key === "bench" ? "Bench" : key === "ir" ? "IR" : key}<input aria-label={`${key} slots`} type="number" min={0} max={12} value={settings[key as keyof RosterSettings]} onChange={e => {
            const count = Number(e.target.value); if (Number.isInteger(count) && count >= 0 && count <= 12) setSettings(s => ({ ...s, [key]: count }));
          }} className={`${control} mt-1 w-full`} /></label>)}</div>
          {!validSettings(settings) && <p role="alert" className="mt-2 text-sm text-red-700">Choose 1–16 modeled starting slots and at most 32 active roster spots.</p>}
        </details>
        <p className="text-xs text-zinc-500">FLEX: RB/WR/TE. SUPERFLEX: QB/RB/WR/TE. K and DST are reserved slots and excluded from ROS scoring. IR players cannot start.</p>
        {storageNote && <p role="status" className="text-xs text-amber-800">{storageNote}</p>}
        <RosPlayerPicker players={players} excluded={roster.map(p => p.playerId)} label="Add to your roster" disabled={roster.length >= 44} onAdd={playerId => {
          setRoster(rows => [...rows, { playerId, ir: false }]); setReceive(ids => ids.filter(id => id !== playerId));
        }} />
        {roster.length ? <div className="overflow-x-auto"><table className="w-full text-left text-sm"><caption className="sr-only">Your roster and proposed outgoing players</caption><thead><tr>{["Player", "ROS median", "Status", "Trade action", ""].map((h, i) => <th key={i} scope="col" className="border-b border-zinc-200 py-2 pr-2">{h}</th>)}</tr></thead>
          <tbody>{roster.map(entry => { const p = byId.get(entry.playerId); return <tr key={entry.playerId}>
            <th scope="row" className="border-b border-zinc-100 py-2 pr-2"><span className="block">{p?.name ?? entry.playerId}</span><span className="text-xs font-normal text-zinc-500">{p ? `${p.position} · ${p.team}` : "Unavailable in this snapshot — remove to evaluate"}</span></th>
            <td className="border-b border-zinc-100 pr-2 tabular-nums">{p ? rosMedian(p).toFixed(1) : "—"}</td>
            <td className="border-b border-zinc-100 pr-2"><select aria-label={`Status for ${p?.name ?? entry.playerId}`} value={entry.ir ? "ir" : "active"} className={control} onChange={e => setRoster(rows => rows.map(r => r.playerId === entry.playerId ? { ...r, ir: e.target.value === "ir" } : r))}><option value="active">Active</option><option value="ir">IR</option></select></td>
            <td className="border-b border-zinc-100 pr-2"><select aria-label={`Trade action for ${p?.name ?? entry.playerId}`} className={control} value={give.includes(entry.playerId) ? "give" : drops.includes(entry.playerId) ? "drop" : "keep"} onChange={e => {
              setGive(ids => [...ids.filter(id => id !== entry.playerId), ...(e.target.value === "give" ? [entry.playerId] : [])]);
              setDrops(ids => [...ids.filter(id => id !== entry.playerId), ...(e.target.value === "drop" ? [entry.playerId] : [])]);
            }}><option value="keep">Keep</option><option value="give">Give</option><option value="drop">Drop</option></select></td>
            <td className="border-b border-zinc-100"><button onClick={() => remove(entry.playerId)} aria-label={`Remove ${p?.name ?? entry.playerId} from roster`} className="text-xs underline">Remove</button></td>
          </tr>; })}</tbody></table></div> : <p className="text-sm text-zinc-500">Start with your QB, RBs, WRs and TE, then add your bench. Starting slots are filled automatically by projected ROS points.</p>}
        <p className="text-xs text-zinc-500">Roster and settings save in this browser. Trade selections are temporary.</p>
      </div>
    </section>}

    <section className="grid gap-3 sm:grid-cols-2" aria-label="Proposed trade">
      <div className="space-y-2 border border-zinc-200 bg-white p-3"><h2 className="font-semibold">You give</h2>
        {rosterAware ? <p className="text-sm text-zinc-500">Choose “Give” beside players on your roster.</p> : <RosPlayerPicker players={players} excluded={[...give, ...receive]} label="Add a player to give" onAdd={id => setGive(ids => [...ids, id])} />}
        <Package ids={give} byId={byId} remove={id => setGive(ids => ids.filter(p => p !== id))} />
        {drops.length > 0 && <p className="text-xs text-amber-800">Also dropping: {drops.map(id => byId.get(id)?.name).join(", ")}. Drops count toward roster value.</p>}
      </div>
      <div className="space-y-2 border border-zinc-200 bg-white p-3"><h2 className="font-semibold">You receive</h2>
        <RosPlayerPicker players={players} excluded={[...receive, ...give, ...(rosterAware ? roster.map(p => p.playerId) : [])]} label="Add a player to receive" onAdd={id => setReceive(ids => [...ids, id])} />
        <Package ids={receive} byId={byId} remove={id => setReceive(ids => ids.filter(p => p !== id))} />
      </div>
    </section>

    <section aria-live="polite" aria-label="Trade result" className="border border-zinc-200 bg-white p-3">
      {!calculation ? <p className="text-sm text-zinc-500">Select a trade to compare projected ROS points.</p> : "error" in calculation ? <p role="alert" className="text-sm text-amber-800">{calculation.error}</p> : <>
        <div className="grid gap-3 sm:grid-cols-3"><Metric label="Player package difference" value={calculation.packageDelta} />
          {"lineupDelta" in calculation && <><Metric label="Starting lineup difference" value={calculation.lineupDelta} /><Metric label="Roster difference, including drops" value={calculation.rosterDelta} /></>}
        </div>
        {"before" in calculation && <><p className="mt-3 text-xs text-zinc-500">Best fixed starting lineup by summed individual ROS medians. Empty slots score zero; this does not model weekly lineup changes, bye replacements, or waiver pickups.</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2"><LineupTable title="Before trade" lineup={calculation.before} /><LineupTable title="After trade" lineup={calculation.after} /></div></>}
      </>}
    </section>
    <p className="text-xs text-zinc-500">Positive differences favor the players you receive. Values sum individual medians; they are not the median outcome of a package or a probability of winning a trade. Projections exclude current injury news. <Link href="/ballnet/?horizon=ros" className="underline">View ROS ranges and scoring</Link>.</p>
  </main>;
}

function Metric({ label, value }: { label: string; value: number }) {
  return <div><p className="text-xs text-zinc-500">{label}</p><p className={`text-2xl font-semibold tabular-nums ${value > 0 ? "text-emerald-700" : value < 0 ? "text-red-700" : "text-zinc-900"}`}>{signed(value)} <span className="text-xs font-normal text-zinc-500">ROS pts</span></p></div>;
}
function Package({ ids, byId, remove }: { ids: string[]; byId: Map<string, RosPlayer>; remove: (id: string) => void }) {
  return <ul className="divide-y divide-zinc-200">{ids.map(id => { const p = byId.get(id); return <li key={id} className="flex items-center justify-between gap-2 py-2 text-sm"><span><strong>{p?.name ?? id}</strong> <span className="text-xs text-zinc-500">{p?.position} · {p ? rosMedian(p).toFixed(1) : "—"}</span></span><button onClick={() => remove(id)} aria-label={`Remove ${p?.name ?? id} from trade`} className="text-xs underline">Remove</button></li>; })}</ul>;
}
function LineupTable({ title, lineup }: { title: string; lineup: Lineup }) {
  return <table className="w-full text-left text-sm"><caption className="border-b border-zinc-200 pb-1 text-left font-semibold">{title} · {lineup.total.toFixed(1)}</caption><thead><tr><th scope="col" className="py-1">Slot</th><th scope="col">Player</th><th scope="col">ROS</th></tr></thead><tbody>{lineup.assignments.map((a, i) => <tr key={i}><th scope="row" className="border-t border-zinc-100 py-1 pr-2 text-xs font-normal text-zinc-500">{a.slot}</th><td className="border-t border-zinc-100 py-1 pr-2">{a.player?.name ?? "Empty slot"}</td><td className="border-t border-zinc-100 py-1 tabular-nums">{a.player ? rosMedian(a.player).toFixed(1) : "0.0"}</td></tr>)}</tbody></table>;
}
