"use client";
import { useMemo, useState } from "react";
import type { ProjectionEntitySummary } from "@/lib/projections";
import { canCompare, comparisonGroup, type ComparisonGroup } from "@/lib/projection-math";
import { PlayerCombobox } from "@/components/search/PlayerCombobox";
import { rankCandidates } from "@/lib/search/fuzzy";

/** Noun phrase for the group a current selection locks the picker to. */
const GROUP_LABEL: Record<ComparisonGroup, string> = {
  QB: "QBs",
  SKILL: "RBs, WRs and TEs",
  K: "kickers",
  DST: "defenses",
};

function groupOf(position: string): ComparisonGroup | null {
  try {
    return comparisonGroup(position);
  } catch {
    return null;
  }
}

export function ProjectionPicker({
  entities,
  selected,
  onAdd,
}: {
  entities: ProjectionEntitySummary[];
  selected: string[];
  onAdd: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const atCap = selected.length >= 4;
  const positions = useMemo(() => new Map(entities.map((e) => [e.entityKey, e.position])), [entities]);
  // First still-known selection fixes the comparison group; an empty selection offers everything.
  const anchor = useMemo(() => {
    for (const key of selected) {
      const p = positions.get(key);
      if (p && groupOf(p)) return p;
    }
    return null;
  }, [positions, selected]);
  const lockedGroup = anchor ? groupOf(anchor) : null;
  const pool = useMemo(() => {
    const rest = entities.filter((e) => !selected.includes(e.entityKey));
    return anchor ? rest.filter((e) => canCompare(anchor, e.position)) : rest;
  }, [entities, selected, anchor]);
  const matches = useMemo(() => {
    return rankCandidates([...pool].sort((a, b) => b.expectedPoints - a.expectedPoints)
      .map(e => ({ ...e, id: e.entityKey })), query).slice(0, 8);
  }, [pool, query]);
  const helper =
    lockedGroup && pool.length === 0
      ? `Only ${GROUP_LABEL[lockedGroup]} can be compared with your current selection.`
      : null;

  return <div className="border border-border bg-card p-3">
    <PlayerCombobox label="Add a projection" query={query} onQueryChange={setQuery} onPick={onAdd}
      disabled={atCap} showWhenEmpty={selected.length === 0}
      placeholder={lockedGroup ? `Search ${GROUP_LABEL[lockedGroup]}` : "Search name, team, position, opponent"}
      items={matches.map(e => ({ key: e.entityKey, primary: e.name, secondary: `${e.team} / ${e.position} vs ${e.opponent}`, meta: e.expectedPoints.toFixed(1) }))} />
    {helper && <p className="mt-2 text-sm text-muted-foreground">{helper}</p>}
  </div>;
}
