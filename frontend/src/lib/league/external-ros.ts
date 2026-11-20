import externalRosJson from "@/data/external-ros-projections.json";
import { playerDeviation } from "@/lib/league/project";
import type { RosPlayer, RosSnapshot } from "@/lib/ros";

export type ExternalRosPlayer = {
  name: string;
  position: string;
  team: string;
  sleeperId?: string | null;
  espnId?: string | null;
  sleeper: number | null;
  espn: number | null;
};

export type ExternalRosSnapshot = {
  schemaVersion: 1;
  kind: "external-ros";
  season: number;
  horizonStartWeek: number;
  horizonEndWeek: number;
  scoring: string;
  capturedAt: string;
  notes: string[];
  counts: { players: number; withSleeper: number; withEspn: number; withBoth: number };
  players: Record<string, ExternalRosPlayer>;
};

export type RankingSource = "midwestball" | "sleeper" | "espn" | "mean";

export const RANKING_SOURCES: { id: RankingSource; label: string; short: string }[] = [
  { id: "midwestball", label: "Midwest Ball", short: "MB" },
  { id: "sleeper", label: "Sleeper", short: "Sleeper" },
  { id: "espn", label: "ESPN", short: "ESPN" },
  { id: "mean", label: "Mean of available", short: "Mean" },
];

export type SourceProjection = {
  midwestball: number;
  midwestballLo: number;
  midwestballHi: number;
  sleeper: number | null;
  espn: number | null;
  /** Mean of the sources that are present (MB always; Sleeper/ESPN when available). */
  blend: number;
  sourceCount: number;
};

export const externalRos = externalRosJson as ExternalRosSnapshot;

export function externalFor(playerId: string): ExternalRosPlayer | null {
  return externalRos.players[playerId] ?? null;
}

/** ±1σ band around the midwestball mean using the same normal fit as league/trade labs. */
export function midwestballBand(player: RosPlayer): { lo: number; hi: number } {
  const sd = playerDeviation(player);
  return { lo: Math.max(0, player.mean - sd), hi: player.mean + sd };
}

/**
 * @param midwestballPlayer - Original MB entity when `player` may already be remapped for ranking.
 */
export function sourceProjection(player: RosPlayer, midwestballPlayer: RosPlayer = player): SourceProjection {
  const band = midwestballBand(midwestballPlayer);
  const ext = externalFor(player.playerId);
  const sleeper = ext?.sleeper ?? null;
  const espn = ext?.espn ?? null;
  const parts = [midwestballPlayer.mean];
  if (sleeper != null) parts.push(sleeper);
  if (espn != null) parts.push(espn);
  return {
    midwestball: midwestballPlayer.mean,
    midwestballLo: band.lo,
    midwestballHi: band.hi,
    sleeper,
    espn,
    blend: parts.reduce((a, b) => a + b, 0) / parts.length,
    sourceCount: parts.length,
  };
}

/** Point estimate used for lineup totals / trade ranking under the selected source. */
export function rankingPoints(player: RosPlayer, source: RankingSource, midwestballPlayer: RosPlayer = player): number {
  if (source === "midwestball") return midwestballPlayer.mean;
  const s = sourceProjection(player, midwestballPlayer);
  if (source === "sleeper") return s.sleeper ?? midwestballPlayer.mean;
  if (source === "espn") return s.espn ?? midwestballPlayer.mean;
  return s.blend;
}

/** Shift MB mean + quantiles to the ranking source so search/P(help) use that level. */
export function remapRosPlayer(player: RosPlayer, source: RankingSource): RosPlayer {
  if (source === "midwestball") return player;
  const next = rankingPoints(player, source);
  const delta = next - player.mean;
  if (Math.abs(delta) < 1e-9) return player;
  return {
    ...player,
    mean: next,
    quantiles: player.quantiles.map((q) => Math.max(0, q + delta)) as RosPlayer["quantiles"],
  };
}

export function remapRosSnapshot(snapshot: RosSnapshot, source: RankingSource): RosSnapshot {
  if (source === "midwestball") return snapshot;
  return { ...snapshot, entities: snapshot.entities.map((player) => remapRosPlayer(player, source)) };
}

export function formatSourceLine(player: RosPlayer, midwestballPlayer: RosPlayer = player): string {
  const s = sourceProjection(player, midwestballPlayer);
  const mb = `MB ${s.midwestball.toFixed(1)} (${s.midwestballLo.toFixed(0)}–${s.midwestballHi.toFixed(0)})`;
  const sl = s.sleeper != null ? `SL ${s.sleeper.toFixed(1)}` : "SL —";
  const es = s.espn != null ? `ESPN ${s.espn.toFixed(1)}` : "ESPN —";
  const meanLabel = s.sourceCount === 3 ? "μ3" : `μ${s.sourceCount}`;
  return `${mb} · ${sl} · ${es} · ${meanLabel} ${s.blend.toFixed(1)}`;
}
