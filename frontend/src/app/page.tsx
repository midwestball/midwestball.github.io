import { Suspense } from "react";
import { loadCurrentSeasonContext } from "@/data/players";
import {
  HighlightsBrowser,
} from "@/components/highlights/HighlightsBrowser";

const HIGHLIGHTS_START_SEASON = 2016;

export default async function Home() {
  const { season, asOfWeek } = await loadCurrentSeasonContext();

  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-3xl px-4 py-8 text-sm text-zinc-500">
          Loading highlights…
        </div>
      }
    >
      <HighlightsBrowser
        startSeason={HIGHLIGHTS_START_SEASON}
        currentSeason={season}
        currentWeek={asOfWeek}
        initialSeason={season}
        initialWeek={asOfWeek}
      />
    </Suspense>
  );
}
