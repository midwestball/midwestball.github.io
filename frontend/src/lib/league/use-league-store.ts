"use client";

import { useMemo, useSyncExternalStore } from "react";
import {
  EMPTY_LEAGUE_STORE,
  LEAGUE_STORAGE_KEY,
  parseLeagueStore,
  removeLeague,
  saveLeagueStore,
  upsertLeague,
  type LeagueStore,
} from "./store";
import type { SavedLeague } from "./types";

export const LEAGUE_STORE_EVENT = "midwestball-league-lab-change";

function subscribe(callback: () => void) {
  window.addEventListener(LEAGUE_STORE_EVENT, callback);
  window.addEventListener("storage", callback);
  return () => {
    window.removeEventListener(LEAGUE_STORE_EVENT, callback);
    window.removeEventListener("storage", callback);
  };
}

function readRaw(): string {
  try {
    return localStorage.getItem(LEAGUE_STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function useLeagueLabStore() {
  const raw = useSyncExternalStore(subscribe, readRaw, () => "");
  const store = useMemo(() => {
    if (!raw) return EMPTY_LEAGUE_STORE;
    try {
      return parseLeagueStore(JSON.parse(raw));
    } catch {
      return EMPTY_LEAGUE_STORE;
    }
  }, [raw]);

  const league = store.leagues.find((item) => item.id === store.activeId) ?? null;

  function commit(next: LeagueStore): boolean {
    if (!saveLeagueStore(next)) return false;
    window.dispatchEvent(new Event(LEAGUE_STORE_EVENT));
    return true;
  }

  function save(next: SavedLeague): boolean {
    return commit(upsertLeague(store, next));
  }

  function unlink(id: string): boolean {
    return commit(removeLeague(store, id));
  }

  function activate(id: string): boolean {
    return commit({ ...store, activeId: id });
  }

  return { store, league, commit, save, unlink, activate };
}
