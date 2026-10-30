"use client";
import { useId, useState } from "react";
export type SuggestionItem = { key: string; primary: string; secondary: string; meta?: string };
export function PlayerCombobox({ label, placeholder = "Search name, team or position", items, onPick, disabled = false,
  showWhenEmpty = false, query: controlled, onQueryChange, emptyMessage = "No matching players available." }: {
  label: string; placeholder?: string; items: SuggestionItem[]; onPick: (key: string) => void; disabled?: boolean;
  showWhenEmpty?: boolean; query?: string; onQueryChange?: (query: string) => void; emptyMessage?: string;
}) {
  const id = useId();
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<boolean | null>(null);
  const [active, setActive] = useState(0);
  const open = !disabled && (expanded ?? showWhenEmpty);
  const index = Math.min(active, Math.max(items.length - 1, 0));
  function change(value: string) { setQuery(value); onQueryChange?.(value); }
  function pick(key: string) { if (disabled) return; onPick(key); change(""); setExpanded(false); setActive(0); }
  return <div className="min-w-0 flex-1 space-y-1" onBlur={event => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setExpanded(false);
  }}>
    <label htmlFor={id} className="block text-xs font-semibold">{label}</label>
    <input id={id} type="search" role="combobox" aria-autocomplete="list" aria-expanded={open}
      aria-controls={`${id}-list`} aria-activedescendant={open && items.length ? `${id}-${index}` : undefined}
      disabled={disabled} value={controlled ?? query} placeholder={disabled ? "Maximum four selected" : placeholder}
      onClick={() => setExpanded(true)} onFocus={() => setExpanded(true)} onChange={e => { change(e.target.value); setActive(0); setExpanded(true); }}
      onKeyDown={event => {
        if (disabled) return;
        if (event.key === "Escape") setExpanded(false);
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
          event.preventDefault(); setExpanded(true);
          setActive(open ? Math.max(0, Math.min(index + (event.key === "ArrowDown" ? 1 : -1), items.length - 1)) : 0);
        }
        if (event.key === "Enter" && open && items[index]) { event.preventDefault(); pick(items[index].key); }
      }} className="h-9 w-full border border-border bg-card px-2 text-sm text-foreground disabled:bg-muted" />
    {open && <ul id={`${id}-list`} role="listbox" aria-label={`${label} results`} className="max-h-64 overflow-auto border border-border bg-popover">
      {items.length ? items.map((item, i) => <li key={item.key} role="presentation">
        <button type="button" role="option" id={`${id}-${i}`} aria-selected={i === index} tabIndex={-1} onMouseDown={e => e.preventDefault()} onClick={() => pick(item.key)}
          className={`flex w-full items-center justify-between gap-2 px-2 py-2 text-left text-sm hover:bg-accent ${i === index ? "bg-accent" : ""}`}>
          <span><strong>{item.primary}</strong> <span className="text-xs text-muted-foreground">{item.secondary}</span></span>
          {item.meta && <span className="shrink-0 tabular-nums">{item.meta}</span>}
        </button>
      </li>) : <li role="status" className="p-2 text-sm text-muted-foreground">{emptyMessage}</li>}
    </ul>}
  </div>;
}
