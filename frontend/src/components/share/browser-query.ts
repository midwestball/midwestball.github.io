"use client";
import { useSyncExternalStore } from "react";
const EVENT = "midwestball:query";
function subscribe(listener: () => void) {
  window.addEventListener("popstate", listener); window.addEventListener(EVENT, listener);
  return () => { window.removeEventListener("popstate", listener); window.removeEventListener(EVENT, listener); };
}
export function useBrowserQuery() {
  return useSyncExternalStore(subscribe, () => window.location.search, () => "");
}
export function writeBrowserQuery(params: URLSearchParams, replace = false) {
  const href = `${location.pathname}${params.size ? `?${params}` : ""}${location.hash}`;
  if (replace) history.replaceState(null, "", href); else history.pushState(null, "", href);
  window.dispatchEvent(new Event(EVENT));
}
