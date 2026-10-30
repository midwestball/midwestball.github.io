"use client";
import { useState } from "react";
export function ShareLinkButton({ getHref, label = "Share link", disabled = false, exportText }: { getHref?: () => string; label?: string; disabled?: boolean; exportText?: string }) {
  const [status, setStatus] = useState("");
  const [fallback, setFallback] = useState("");
  const [long, setLong] = useState(false);
  async function copy() {
    let href = "";
    try {
      href = getHref?.() ?? window.location.href;
      setLong(href.length > 1800);
      await navigator.clipboard.writeText(href); setFallback(""); setStatus("Link copied");
    } catch (error) {
      if (href) { setFallback(href); setStatus("Could not copy; select this URL."); }
      else setStatus(error instanceof Error ? error.message : "Could not create link.");
    }
  }
  return <div className="space-y-1"><button type="button" disabled={disabled} aria-label="Copy shareable link" onClick={copy}
    className="border border-border bg-card px-2 py-1 text-sm disabled:text-muted-foreground">{label}</button>
    <span role="status" className="ml-2 text-xs text-muted-foreground">{status}</span>
    {fallback && <input aria-label="Shareable URL" readOnly value={fallback} onFocus={e => e.currentTarget.select()} className="w-full border border-border bg-card p-2 text-sm" />}
    {long && <p className="text-xs text-warning-foreground">This long link may be unreliable in some apps. No players were removed.</p>}
    {long && exportText && <details><summary className="cursor-pointer text-xs">Export scenario as text</summary><textarea aria-label="Scenario JSON" readOnly value={exportText} onFocus={e => e.currentTarget.select()} className="h-40 w-full border border-border bg-card p-2 text-xs" /></details>}
  </div>;
}
