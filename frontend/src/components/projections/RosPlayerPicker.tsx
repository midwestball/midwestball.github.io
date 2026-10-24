"use client";

import { useMemo, useState } from "react";
import { ROS_POSITIONS, rosMedian, type RosPlayer } from "@/lib/ros";

export function RosPlayerPicker({ players, excluded, onAdd, label, disabled = false }: {
  players: RosPlayer[]; excluded: string[]; onAdd: (id: string) => void; label: string; disabled?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [position, setPosition] = useState("");
  const [open, setOpen] = useState(false);
  const matches = useMemo(() => players.filter(p => !excluded.includes(p.playerId) &&
    (!position || p.position === position) && `${p.name} ${p.team}`.toLowerCase().includes(query.toLowerCase().trim()))
    .sort((a, b) => rosMedian(b) - rosMedian(a) || a.name.localeCompare(b.name)).slice(0, 8), [players, excluded, position, query]);
  return <div className="space-y-1">
    <label className="block text-xs font-semibold" htmlFor={label}>{label}</label>
    <div className="flex gap-1">
      <input id={label} type="search" value={query} disabled={disabled} placeholder="Search name or team"
        className="min-w-0 flex-1 border border-zinc-300 bg-white px-2 py-2 text-sm disabled:bg-zinc-100"
        onFocus={() => setOpen(true)} onChange={e => { setQuery(e.target.value); setOpen(true); }} />
      <select aria-label={`${label} position`} value={position} disabled={disabled} onChange={e => { setPosition(e.target.value); setOpen(true); }} className="border border-zinc-300 bg-white px-2 text-sm">
        <option value="">All</option>{ROS_POSITIONS.map(p => <option key={p}>{p}</option>)}
      </select>
      {open && <button type="button" onClick={() => setOpen(false)} className="border border-zinc-300 px-2 text-xs">Close</button>}
    </div>
    {open && !disabled && <ul className="max-h-64 divide-y divide-zinc-200 overflow-auto border border-zinc-200 bg-white" aria-label={`${label} results`}>
      {matches.length ? matches.map(p => <li key={p.playerId}><button type="button" onClick={() => { onAdd(p.playerId); setQuery(""); setOpen(false); }} className="flex w-full items-center justify-between gap-2 px-2 py-2 text-left text-sm hover:bg-zinc-100">
        <span><strong>{p.name}</strong> <span className="text-xs text-zinc-500">{p.position} · {p.team}</span></span><span className="whitespace-nowrap tabular-nums">{rosMedian(p).toFixed(1)} <span className="text-xs text-zinc-500">ROS</span> +</span>
      </button></li>) : <li className="p-2 text-sm text-zinc-500">No matching players available.</li>}
    </ul>}
  </div>;
}
