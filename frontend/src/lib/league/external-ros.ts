import externalRosJson from "@/data/external-ros-projections.json";
import { playerDeviation } from "@/lib/league/project";
import type { RosPlayer } from "@/lib/ros";

export type ExternalRosPlayer = {
  name: string;
  position: string;
  team: string;
  sleeperId?: string;
  espnId?: string;
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

export function sourceProjection(player: RosPlayer): SourceProjection {
  const band = midwestballBand(player);
  const ext = externalFor(player.playerId);
  const sleeper = ext?.sleeper ?? null;
  const espn = ext?.espn ?? null;
  const parts = [player.mean];
  if (sleeper != null) parts.push(sleeper);
  if (espn != null) parts.push(espn);
  return {
    midwestball: player.mean,
    midwestballLo: band.lo,
    midwestballHi: band.hi,
    sleeper,
    espn,
    blend: parts.reduce((a, b) => a + b, 0) / parts.length,
    sourceCount: parts.length,
  };
}

export function formatSourceLine(player: RosPlayer): string {
  const s = sourceProjection(player);
  const mb = `MB ${s.midwestball.toFixed(1)} (${s.midwestballLo.toFixed(0)}–${s.midwestballHi.toFixed(0)})`;
  const sl = s.sleeper != null ? `SL ${s.sleeper.toFixed(1)}` : "SL —";
  const es = s.espn != null ? `ESPN ${s.espn.toFixed(1)}` : "ESPN —";
  const meanLabel = s.sourceCount === 3 ? "μ3" : `μ${s.sourceCount}`;
  return `${mb} · ${sl} · ${es} · ${meanLabel} ${s.blend.toFixed(1)}`;
}
