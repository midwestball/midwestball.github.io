"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { fetchCurrentMeta, fetchPlayersIndex } from "@/lib/ballnet-store";
import type { PlayerBio } from "@/lib/payload";
import { PlayerPageClient } from "./PlayerPageClient";

export function RuntimePlayerPage() {
  const id = useSearchParams().get("id");
  const [loaded, setLoaded] = useState<{ player: PlayerBio; season: number } | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    void Promise.all([fetchPlayersIndex(), fetchCurrentMeta()]).then(([index, current]) => {
      if (cancelled) return;
      if (!index) { setError("Could not load the player index. Check your connection and retry."); return; }
      const player = index.players.find(p => p.id === id);
      if (!player) { setError("This player is not available in the current index."); return; }
      setLoaded({ player, season: current?.season ?? player.seasons.at(-1) ?? 2026 });
      setError("");
    }).catch(() => { if (!cancelled) setError("Could not load this player. Please retry."); });
    return () => { cancelled = true; };
  }, [id, attempt]);
  if (!id) return <main className="mx-auto max-w-3xl p-4">Choose a player from Search.</main>;
  if (loaded?.player.id === id) return <PlayerPageClient player={loaded.player} currentSeason={loaded.season} />;
  return <main className="mx-auto max-w-3xl p-4" role="status">{error || "Loading player…"}{error && <button className="ml-2 underline" onClick={() => { setError(""); setAttempt(n => n + 1); }}>Retry</button>}</main>;
}
