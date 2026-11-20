"use client";

import { PlayerComparisonLink } from "@/components/PlayerComparisonLink";
import { LeagueConnectForms, keepSelection, leagueControlClass as control, messageOf } from "@/components/league/LeagueConnectForms";
import { LeagueDistributions, PlayerCurve } from "./LeagueCharts";
import { useRos } from "@/components/projections/useRos";
import { fetchEspnLeague, normalizeEspn } from "@/lib/league/espn";
import { loadPlayerDirectory } from "@/lib/league/identity";
import { formatPct, formatPoints, formatRecord, methodCaveats, projectLeague, type LeagueProjection, type TeamProjection } from "@/lib/league/project";
import { importSleeperLeague } from "@/lib/league/sleeper";
import { leagueSettingsLabel, type LeagueStore } from "@/lib/league/store";
import { LeagueConnectError, type SavedLeague } from "@/lib/league/types";
import { useLeagueLabStore } from "@/lib/league/use-league-store";
import { useMemo, useRef, useState } from "react";

export function LeagueLabClient() {
  const { snapshot, error: rosError, retry } = useRos();
  const { store, league, save, unlink, activate } = useLeagueLabStore();
  const [working, setWorking] = useState("");
  const [error, setError] = useState("");
  const [confirmUnlink, setConfirmUnlink] = useState(false);
  const run = useRef(0);

  const projection = useMemo(() => (league && snapshot ? projectLeague(league, snapshot) : null), [league, snapshot]);

  function persist(next: SavedLeague) {
    setError("");
    setConfirmUnlink(false);
    return save(next);
  }

  async function guarded(action: () => Promise<void>) {
    const id = ++run.current;
    setError("");
    try {
      await action();
    } catch (cause) {
      if (run.current === id) setError(messageOf(cause));
    } finally {
      if (run.current === id) setWorking("");
    }
  }

  function refresh() {
    if (!league) return;
    setWorking("Refreshing the saved league…");
    void guarded(async () => {
      const identity = await loadPlayerDirectory();
      if (league.provider === "sleeper") {
        persist(keepSelection(league, await importSleeperLeague(league.providerLeagueId, null, identity)));
        return;
      }
      try {
        const raw = await fetchEspnLeague(league.providerLeagueId, league.season);
        persist(keepSelection(league, normalizeEspn(raw, { leagueId: league.providerLeagueId, season: league.season, identity })));
      } catch (cause) {
        if (cause instanceof LeagueConnectError && cause.code === "AUTH_REQUIRED") {
          setError("This ESPN league needs a fresh JSON import. Expand “Link another league” and paste or upload the league file.");
        }
        throw cause;
      }
    });
  }

  function chooseTeam(teamId: string) {
    if (!league) return;
    persist({ ...league, selectedTeamId: teamId || null, selectionSource: teamId ? "manual" : null });
  }

  const forms = (
    <LeagueConnectForms
      existingLeague={league}
      onSave={(next) => {
        setConfirmUnlink(false);
        return persist(next);
      }}
      onError={setError}
      working={working}
      setWorking={setWorking}
    />
  );

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-5 px-4 py-8">
      <header className="space-y-2">
        <p className="text-[11px] font-semibold tracking-[0.14em] text-muted-foreground uppercase">Lab · not in nav</p>
        <h1 className="text-2xl font-semibold tracking-tight">League</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Link one Sleeper or ESPN league in this browser. After that, the roster and schedule stay on this device. Rest-of-season projections already on the site estimate points for each team, with a rough chance of the best record and of scoring the most points.
        </p>
      </header>
      {error && (
        <p role="alert" className="border border-error-border bg-error-surface p-3 text-sm">
          {error}
        </p>
      )}
      {working && (
        <p role="status" className="text-sm text-muted-foreground">
          {working}
        </p>
      )}
      {league ? (
        <>
          <LeagueReport
            league={league}
            projection={projection}
            rosError={rosError}
            retry={retry}
            generatedAt={snapshot?.generatedAt ?? null}
            onTeam={chooseTeam}
            onRefresh={refresh}
            onUnlink={() => {
              if (!confirmUnlink) {
                setConfirmUnlink(true);
                return;
              }
              unlink(league.id);
              setConfirmUnlink(false);
            }}
            confirmUnlink={confirmUnlink}
            refreshing={!!working}
            store={store}
            onActivate={(id) => {
              setConfirmUnlink(false);
              activate(id);
            }}
          />
          <details className="border border-border bg-card p-3">
            <summary className="cursor-pointer text-sm font-semibold">Link another league</summary>
            <div className="mt-3">{forms}</div>
          </details>
        </>
      ) : (
        forms
      )}
      <Caveats items={projection?.caveats ?? methodCaveats(league)} />
    </main>
  );
}

function LeagueReport({
  league,
  projection,
  rosError,
  retry,
  generatedAt,
  onTeam,
  onRefresh,
  onUnlink,
  confirmUnlink,
  refreshing,
  store,
  onActivate,
}: {
  league: SavedLeague;
  projection: LeagueProjection | null;
  rosError: string;
  retry: () => void;
  generatedAt: string | null;
  onTeam: (teamId: string) => void;
  onRefresh: () => void;
  onUnlink: () => void;
  confirmUnlink: boolean;
  refreshing: boolean;
  store: LeagueStore;
  onActivate: (id: string) => void;
}) {
  const rows = new Map(projection?.teams.map((team) => [team.teamId, team]));
  const ordered = [...league.teams].sort((a, b) => {
    const left = rows.get(a.id)?.projectedPoints ?? rows.get(a.id)?.rosMean ?? Number.NEGATIVE_INFINITY;
    const right = rows.get(b.id)?.projectedPoints ?? rows.get(b.id)?.rosMean ?? Number.NEGATIVE_INFINITY;
    return right - left || a.name.localeCompare(b.name);
  });
  return (
    <section className="space-y-3" aria-label="Linked league">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">{league.name}</h2>
          <p className="text-sm text-muted-foreground">
            {league.provider === "sleeper" ? "Sleeper" : "ESPN"} · {league.season} · {leagueSettingsLabel(league.rosterSettings)} · Saved{" "}
            <time dateTime={league.importedAt}>{new Date(league.importedAt).toLocaleString()}</time>
            {league.asOfWeek ? ` · provider week ${league.asOfWeek}` : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={onRefresh} disabled={refreshing} className={control}>
            Refresh league
          </button>
          <button type="button" onClick={onUnlink} className={control}>
            {confirmUnlink ? "Confirm unlink" : "Unlink league"}
          </button>
        </div>
      </div>
      {store.leagues.length > 1 && (
        <label className="block text-xs font-semibold">
          Saved league
          <select value={league.id} onChange={(event) => onActivate(event.target.value)} className={`${control} mt-1 block`}>
            {store.leagues.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} · {item.season}
              </option>
            ))}
          </select>
        </label>
      )}
      <label className="block text-xs font-semibold">
        Your team
        <select aria-label="Your team" value={league.selectedTeamId ?? ""} onChange={(event) => onTeam(event.target.value)} className={`${control} mt-1 block max-w-full`}>
          <option value="">Select your team</option>
          {league.teams.map((team) => (
            <option key={team.id} value={team.id}>
              {team.name}
            </option>
          ))}
        </select>
      </label>
      {league.selectionSource === "sleeper-user" && (
        <p className="text-sm text-muted-foreground">Preselected from the Sleeper username. That match does not prove the team is yours, and you can change it.</p>
      )}
      {rosError && (
        <p role="alert" className="border border-error-border bg-error-surface p-3 text-sm">
          {rosError}{" "}
          <button type="button" onClick={retry} className="underline">
            Retry
          </button>
        </p>
      )}
      {!projection && !rosError && <p className="text-sm text-muted-foreground">Loading rest-of-season projections…</p>}
      {projection?.mode === "blocked" && (
        <p role="status" className="border border-warning-border bg-warning-surface p-3 text-sm text-warning-foreground">
          {projection.reason}
        </p>
      )}
      {projection && projection.mode !== "blocked" && (
        <p className="text-sm text-muted-foreground">
          {projection.mode === "simulated"
            ? `Record and title chances are from ${projection.sims.toLocaleString()} simulated seasons. The same draws are used each time this page is opened.`
            : projection.mode === "points-only"
              ? `Point-title chances are from ${projection.sims.toLocaleString()} draws. The saved schedule did not pair the remaining games, so record chances are omitted.`
              : projection.mode === "standings"
                ? "No regular-season games remain after the projection cutoff, so the title marks are the saved standings."
                : "These are rest-of-season lineup estimates only. They are not added to points already scored."}
          {generatedAt ? (
            <>
              {" "}
              Projections updated <time dateTime={generatedAt}>{new Date(generatedAt).toLocaleString()}</time>.
            </>
          ) : null}
        </p>
      )}
      <div className="overflow-x-auto border border-border">
        <table className="w-full min-w-[52rem] text-left text-sm">
          <caption className="sr-only">Projected fantasy standings</caption>
          <thead className="bg-card text-xs text-muted-foreground">
            <tr>
              <th className="p-2 font-semibold">Team</th>
              {projection && projection.mode !== "blocked" && <th className="p-2 font-semibold">Through week {projection.cutoffWeek}</th>}
              <th className="p-2 font-semibold">Rest of fantasy season</th>
              <th className="p-2 font-semibold">Projected points</th>
              <th className="p-2 font-semibold">Record outlook</th>
              <th className="p-2 font-semibold">P(best record)</th>
              <th className="p-2 font-semibold">P(most points)</th>
            </tr>
          </thead>
          <tbody>
            {ordered.map((team) => {
              const row = rows.get(team.id);
              return (
                <tr key={team.id} className={team.id === league.selectedTeamId ? "bg-muted" : undefined}>
                  <th scope="row" className="border-t border-border p-2 font-medium">
                    <span className="block">
                      {team.name}
                      {team.id === league.selectedTeamId ? " · yours" : ""}
                    </span>
                    <span className="block text-xs font-normal text-muted-foreground">
                      {team.manager} · saved {formatRecord(team.wins, team.losses, team.ties)} · {formatPoints(team.points)} pts
                    </span>
                    {row && <LineupDetails row={row} season={league.season} />}
                  </th>
                  {projection && projection.mode !== "blocked" && (
                    <td className="border-t border-border p-2 tabular-nums">
                      {row ? `${formatRecord(row.through.wins, row.through.losses, row.through.ties)} · ${formatPoints(row.through.points)}` : "—"}
                    </td>
                  )}
                  <td className="border-t border-border p-2 tabular-nums">
                    {row?.rosMean === null || row?.rosMean === undefined ? (
                      "—"
                    ) : (
                      <>
                        {formatPoints(row.rosMean)} <span className="text-xs text-muted-foreground">mean</span>
                        {row.rosMedianSum !== null && <span className="block text-xs text-muted-foreground">{formatPoints(row.rosMedianSum)} median sum</span>}
                      </>
                    )}
                  </td>
                  <td className="border-t border-border p-2 tabular-nums">
                    {row?.projectedPoints === null || row?.projectedPoints === undefined ? "—" : formatPoints(row.projectedPoints)}
                  </td>
                  <td className="border-t border-border p-2">
                    {row?.records.length ? (
                      <>
                        <span className="tabular-nums">
                          {row.records[0]!.label} {formatPct(row.records[0]!.probability)}
                        </span>
                        {row.expectedWins !== null && (
                          <span className="block text-xs text-muted-foreground">
                            Exp. wins {row.expectedWins.toFixed(1)}
                            {row.records.length > 1 ? ` · ${row.records.slice(1).map((record) => `${record.label} ${formatPct(record.probability)}`).join(" · ")}` : ""}
                          </span>
                        )}
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="border-t border-border p-2 tabular-nums">
                    {row?.pBestRecord === null || row?.pBestRecord === undefined ? "—" : formatPct(row.pBestRecord)}
                  </td>
                  <td className="border-t border-border p-2 tabular-nums">
                    {row?.pMostPoints === null || row?.pMostPoints === undefined ? "—" : formatPct(row.pMostPoints)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {projection && projection.mode !== "blocked" && <LeagueDistributions league={league} projection={projection} />}
    </section>
  );
}

function LineupDetails({ row, season }: { row: TeamProjection; season: number }) {
  const missing = row.unmapped.length + row.heldOut.length;
  return (
    <details className="mt-1 text-xs font-normal text-muted-foreground">
      <summary>{row.lineupError ?? `Lineup${missing ? ` · ${missing} not started` : ""}`}</summary>
      <ul className="mt-1 space-y-1">
        {row.lineup.map((spot, index) => (
          <li key={`${spot.slot}-${index}`}>
            {spot.slot}:{" "}
            {spot.player ? (
              <>
                <PlayerComparisonLink playerId={spot.player.playerId} season={season}>
                  {spot.player.name}
                </PlayerComparisonLink>{" "}
                {formatPoints(spot.player.mean)}
                {spot.rosterName ? ` (roster: ${spot.rosterName})` : ""}
                <PlayerCurve player={spot.player} />
              </>
            ) : (
              "empty"
            )}
          </li>
        ))}
        {row.benched.map((item) => (
          <li key={item.player.playerId}>
            {item.name} — Bench · {formatPoints(item.player.mean)}
            <PlayerCurve player={item.player} />
          </li>
        ))}
        {row.heldOut.map((item) => (
          <li key={item.name}>
            {item.name} — {item.detail}
          </li>
        ))}
        {row.unmapped.map((item) => (
          <li key={`${item.name}-${item.detail}`}>
            {item.name} — {item.detail}
          </li>
        ))}
      </ul>
    </details>
  );
}

function Caveats({ items }: { items: string[] }) {
  return (
    <section className="space-y-2 border border-border bg-card p-3" aria-labelledby="league-caveats">
      <h2 id="league-caveats" className="text-sm font-semibold">
        How to read this
      </h2>
      <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}
