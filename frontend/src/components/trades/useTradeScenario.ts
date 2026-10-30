"use client";
import { useEffect, useState, type SetStateAction } from "react";
import { DEFAULT_SETTINGS, restoreRoster } from "@/lib/trades";
import { decodeTradeShare, encodeTradeShare, TRADE_KEYS, type TradeShareState } from "@/lib/share-state/trades";
import { useBrowserQuery, writeBrowserQuery } from "@/components/share/browser-query";
export const STORAGE_KEY = "midwestball-trade-roster-v1";
const empty = (): TradeShareState => ({ mode: "roster", settings: { ...DEFAULT_SETTINGS }, roster: [], give: [], receive: [], drops: [] });
export function useTradeScenario(available?: ReadonlySet<string>) {
  const raw = useBrowserQuery();
  const decoded = decodeTradeShare(new URLSearchParams(raw), available);
  const shared = decoded.state !== null || !!decoded.fatal;
  const [local, setLocal] = useState(empty);
  const [draft, setDraft] = useState<{ raw: string; state: TradeShareState } | null>(null);
  const [ready, setReady] = useState(false);
  const [storageNote, setStorageNote] = useState("");
  function readSaved() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const restored = raw ? restoreRoster(JSON.parse(raw)) : null;
      if (raw && !restored) setStorageNote("The saved roster could not be restored. Build a new roster below.");
      return restored ? { ...empty(), ...restored } : empty();
    } catch { setStorageNote("Browser storage is unavailable. Your roster will last for this visit."); return empty(); }
  }
  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) { setLocal(readSaved()); setReady(true); } });
    const restore = () => { if (!TRADE_KEYS.some(k => new URLSearchParams(location.search).has(k))) setLocal(readSaved()); };
    window.addEventListener("popstate", restore);
    return () => { cancelled = true; window.removeEventListener("popstate", restore); };
  }, []);
  useEffect(() => {
    // Check the actual address as well: no URL hydration timing can enable a write.
    if (!ready || shared || TRADE_KEYS.some(k => new URLSearchParams(location.search).has(k))) return;
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, settings: local.settings, roster: local.roster })); }
    catch { /* The working scenario remains usable. */ }
  }, [local, ready, shared]);
  const state = shared && draft?.raw === raw ? draft.state : decoded.state ?? local;
  function change(apply: (current: TradeShareState) => TradeShareState) {
    if (shared) {
      const current = draft?.raw === location.search ? draft.state : decodeTradeShare(new URLSearchParams(location.search)).state;
      if (!current) return;
      const next = apply(current);
      try {
        const encoded = encodeTradeShare(next); const params = new URLSearchParams(location.search);
        TRADE_KEYS.forEach(k => params.delete(k)); encoded.forEach((v,k) => params.set(k,v));
        setDraft(null); setStorageNote(""); writeBrowserQuery(params, true);
      } catch (error) {
        setDraft({ raw: location.search, state: next });
        setStorageNote(error instanceof Error ? error.message : "Check the scenario before sharing.");
      }
    } else setLocal(apply);
  }
  function update<K extends keyof TradeShareState>(key: K, value: SetStateAction<TradeShareState[K]>) {
    change(current => ({ ...current, [key]: typeof value === "function" ? (value as (v: TradeShareState[K]) => TradeShareState[K])(current[key]) : value }));
  }
  function clearShare() { const p = new URLSearchParams(location.search); TRADE_KEYS.forEach(k => p.delete(k)); writeBrowserQuery(p, true); }
  function useSaved() { setLocal(readSaved()); clearShare(); }
  function save() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, settings: state.settings, roster: state.roster })); setStorageNote("Roster saved"); }
    catch { setStorageNote("Could not save this roster. Browser storage is unavailable."); }
  }
  function shareHref() { const url = new URL(location.href); TRADE_KEYS.forEach(k => url.searchParams.delete(k)); encodeTradeShare(state).forEach((v,k) => url.searchParams.set(k,v)); return url.toString(); }
  return { state, update, change, shared, fatal: decoded.fatal, warnings: decoded.warnings, storageNote, ready, save, useSaved, shareHref };
}
