import { teamSwatchBackground } from "@/lib/team-colors";
import { cn } from "@/lib/utils";

/** Team abbreviation with a primary/secondary horizontal swatch. */
export function TeamAbbr({
  team,
  className,
}: {
  team: string;
  className?: string;
}) {
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <span
        className="size-2.5 shrink-0"
        style={{ background: teamSwatchBackground(team) }}
        aria-hidden
      />
      <span>{team}</span>
    </span>
  );
}
