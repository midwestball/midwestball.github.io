export const ROS_POSITIONS = ["QB", "RB", "WR", "TE"] as const;
export type RosPosition = (typeof ROS_POSITIONS)[number];
export type RosPlayer = {
  playerId: string;
  name: string;
  position: RosPosition;
  team: string;
  remainingTeamGames: number;
  mean: number;
  quantiles: [number, number, number, number, number];
};
export type RosSnapshot = {
  schemaVersion: 1;
  kind: "ros";
  snapshotId: string;
  season: number;
  cutoffWeek: number;
  generatedAt: string;
  modelVersion: string;
  scoringProfile: "ppr-v1";
  quantileLevels: number[];
  methodology: string;
  entities: RosPlayer[];
};

const object = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null;
const text = (v: unknown): v is string => typeof v === "string" && v.length > 0;
const nonnegative = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v) && v >= 0;
export function isRosSnapshot(v: unknown): v is RosSnapshot {
  if (!object(v) || v.schemaVersion !== 1 || v.kind !== "ros" || !text(v.snapshotId) ||
      !Number.isInteger(v.season) || !Number.isInteger(v.cutoffWeek) || (v.cutoffWeek as number) < 0 ||
      (v.cutoffWeek as number) > 17 || !text(v.generatedAt) || !text(v.modelVersion) ||
      v.scoringProfile !== "ppr-v1" || !text(v.methodology) ||
      JSON.stringify(v.quantileLevels) !== "[0.05,0.25,0.5,0.75,0.95]" ||
      !Array.isArray(v.entities) || v.entities.length < 4) return false;
  const ids = new Set<string>();
  const positions = new Set<string>();
  const valid = v.entities.every((p: unknown) => {
    if (!object(p) || !text(p.playerId) || ids.has(p.playerId) || !text(p.name) || !text(p.team) ||
        !(ROS_POSITIONS as readonly unknown[]).includes(p.position) || !nonnegative(p.mean) ||
        !Number.isInteger(p.remainingTeamGames) || (p.remainingTeamGames as number) < 1 ||
        (p.remainingTeamGames as number) > 17 || !Array.isArray(p.quantiles) || p.quantiles.length !== 5 ||
        !p.quantiles.every((q, i, a) => nonnegative(q) && (i === 0 || q >= a[i - 1]))) return false;
    ids.add(p.playerId); positions.add(p.position as string); return true;
  });
  return valid && ROS_POSITIONS.every(p => positions.has(p));
}

export const rosMedian = (p: RosPlayer) => p.quantiles[2];
