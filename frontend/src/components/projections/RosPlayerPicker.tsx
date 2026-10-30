"use client";
import { useMemo, useState } from "react";
import { ROS_POSITIONS, rosMedian, type RosPlayer } from "@/lib/ros";
import { rankCandidates } from "@/lib/search/fuzzy";
import { PlayerCombobox } from "@/components/search/PlayerCombobox";
export function RosPlayerPicker({ players, excluded, onAdd, label, disabled = false }: {
  players: RosPlayer[]; excluded: string[]; onAdd: (id: string) => void; label: string; disabled?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [position, setPosition] = useState("");
  const matches = useMemo(() => rankCandidates(players.filter(p => !excluded.includes(p.playerId) && (!position || p.position === position))
    .sort((a, b) => rosMedian(b) - rosMedian(a) || a.name.localeCompare(b.name)).map(p => ({ ...p, id: p.playerId })), query).slice(0, 8), [players, excluded, position, query]);
  return <div className="flex items-start gap-1">
    <PlayerCombobox label={label} disabled={disabled} query={query} onQueryChange={setQuery} onPick={onAdd}
      items={matches.map(p => ({ key: p.playerId, primary: p.name, secondary: `${p.position} / ${p.team}`, meta: `${rosMedian(p).toFixed(1)} ROS +` }))} />
    <label className="text-xs font-semibold">Position<select aria-label={`${label} position`} value={position} disabled={disabled} onChange={e => setPosition(e.target.value)} className="mt-1 block h-9 border border-border bg-card px-2 text-sm">
      <option value="">All</option>{ROS_POSITIONS.map(p => <option key={p}>{p}</option>)}
    </select></label>
  </div>;
}

