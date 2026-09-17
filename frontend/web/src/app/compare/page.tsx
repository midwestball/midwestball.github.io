import {
  GROUP_LABEL,
  isPositionCode,
  positionGroupOf,
} from "@/lib/catalog";
import { hydratePlayerStats } from "@/lib/catalog/hydrate";
import {
  loadCurrentSeasonContext,
  loadPlayerIndex,
  loadPublishedSeasons,
} from "@/data/players";
import { loadHydratedPlayerSnapshots } from "@/lib/ballnet-store";
import {
  CompareBoard,
  type CompareColumn,
} from "@/components/compare/CompareBoard";
import { ComparePicker } from "@/components/compare/ComparePicker";

export const revalidate = 3600;

const MAX_PLAYERS = 4;

function parsePlayerIds(raw: string | undefined): string[] {
  if (!raw) return [];
  const seen = new Set<string>();
  const ids: string[] = [];
  for (const part of raw.split(",")) {
    const id = part.trim();
    if (!id || seen.has(id)) continue;
    seen.add(id);
    ids.push(id);
    if (ids.length >= MAX_PLAYERS) break;
  }
  return ids;
}

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ p?: string; season?: string }>;
}) {
  const { p, season: seasonParam } = await searchParams;
  const selectedIds = parsePlayerIds(p);

  const [index, { season: currentSeason }, publishedSeasons] =
    await Promise.all([
      loadPlayerIndex(),
      loadCurrentSeasonContext(),
      loadPublishedSeasons(),
    ]);

  const seasonOptions = publishedSeasons.map((row) => row.season);
  const requested = Number(seasonParam);
  const season = seasonOptions.includes(requested)
    ? requested
    : currentSeason;

  const selectedBios = selectedIds
    .map((id) => index.find((player) => player.id === id))
    .filter((player): player is NonNullable<typeof player> => Boolean(player));

  const groups = new Set(
    selectedBios
      .filter((player) => isPositionCode(player.position))
      .map((player) => positionGroupOf(player.position)),
  );
  const sameGroup = groups.size <= 1;
  const positionGroup = sameGroup ? [...groups][0] : undefined;

  const columns: CompareColumn[] = [];
  if (sameGroup && positionGroup) {
    const loaded = await Promise.all(
      selectedBios.map(async (bio) => {
        const { page, snapshots } = await loadHydratedPlayerSnapshots(
          bio.id,
          positionGroup,
          { season },
        );
        const position = page?.player.position ?? bio.position;
        const team = page?.player.team ?? bio.team;
        return {
          playerId: bio.id,
          name: bio.name,
          position,
          team,
          stats: hydratePlayerStats(position, snapshots),
        } satisfies CompareColumn;
      }),
    );
    columns.push(...loaded);
  }

  const groupLabel =
    positionGroup != null ? GROUP_LABEL[positionGroup] : null;

  return (
    <div>
      <div className="border-b border-zinc-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-5">
          <p className="text-xs font-semibold tracking-[0.2em] text-zinc-500 uppercase">
            Players
          </p>
          <h1 className="mt-0.5 text-3xl font-semibold tracking-tight">
            Compare
          </h1>
          <p className="mt-1 max-w-xl text-sm leading-5 text-zinc-600">
            Place up to four players side by side. Expand a row for one shared
            league plot with team-colored markers
            {groupLabel ? ` · ${groupLabel}` : ""}.
          </p>
        </div>
      </div>

      <main className="mx-auto max-w-6xl space-y-4 px-4 py-4">
        <div className="rounded-none border border-zinc-200 bg-white px-3 py-3">
          <ComparePicker
            players={index}
            selectedIds={selectedBios.map((p) => p.id)}
            season={season}
            seasons={seasonOptions}
          />
        </div>

        {!sameGroup ? (
          <div className="rounded-none border border-zinc-200 bg-white px-3 py-4 text-sm leading-5 text-zinc-600">
            Compare requires players from the same position group. Remove a
            player or pick a matching group.
          </div>
        ) : columns.length === 0 ? (
          <div className="rounded-none border border-zinc-200 bg-white px-3 py-4 text-sm leading-5 text-zinc-600">
            Select players above to align their percentile sliders and league
            distributions.
          </div>
        ) : (
          <div className="rounded-none border border-zinc-200 bg-white">
            <CompareBoard columns={columns} />
          </div>
        )}
      </main>
    </div>
  );
}
