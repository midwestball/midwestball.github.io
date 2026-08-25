import { statsForPosition, type StatDefinition } from "@/lib/catalog";
import type { StatAvailabilityStatus, StatPayload } from "@/lib/distribution";
import type { JsonStatSnapshot } from "@/lib/payload";

function availabilityFor(
  definition: StatDefinition,
  snapshot: JsonStatSnapshot | undefined,
): StatAvailabilityStatus {
  if (definition.alwaysUnavailable) return "not_in_nflverse";
  if (!snapshot) return "pending";
  if (snapshot.unavailableReason) return snapshot.unavailableReason;
  if (!snapshot.qualified) return "insufficient_sample";
  return Boolean(snapshot.curve?.length) ? "ready" : "pending";
}

export function hydratePlayerStats(
  position: string,
  snapshots: JsonStatSnapshot[] = [],
): StatPayload[] {
  const byId = new Map(snapshots.map((snapshot) => [snapshot.id, snapshot]));

  return statsForPosition(position).map((definition) => {
    const snapshot = byId.get(definition.id);
    const availability = availabilityFor(definition, snapshot);

    return {
      id: definition.id,
      label: definition.label,
      section: definition.section,
      higherIsBetter: definition.higherIsBetter,
      format: definition.format,
      availability,
      minN: definition.minNBase,
      denom: definition.denom,
      xMin: snapshot?.xMin ?? definition.xMin,
      xMax: snapshot?.xMax ?? definition.xMax,
      yMax: snapshot?.yMax ?? 1,
      playerValue: snapshot?.playerValue ?? null,
      percentile: snapshot?.percentile ?? null,
      curve: snapshot?.curve ?? [],
      kind: definition.kind,
      lowerBound: snapshot?.lowerBound ?? definition.lowerBound,
      upperBound: snapshot?.upperBound ?? definition.upperBound,
    };
  });
}
