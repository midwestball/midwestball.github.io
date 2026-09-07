export type PositionGroup =
  | "qb"
  | "backfield"
  | "pass_catcher"
  | "ol"
  | "def_front"
  | "secondary"
  | "kicker"
  | "punter"
  | "returner";

export type PositionCode =
  | "QB"
  | "RB"
  | "FB"
  | "WR"
  | "TE"
  | "T"
  | "OT"
  | "G"
  | "OG"
  | "C"
  | "ED"
  | "EDGE"
  | "DE"
  | "DT"
  | "NT"
  | "LB"
  | "ILB"
  | "OLB"
  | "CB"
  | "FS"
  | "SS"
  | "S"
  | "K"
  | "P"
  | "KR"
  | "PR";

export type ValueFormat =
  | "count"
  | "yards"
  | "one_decimal"
  | "two_decimal"
  | "percent"
  | "percent_pts"
  | "rating"
  | "seconds"
  | "ratio";

export type ZeroMass = "none" | "low" | "med" | "high";

export type StatDefinition = {
  id: string;
  label: string;
  section: string;
  kind: "continuous" | "discrete";
  higherIsBetter: boolean;
  format: ValueFormat;
  xMin: number;
  xMax: number;
  lowerBound?: number;
  upperBound?: number;
  binWidth?: number;
  /** Ramp–hold n_base. Null means the row is permanently unavailable. */
  minNBase: number | null;
  denom: string;
  /**
   * Sibling counting-stat id for search min-volume (e.g. fg_pct → fg_attempts).
   * Absent for NGS-week / games / snaps / dropbacks / air-yards denoms with no published volume sibling.
   */
  volumeStatId?: string;
  source: string;
  startYear: number | null;
  zeroMass: ZeroMass;
  alwaysUnavailable?: boolean;
};
