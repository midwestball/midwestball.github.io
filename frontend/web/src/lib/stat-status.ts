import type { StatPayload } from "@/lib/distribution";

export function isStatReady(
  stat: StatPayload,
): stat is StatPayload & { playerValue: number; percentile: number } {
  return (
    stat.availability === "ready" &&
    stat.playerValue != null &&
    stat.percentile != null &&
    stat.curve.length > 0
  );
}

export function availabilityCopy(stat: StatPayload): string {
  switch (stat.availability) {
    case "not_in_nflverse":
      return "Not available in public data.";
    case "missing_source":
      return "Source data is missing for this week.";
    case "insufficient_sample":
      return stat.minN != null
        ? `Not enough sample yet. Needs ${stat.minN} ${stat.denom}`
        : "Not enough sample yet for a stable percentile.";
    case "pending":
      return "Waiting on an update. The row is listed so the position catalog is complete.";
    case "ready":
      return "";
  }
}
