import { Suspense } from "react";
import { loadCurrentSeasonContext } from "@/data/players";
import { PlayHighlightsLabClient } from "./PlayHighlightsLabClient";

const PLAY_HIGHLIGHTS_START_SEASON = 2016;

export default async function PlayHighlightsLabPage() {
  const { season, asOfWeek } = await loadCurrentSeasonContext();

  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-3xl px-4 py-8 text-sm text-muted-foreground">
          Loading play highlights…
        </div>
      }
    >
      <PlayHighlightsLabClient
        startSeason={PLAY_HIGHLIGHTS_START_SEASON}
        currentSeason={season}
        currentWeek={asOfWeek}
        initialSeason={season}
        initialWeek={asOfWeek}
      />
    </Suspense>
  );
}
