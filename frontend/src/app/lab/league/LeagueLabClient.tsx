"use client";

import { PlayerComparisonLink } from "@/components/PlayerComparisonLink";
import { LeagueDistributions, PlayerCurve } from "./LeagueCharts";
import { useRos } from "@/components/projections/useRos";
import { fetchEspnLeague, normalizeEspn, parseEspnLeagueReference, parseEspnPaste, espnLeagueUrl } from "@/lib/league/espn";
import { loadPlayerDirectory } from "@/lib/league/identity";
import { formatPct, formatPoints, formatRecord, methodCaveats, projectLeague, type LeagueProjection, type TeamProjection } from "@/lib/league/project";
import { discoverSleeperLeagues, importSleeperLeague, type SleeperLeagueSummary } from "@/lib/league/sleeper";
import { EMPTY_LEAGUE_STORE, LEAGUE_STORAGE_KEY, leagueSettingsLabel, parseLeagueStore, removeLeague, saveLeagueStore, upsertLeague, type LeagueStore } from "@/lib/league/store";
import { LeagueConnectError, type SavedLeague } from "@/lib/league/types";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

const STORAGE_EVENT = "midwestball-league-lab-change";
const control = "border border-border bg-card px-2 py-1 text-sm";
const primary = "border border-ring bg-primary px-3 py-1 text-sm font-semibold text-primary-foreground disabled:opacity-60";

function keepSelection(previous: SavedLeague, next: SavedLeague): SavedLeague {
  if (previous.selectedTeamId && next.teams.some((team) => team.id === previous.selectedTeamId)) {
    return { ...next, selectedTeamId: previous.selectedTeamId, selectionSource: previous.selectionSource };
  }
  return next;
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "The league didn't load.";
}

function readFileText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : "");
    reader.onerror = () => reject(new LeagueConnectError("INVALID", "Could not read that league file."));
    reader.readAsText(file);
  });
}

function subscribeToLeagueStore(callback: () => void) {
  window.addEventListener(STORAGE_EVENT, callback);
  window.addEventListener("storage", callback);
  return () => {
    window.removeEventListener(STORAGE_EVENT, callback);
    window.removeEventListener("storage", callback);
  };
}

function readLeagueStore(): string {
  try { return localStorage.getItem(LEAGUE_STORAGE_KEY) ?? ""; }
  catch { return ""; }
}

export function LeagueLabClient() {
  const { snapshot, error: rosError, retry } = useRos();
  const rawStore = useSyncExternalStore(subscribeToLeagueStore, readLeagueStore, () => "");
  const store = useMemo(() => {
    if (!rawStore) return EMPTY_LEAGUE_STORE;
    try { return parseLeagueStore(JSON.parse(rawStore)); }
    catch { return EMPTY_LEAGUE_STORE; }
  }, [rawStore]);
  const [working, setWorking] = useState("");
  const [error, setError] = useState("");
  const [confirmUnlink, setConfirmUnlink] = useState(false);
  const [sleeperName, setSleeperName] = useState("");
  const [sleeperSeason, setSleeperSeason] = useState(2026);
  const [espnSeason, setEspnSeason] = useState(2026);
  const [espnInput, setEspnInput] = useState("");
  const [paste, setPaste] = useState("");
  const [showPaste, setShowPaste] = useState(false);
  const [espnImport, setEspnImport] = useState<"paste" | "file">("paste");
  const [espnFile, setEspnFile] = useState<File | null>(null);
  const [found, setFound] = useState<{ userId: string; leagues: SleeperLeagueSummary[] } | null>(null);
  const seasonsTouched = useRef(false);
  const run = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    fetch("https://api.sleeper.app/v1/state/nfl", { signal: controller.signal })
      .then((response) => response.json())
      .then((body: { season?: unknown }) => {
        if (seasonsTouched.current || typeof body.season !== "string" || !/^\d{4}$/.test(body.season)) return;
        const season = Number(body.season);
        setSleeperSeason(season);
        setEspnSeason(season);
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  const league = store.leagues.find((item) => item.id === store.activeId) ?? null;
  const projection = useMemo(() => (league && snapshot ? projectLeague(league, snapshot) : null), [league, snapshot]);

  function commit(next: LeagueStore) {
    if (!saveLeagueStore(next)) {
      setError("This browser couldn't save the league locally.");
      return;
    }
    window.dispatchEvent(new Event(STORAGE_EVENT));
  }

  function save(next: SavedLeague) {
    setError("");
    setConfirmUnlink(false);
    setPaste("");
    setEspnFile(null);
    commit(upsertLeague(store, next));
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

  function findSleeper() {
    setWorking("Looking up that Sleeper username…");
    setFound(null);
    void guarded(async () => {
      const result = await discoverSleeperLeagues(sleeperName, sleeperSeason);
      setFound({ userId: result.userId, leagues: result.leagues });
      if (!result.leagues.length) setError(`No NFL leagues for that username in ${sleeperSeason}.`);
    });
  }

  function connectSleeper(leagueId: string) {
    setWorking("Loading the league and the player directory…");
    void guarded(async () => {
      const identity = await loadPlayerDirectory();
      const next = await importSleeperLeague(leagueId, found?.userId ?? null, identity);
      save(league && league.id === next.id ? keepSelection(league, next) : next);
      setFound(null);
    });
  }

  function connectEspn() {
    setWorking("Reading that ESPN league…");
    void guarded(async () => {
      const { leagueId } = parseEspnLeagueReference(espnInput, espnSeason);
      const identity = await loadPlayerDirectory();
      try {
        const raw = await fetchEspnLeague(leagueId, espnSeason);
        const next = normalizeEspn(raw, { leagueId, season: espnSeason, identity });
        save(league && league.id === next.id ? keepSelection(league, next) : next);
        setShowPaste(false);
      } catch (cause) {
        if (cause instanceof LeagueConnectError && cause.code === "AUTH_REQUIRED") setShowPaste(true);
        throw cause;
      }
    });
  }

  async function readEspnImport(text: string) {
    const { leagueId } = parseEspnLeagueReference(espnInput, espnSeason);
    const identity = await loadPlayerDirectory();
    save(parseEspnPaste(text, { leagueId, season: espnSeason, identity }));
    setShowPaste(false);
  }

  function importPaste() {
    setWorking("Reading the pasted league…");
    void guarded(() => readEspnImport(paste));
  }

  function importFile() {
    const file = espnFile;
    if (!file) {
      setError("Choose a league JSON file first.");
      return;
    }
    setWorking("Reading the league file…");
    void guarded(async () => {
      await readEspnImport(await readFileText(file));
    });
  }

  function refresh() {
    if (!league) return;
    setWorking("Refreshing the saved league…");
    void guarded(async () => {
      const identity = await loadPlayerDirectory();
      if (league.provider === "sleeper") {
        save(keepSelection(league, await importSleeperLeague(league.providerLeagueId, null, identity)));
        return;
      }
      try {
        const raw = await fetchEspnLeague(league.providerLeagueId, league.season);
        save(keepSelection(league, normalizeEspn(raw, { leagueId: league.providerLeagueId, season: league.season, identity })));
      } catch (cause) {
        if (cause instanceof LeagueConnectError && cause.code === "AUTH_REQUIRED") {
          setEspnInput(league.providerLeagueId);
          setEspnSeason(league.season);
          setShowPaste(true);
        }
        throw cause;
      }
    });
  }

  function chooseTeam(teamId: string) {
    if (!league) return;
    save({ ...league, selectedTeamId: teamId || null, selectionSource: teamId ? "manual" : null });
  }

  const forms = <div className="grid gap-4 lg:grid-cols-2">
    <form className="space-y-3 border border-border bg-card p-3" onSubmit={(event) => { event.preventDefault(); findSleeper(); }}>
      <h2 className="text-lg font-semibold">Sleeper</h2>
      <p className="text-sm text-muted-foreground">Enter a username. No password. The username does not prove you own a team.</p>
      <label className="block text-xs font-semibold">Sleeper username
        <input value={sleeperName} autoComplete="off" onChange={(event) => setSleeperName(event.target.value)} className={`${control} mt-1 w-full`} />
      </label>
      <label className="block text-xs font-semibold">Season
        <input type="number" min={2017} max={2035} value={sleeperSeason} onChange={(event) => { seasonsTouched.current = true; setSleeperSeason(Number(event.target.value)); }} className={`${control} mt-1 w-28`} />
      </label>
      <button type="submit" disabled={!!working || !sleeperName.trim()} className={primary}>Find leagues</button>
      {found && found.leagues.length > 0 && <ul className="space-y-2">
        {found.leagues.map((item) => <li key={item.id}><button type="button" disabled={!!working} onClick={() => connectSleeper(item.id)} className={`${control} w-full text-left`}>Import {item.name} · {item.teams} teams{item.status ? ` · ${item.status}` : ""}</button></li>)}
      </ul>}
    </form>
    <form className="space-y-3 border border-border bg-card p-3" onSubmit={(event) => { event.preventDefault(); connectEspn(); }}>
      <h2 className="text-lg font-semibold">ESPN</h2>
      <p className="text-sm text-muted-foreground">Paste a fantasy.espn.com league link or a numeric league ID. A public league loads directly. Session cookies are not accepted on this static page and are never saved.</p>
      <label className="block text-xs font-semibold">ESPN league URL or ID
        <input value={espnInput} autoComplete="off" onChange={(event) => setEspnInput(event.target.value)} className={`${control} mt-1 w-full`} />
      </label>
      <label className="block text-xs font-semibold">Season
        <input type="number" min={2017} max={2035} value={espnSeason} onChange={(event) => { seasonsTouched.current = true; setEspnSeason(Number(event.target.value)); }} className={`${control} mt-1 w-28`} />
      </label>
      <button type="submit" disabled={!!working || !espnInput.trim()} className={primary}>Link league</button>
      <p className="text-sm text-muted-foreground">If the league is private, a commissioner can make it viewable, or you can open the read-only URL while logged into ESPN and import the JSON once. That import stores the league, not your cookies. <a className="underline" href="https://support.espn.com/hc/en-us/articles/360000991871-Making-a-Private-League-Viewable-to-the-Public" target="_blank" rel="noreferrer">ESPN public-view setting</a></p>
      {(showPaste || paste || espnFile) && <>
        <p className="text-sm">Open <EspnDataLink input={espnInput} season={espnSeason} /> while logged in. Paste the JSON, or save the response and choose the file.</p>
        <div className="flex gap-2" role="group" aria-label="How to add the ESPN JSON">
          <button type="button" aria-pressed={espnImport === "paste"} onClick={() => setEspnImport("paste")} className={espnImport === "paste" ? "border border-ring bg-muted px-2 py-1 text-sm font-semibold" : control}>Paste JSON</button>
          <button type="button" aria-pressed={espnImport === "file"} onClick={() => setEspnImport("file")} className={espnImport === "file" ? "border border-ring bg-muted px-2 py-1 text-sm font-semibold" : control}>JSON file</button>
        </div>
        {espnImport === "paste" ? <>
          <label className="block text-xs font-semibold">ESPN league JSON
            <textarea value={paste} spellCheck={false} autoComplete="off" rows={6} onChange={(event) => setPaste(event.target.value)} className={`${control} mt-1 w-full font-mono`} />
          </label>
          <button type="button" disabled={!!working || !paste.trim()} onClick={importPaste} className={primary}>Import pasted league</button>
        </> : <>
          <label className="block text-xs font-semibold">League JSON file
            <input type="file" accept="application/json,.json" onChange={(event) => setEspnFile(event.target.files?.[0] ?? null)} className={`${control} mt-1 block w-full`} />
          </label>
          {espnFile && <p className="text-xs text-muted-foreground">Selected {espnFile.name}</p>}
          <button type="button" disabled={!!working || !espnFile} onClick={importFile} className={primary}>Import league file</button>
        </>}
      </>}
    </form>
  </div>;

  return <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-5 px-4 py-8">
    <header className="space-y-2">
      <p className="text-[11px] font-semibold tracking-[0.14em] text-muted-foreground uppercase">Lab · not in nav</p>
      <h1 className="text-2xl font-semibold tracking-tight">League</h1>
      <p className="max-w-3xl text-sm text-muted-foreground">Link one Sleeper or ESPN league in this browser. After that, the roster and schedule stay on this device. Rest-of-season projections already on the site estimate points for each team, with a rough chance of the best record and of scoring the most points.</p>
    </header>
    {error && <p role="alert" className="border border-error-border bg-error-surface p-3 text-sm">{error}</p>}
    {working && <p role="status" className="text-sm text-muted-foreground">{working}</p>}
    {league ? <>
      <LeagueReport league={league} projection={projection} rosError={rosError} retry={retry} generatedAt={snapshot?.generatedAt ?? null} onTeam={chooseTeam} onRefresh={refresh} onUnlink={() => {
        if (!confirmUnlink) { setConfirmUnlink(true); return; }
        commit(removeLeague(store, league.id));
        setConfirmUnlink(false);
      }} confirmUnlink={confirmUnlink} refreshing={!!working} store={store} onActivate={(id) => { setConfirmUnlink(false); commit({ ...store, activeId: id }); }} />
      <details className="border border-border bg-card p-3"><summary className="cursor-pointer text-sm font-semibold">Link another league</summary><div className="mt-3">{forms}</div></details>
    </> : forms}
    <Caveats items={projection?.caveats ?? methodCaveats(league)} />
  </main>;
}

function EspnDataLink({ input, season }: { input: string; season: number }) {
  let href = "";
  try { href = espnLeagueUrl(parseEspnLeagueReference(input, season).leagueId, season); } catch { href = ""; }
  return href ? <a className="underline" href={href} target="_blank" rel="noreferrer">the ESPN league data</a> : <span>the ESPN league data</span>;
}

function LeagueReport({ league, projection, rosError, retry, generatedAt, onTeam, onRefresh, onUnlink, confirmUnlink, refreshing, store, onActivate }: {
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
  return <section className="space-y-3" aria-label="Linked league">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="text-xl font-semibold">{league.name}</h2>
        <p className="text-sm text-muted-foreground">{league.provider === "sleeper" ? "Sleeper" : "ESPN"} · {league.season} · {leagueSettingsLabel(league.rosterSettings)} · Saved <time dateTime={league.importedAt}>{new Date(league.importedAt).toLocaleString()}</time>{league.asOfWeek ? ` · provider week ${league.asOfWeek}` : ""}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={onRefresh} disabled={refreshing} className={control}>Refresh league</button>
        <button type="button" onClick={onUnlink} className={control}>{confirmUnlink ? "Confirm unlink" : "Unlink league"}</button>
      </div>
    </div>
    {store.leagues.length > 1 && <label className="block text-xs font-semibold">Saved league
      <select value={league.id} onChange={(event) => onActivate(event.target.value)} className={`${control} mt-1 block`}>{store.leagues.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.season}</option>)}</select>
    </label>}
    <label className="block text-xs font-semibold">Your team
      <select aria-label="Your team" value={league.selectedTeamId ?? ""} onChange={(event) => onTeam(event.target.value)} className={`${control} mt-1 block max-w-full`}>
        <option value="">Select your team</option>
        {league.teams.map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}
      </select>
    </label>
    {league.selectionSource === "sleeper-user" && <p className="text-sm text-muted-foreground">Preselected from the Sleeper username. That match does not prove the team is yours, and you can change it.</p>}
    {rosError && <p role="alert" className="border border-error-border bg-error-surface p-3 text-sm">{rosError} <button type="button" onClick={retry} className="underline">Retry</button></p>}
    {!projection && !rosError && <p className="text-sm text-muted-foreground">Loading rest-of-season projections…</p>}
    {projection?.mode === "blocked" && <p role="status" className="border border-warning-border bg-warning-surface p-3 text-sm text-warning-foreground">{projection.reason}</p>}
    {projection && projection.mode !== "blocked" && <p className="text-sm text-muted-foreground">{projection.mode === "simulated" ? `Record and title chances are from ${projection.sims.toLocaleString()} simulated seasons. The same draws are used each time this page is opened.` : projection.mode === "points-only" ? `Point-title chances are from ${projection.sims.toLocaleString()} draws. The saved schedule did not pair the remaining games, so record chances are omitted.` : projection.mode === "standings" ? "No regular-season games remain after the projection cutoff, so the title marks are the saved standings." : "These are rest-of-season lineup estimates only. They are not added to points already scored."}{generatedAt ? <> Projections updated <time dateTime={generatedAt}>{new Date(generatedAt).toLocaleString()}</time>.</> : null}</p>}
    <div className="overflow-x-auto border border-border">
      <table className="w-full min-w-[52rem] text-left text-sm">
        <caption className="sr-only">Projected fantasy standings</caption>
        <thead className="bg-card text-xs text-muted-foreground"><tr>
          <th className="p-2 font-semibold">Team</th>
          {projection && projection.mode !== "blocked" && <th className="p-2 font-semibold">Through week {projection.cutoffWeek}</th>}
          <th className="p-2 font-semibold">Rest of fantasy season</th>
          <th className="p-2 font-semibold">Projected points</th>
          <th className="p-2 font-semibold">Record outlook</th>
          <th className="p-2 font-semibold">P(best record)</th>
          <th className="p-2 font-semibold">P(most points)</th>
        </tr></thead>
        <tbody>
          {ordered.map((team) => {
            const row = rows.get(team.id);
            return <tr key={team.id} className={team.id === league.selectedTeamId ? "bg-muted" : undefined}>
              <th scope="row" className="border-t border-border p-2 font-medium">
                <span className="block">{team.name}{team.id === league.selectedTeamId ? " · yours" : ""}</span>
                <span className="block text-xs font-normal text-muted-foreground">{team.manager} · saved {formatRecord(team.wins, team.losses, team.ties)} · {formatPoints(team.points)} pts</span>
                {row && <LineupDetails row={row} season={league.season} />}
              </th>
              {projection && projection.mode !== "blocked" && <td className="border-t border-border p-2 tabular-nums">{row ? `${formatRecord(row.through.wins, row.through.losses, row.through.ties)} · ${formatPoints(row.through.points)}` : "—"}</td>}
              <td className="border-t border-border p-2 tabular-nums">{row?.rosMean === null || row?.rosMean === undefined ? "—" : <>{formatPoints(row.rosMean)} <span className="text-xs text-muted-foreground">mean</span>{row.rosMedianSum !== null && <span className="block text-xs text-muted-foreground">{formatPoints(row.rosMedianSum)} median sum</span>}</>}</td>
              <td className="border-t border-border p-2 tabular-nums">{row?.projectedPoints === null || row?.projectedPoints === undefined ? "—" : formatPoints(row.projectedPoints)}</td>
              <td className="border-t border-border p-2">{row?.records.length ? <><span className="tabular-nums">{row.records[0]!.label} {formatPct(row.records[0]!.probability)}</span>{row.expectedWins !== null && <span className="block text-xs text-muted-foreground">Exp. wins {row.expectedWins.toFixed(1)}{row.records.length > 1 ? ` · ${row.records.slice(1).map((record) => `${record.label} ${formatPct(record.probability)}`).join(" · ")}` : ""}</span>}</> : "—"}</td>
              <td className="border-t border-border p-2 tabular-nums">{row?.pBestRecord === null || row?.pBestRecord === undefined ? "—" : formatPct(row.pBestRecord)}</td>
              <td className="border-t border-border p-2 tabular-nums">{row?.pMostPoints === null || row?.pMostPoints === undefined ? "—" : formatPct(row.pMostPoints)}</td>
            </tr>;
          })}
        </tbody>
      </table>
    </div>
    {projection && projection.mode !== "blocked" && <LeagueDistributions league={league} projection={projection} />}
  </section>;
}

function LineupDetails({ row, season }: { row: TeamProjection; season: number }) {
  const missing = row.unmapped.length + row.heldOut.length;
  return <details className="mt-1 text-xs font-normal text-muted-foreground">
    <summary>{row.lineupError ?? `Lineup${missing ? ` · ${missing} not started` : ""}`}</summary>
    <ul className="mt-1 space-y-1">
      {row.lineup.map((spot, index) => <li key={`${spot.slot}-${index}`}>{spot.slot}: {spot.player ? <><PlayerComparisonLink playerId={spot.player.playerId} season={season}>{spot.player.name}</PlayerComparisonLink> {formatPoints(spot.player.mean)}{spot.rosterName ? ` (roster: ${spot.rosterName})` : ""}<PlayerCurve player={spot.player} /></> : "empty"}</li>)}
      {row.benched.map((item) => <li key={item.player.playerId}>{item.name} — Bench · {formatPoints(item.player.mean)}<PlayerCurve player={item.player} /></li>)}
      {row.heldOut.map((item) => <li key={item.name}>{item.name} — {item.detail}</li>)}
      {row.unmapped.map((item) => <li key={`${item.name}-${item.detail}`}>{item.name} — {item.detail}</li>)}
    </ul>
  </details>;
}

function Caveats({ items }: { items: string[] }) {
  return <section className="space-y-2 border border-border bg-card p-3" aria-labelledby="league-caveats">
    <h2 id="league-caveats" className="text-sm font-semibold">How to read this</h2>
    <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">{items.map((item) => <li key={item}>{item}</li>)}</ul>
  </section>;
}
