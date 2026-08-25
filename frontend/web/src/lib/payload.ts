import type { Point, StatAvailabilityStatus } from "@/lib/distribution";

/**
 * Per-player scalar overlay. League `curve` (and usually domain fields)
 * come from `league/{season}/w{week}/{group}.json` and are merged at load time.
 */
export type JsonStatSnapshot = {
  id: string;
  playerValue: number | null;
  percentile: number | null;
  qualified: boolean;
  denomYtd?: number;
  kind: "continuous" | "discrete";
  xMin?: number;
  xMax?: number;
  yMax?: number;
  lowerBound?: number;
  upperBound?: number;
  curve?: Point[];
  unavailableReason?: Exclude<StatAvailabilityStatus, "ready" | "pending">;
};

export type PlayerBio = {
  id: string;
  name: string;
  position: string;
  team: string;
  seasons: number[];
};

export type PlayerPageJson = {
  schemaVersion?: 1;
  player: PlayerBio;
  season: number;
  asOfWeek: number;
  stats: JsonStatSnapshot[];
};
