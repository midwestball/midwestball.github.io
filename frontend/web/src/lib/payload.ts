import type {
  HistogramBin,
  Point,
  StatAvailabilityStatus,
} from "@/lib/distribution";

/**
 * JSON Ballnet will publish per player-season. Display formatting lives in
 * the Knowball catalog (`format` enum), not in this payload.
 */
export type JsonStatSnapshot = {
  id: string;
  playerValue: number;
  percentile: number;
  qualified: boolean;
  denomYtd?: number;
  kind: "continuous" | "discrete";
  xMin: number;
  xMax: number;
  yMax: number;
  lowerBound?: number;
  upperBound?: number;
  binWidth?: number;
  curve?: Point[];
  bins?: HistogramBin[];
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
  player: PlayerBio;
  season: number;
  asOfWeek: number;
  stats: JsonStatSnapshot[];
};
