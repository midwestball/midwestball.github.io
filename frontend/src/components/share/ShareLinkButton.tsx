"use client";
import { useState } from "react";
export function ShareLinkButton({ getHref, label = "Share link", disabled = false }: { getHref?: () => string; label?: string; disabled?: boolean }) {
  const [status, setStatus] = useState("");
  const [fallback, setFallback] = useState("");
  async function copy() {
    let href = "";
    try {
      href = getHref?.() ?? window.location.href;
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
  </div>;
}
