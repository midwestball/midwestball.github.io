"use client";
import { useId, useMemo, useRef, useState } from "react";
import type { ProjectionEntitySummary } from "@/lib/projections";
import { canCompare, comparisonGroup, type ComparisonGroup } from "@/lib/projection-math";
import { TeamAbbr } from "@/components/TeamAbbr";

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
  // Suggestions collapse after a pick so the chart and table own the screen, and
  // come straight back whenever the search box takes focus.
  const [expanded, setExpanded] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const listId = useId();
  const showList = expanded || selected.length === 0;

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
    const q = query.trim().toLowerCase();
    return pool
      .filter((e) => !q || `${e.name} ${e.team} ${e.position} ${e.opponent}`.toLowerCase().includes(q))
      .sort((a, b) => b.expectedPoints - a.expectedPoints)
      .slice(0, 8);
  }, [pool, query]);
  const helper =
    lockedGroup && pool.length === 0
      ? `Only ${GROUP_LABEL[lockedGroup]} can be compared with your current selection.`
      : null;

  const pick = (id: string) => {
    onAdd(id);
    setQuery("");
    setExpanded(false);
    searchRef.current?.blur();
  };

  return (
    <div className="border border-zinc-200 bg-white p-3">
      <label htmlFor="projection-search" className="text-sm font-semibold">
        Add a projection
      </label>
      <input
        id="projection-search"
        ref={searchRef}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => setExpanded(true)}
        onBlur={() => setExpanded(false)}
        role="combobox"
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
        disabled={atCap}
        placeholder={
          atCap
            ? "Maximum four selected"
            : lockedGroup
              ? `Search ${GROUP_LABEL[lockedGroup]}…`
              : "Search name, team, position, opponent"
        }
        className="mt-2 w-full rounded-none border border-zinc-300 px-3 py-2 text-sm"
      />
      {helper ? (
        <p className="mt-2 text-sm text-zinc-500">{helper}</p>
      ) : showList && matches.length > 0 ? (
        <ul id={listId} role="listbox" className="mt-1 border border-zinc-200">
          {matches.map((e) => (
            <li key={e.entityKey} role="presentation">
              <button
                role="option"
                aria-selected={false}
                className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-zinc-50 focus:bg-zinc-50"
                // Keeping focus on the input stops the list from vanishing on blur
                // before this click lands.
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => pick(e.entityKey)}
              >
                <span className="flex min-w-0 flex-wrap items-center gap-x-1.5">
                  <span className="font-medium text-zinc-900">{e.name}</span>
                  <TeamAbbr team={e.team} />
                  <span className="text-zinc-500">
                    {e.position} vs {e.opponent}
                  </span>
                </span>
                <span className="shrink-0 tabular-nums">{e.expectedPoints.toFixed(1)}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
