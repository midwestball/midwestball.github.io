"use client";

import { useEffect, useRef, useState } from "react";
import { fetchEspnLeague, normalizeEspn, parseEspnLeagueReference, parseEspnPaste, espnLeagueUrl } from "@/lib/league/espn";
import { loadPlayerDirectory } from "@/lib/league/identity";
import { discoverSleeperLeagues, importSleeperLeague, type SleeperLeagueSummary } from "@/lib/league/sleeper";
import { LeagueConnectError, type SavedLeague } from "@/lib/league/types";

const control = "border border-border bg-card px-2 py-1 text-sm";
const primary = "border border-ring bg-primary px-3 py-1 text-sm font-semibold text-primary-foreground disabled:opacity-60";

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

function keepSelection(previous: SavedLeague, next: SavedLeague): SavedLeague {
  if (previous.selectedTeamId && next.teams.some((team) => team.id === previous.selectedTeamId)) {
    return { ...next, selectedTeamId: previous.selectedTeamId, selectionSource: previous.selectionSource };
  }
  return next;
}

export type LeagueConnectFormsProps = {
  existingLeague: SavedLeague | null;
  onSave: (league: SavedLeague) => boolean;
  onError: (message: string) => void;
  working: string;
  setWorking: (value: string) => void;
};

export function LeagueConnectForms({ existingLeague, onSave, onError, working, setWorking }: LeagueConnectFormsProps) {
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

  function save(next: SavedLeague) {
    onError("");
    setPaste("");
    setEspnFile(null);
    const payload = existingLeague && existingLeague.id === next.id ? keepSelection(existingLeague, next) : next;
    if (!onSave(payload)) onError("This browser couldn't save the league locally.");
  }

  async function guarded(action: () => Promise<void>) {
    const id = ++run.current;
    onError("");
    try {
      await action();
    } catch (cause) {
      if (run.current === id) onError(messageOf(cause));
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
      if (!result.leagues.length) onError(`No NFL leagues for that username in ${sleeperSeason}.`);
    });
  }

  function connectSleeper(leagueId: string) {
    setWorking("Loading the league and the player directory…");
    void guarded(async () => {
      const identity = await loadPlayerDirectory();
      save(await importSleeperLeague(leagueId, found?.userId ?? null, identity));
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
        save(normalizeEspn(raw, { leagueId, season: espnSeason, identity }));
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

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <form
        className="space-y-3 border border-border bg-card p-3"
        onSubmit={(event) => {
          event.preventDefault();
          findSleeper();
        }}
      >
        <h2 className="text-lg font-semibold">Sleeper</h2>
        <p className="text-sm text-muted-foreground">Enter a username. No password. The username does not prove you own a team.</p>
        <label className="block text-xs font-semibold">
          Sleeper username
          <input value={sleeperName} autoComplete="off" onChange={(event) => setSleeperName(event.target.value)} className={`${control} mt-1 w-full`} />
        </label>
        <label className="block text-xs font-semibold">
          Season
          <input
            type="number"
            min={2017}
            max={2035}
            value={sleeperSeason}
            onChange={(event) => {
              seasonsTouched.current = true;
              setSleeperSeason(Number(event.target.value));
            }}
            className={`${control} mt-1 w-28`}
          />
        </label>
        <button type="submit" disabled={!!working || !sleeperName.trim()} className={primary}>
          Find leagues
        </button>
        {found && found.leagues.length > 0 && (
          <ul className="space-y-2">
            {found.leagues.map((item) => (
              <li key={item.id}>
                <button type="button" disabled={!!working} onClick={() => connectSleeper(item.id)} className={`${control} w-full text-left`}>
                  Import {item.name} · {item.teams} teams{item.status ? ` · ${item.status}` : ""}
                </button>
              </li>
            ))}
          </ul>
        )}
      </form>
      <form
        className="space-y-3 border border-border bg-card p-3"
        onSubmit={(event) => {
          event.preventDefault();
          connectEspn();
        }}
      >
        <h2 className="text-lg font-semibold">ESPN</h2>
        <p className="text-sm text-muted-foreground">
          Paste a fantasy.espn.com league link or a numeric league ID. A public league loads directly. Session cookies are not accepted on this static page and are never saved.
        </p>
        <label className="block text-xs font-semibold">
          ESPN league URL or ID
          <input value={espnInput} autoComplete="off" onChange={(event) => setEspnInput(event.target.value)} className={`${control} mt-1 w-full`} />
        </label>
        <label className="block text-xs font-semibold">
          Season
          <input
            type="number"
            min={2017}
            max={2035}
            value={espnSeason}
            onChange={(event) => {
              seasonsTouched.current = true;
              setEspnSeason(Number(event.target.value));
            }}
            className={`${control} mt-1 w-28`}
          />
        </label>
        <button type="submit" disabled={!!working || !espnInput.trim()} className={primary}>
          Link league
        </button>
        <p className="text-sm text-muted-foreground">
          If the league is private, a commissioner can make it viewable, or you can open the read-only URL while logged into ESPN and import the JSON once. That import stores the league, not your cookies.{" "}
          <a className="underline" href="https://support.espn.com/hc/en-us/articles/360000991871-Making-a-Private-League-Viewable-to-the-Public" target="_blank" rel="noreferrer">
            ESPN public-view setting
          </a>
        </p>
        {(showPaste || paste || espnFile) && (
          <>
            <p className="text-sm">
              Open <EspnDataLink input={espnInput} season={espnSeason} /> while logged in. Paste the JSON, or save the response and choose the file.
            </p>
            <div className="flex gap-2" role="group" aria-label="How to add the ESPN JSON">
              <button type="button" aria-pressed={espnImport === "paste"} onClick={() => setEspnImport("paste")} className={espnImport === "paste" ? "border border-ring bg-muted px-2 py-1 text-sm font-semibold" : control}>
                Paste JSON
              </button>
              <button type="button" aria-pressed={espnImport === "file"} onClick={() => setEspnImport("file")} className={espnImport === "file" ? "border border-ring bg-muted px-2 py-1 text-sm font-semibold" : control}>
                JSON file
              </button>
            </div>
            {espnImport === "paste" ? (
              <>
                <label className="block text-xs font-semibold">
                  ESPN league JSON
                  <textarea value={paste} spellCheck={false} autoComplete="off" rows={6} onChange={(event) => setPaste(event.target.value)} className={`${control} mt-1 w-full font-mono`} />
                </label>
                <button
                  type="button"
                  disabled={!!working || !paste.trim()}
                  onClick={() => {
                    setWorking("Reading the pasted league…");
                    void guarded(() => readEspnImport(paste));
                  }}
                  className={primary}
                >
                  Import pasted league
                </button>
              </>
            ) : (
              <>
                <label className="block text-xs font-semibold">
                  League JSON file
                  <input type="file" accept="application/json,.json" onChange={(event) => setEspnFile(event.target.files?.[0] ?? null)} className={`${control} mt-1 block w-full`} />
                </label>
                {espnFile && <p className="text-xs text-muted-foreground">Selected {espnFile.name}</p>}
                <button
                  type="button"
                  disabled={!!working || !espnFile}
                  onClick={() => {
                    const file = espnFile;
                    if (!file) {
                      onError("Choose a league JSON file first.");
                      return;
                    }
                    setWorking("Reading the league file…");
                    void guarded(async () => {
                      await readEspnImport(await readFileText(file));
                    });
                  }}
                  className={primary}
                >
                  Import league file
                </button>
              </>
            )}
          </>
        )}
      </form>
    </div>
  );
}

function EspnDataLink({ input, season }: { input: string; season: number }) {
  let href = "";
  try {
    href = espnLeagueUrl(parseEspnLeagueReference(input, season).leagueId, season);
  } catch {
    href = "";
  }
  return href ? (
    <a className="underline" href={href} target="_blank" rel="noreferrer">
      the ESPN league data
    </a>
  ) : (
    <span>the ESPN league data</span>
  );
}

export { control as leagueControlClass, primary as leaguePrimaryClass, keepSelection, messageOf };
