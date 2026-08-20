import type { StatPayload } from "@/lib/distribution";

export function isStatReady(
  stat: StatPayload,
): stat is StatPayload & { playerValue: number; percentile: number } {
  return (
    stat.availability === "ready" &&
    stat.playerValue != null &&
    stat.percentile != null &&
    (stat.kind === "continuous" ? stat.curve.length > 0 : stat.bins.length > 0)
  );
}

export function availabilityCopy(stat: StatPayload): string {
  switch (stat.availability) {
    case "not_in_nflverse":
      return "Not available in public nflverse data — this row stays gray until a licensed source is wired in Ballnet.";
    case "missing_source":
      return "Source row is missing for this week. Missing is not treated as zero.";
    case "insufficient_sample":
      return stat.minN != null
        ? `Not enough sample yet. Needs ${stat.minN} ${stat.denom} (ramp–hold, held at 4× after week 4).`
        : "Not enough sample yet for a stable percentile.";
    case "pending":
      return "Waiting on a Ballnet snapshot. The row is listed so the position catalog is complete.";
    case "ready":
      return "";
  }
}
