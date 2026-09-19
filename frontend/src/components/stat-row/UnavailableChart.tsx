import { availabilityCopy } from "@/lib/stat-status";
import type { StatPayload } from "@/lib/distribution";

export function UnavailableChart({ stat }: { stat: StatPayload }) {
  return (
    <div className="flex min-h-16 items-center justify-center rounded-none border border-dashed border-zinc-200 bg-zinc-50 px-3 py-3 text-center text-xs leading-4 text-zinc-500">
      {availabilityCopy(stat)}
    </div>
  );
}
