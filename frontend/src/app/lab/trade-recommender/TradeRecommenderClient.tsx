"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { PlayerComparisonLink } from "@/components/PlayerComparisonLink";
import { LeagueConnectForms, leagueControlClass as control } from "@/components/league/LeagueConnectForms";
import { useRos } from "@/components/projections/useRos";
import { formatPct, formatPoints, projectLeague } from "@/lib/league/project";
import {
  analyzeTeamStrengths,
  canRecommend,
  clampPackageSize,
  gapOverlayForSide,
  MAX_PACKAGE_SIZE,
  otherDeltaFloor,
  recommendForTeam,
  recommendTrades,
  strengthOverlayForTrade,
  THREE_PACK_POOL,
  tradeablePlayers,
  type TradeRecommendation,
} from "@/lib/league/recommend-trades";
import { leagueSettingsLabel } from "@/lib/league/store";
import { useLeagueLabStore } from "@/lib/league/use-league-store";
import { rosMedian, type RosPlayer } from "@/lib/ros";
import { LeagueStrengthBars, TradeImpactCurves, TradeScatter, WeaknessChart } from "./TradeCharts";

type Mode = "suggest" | "two-team" | "give-away";

const signed = (n: number) => `${n > 0 ? "+" : ""}${n.toFixed(1)}`;

export function TradeRecommenderClient() {
  const { snapshot, error: rosError, retry } = useRos();
  const { store, league, save, activate } = useLeagueLabStore();
  const [working, setWorking] = useState("");
  const [error, setError] = useState("");
  const [mode, setMode] = useState<Mode>("suggest");
  const [fairness, setFairness] = useState(0);
  const [maxEachSide, setMaxEachSide] = useState(2);
  const [yourTeamId, setYourTeamId] = useState("");
  const [partnerId, setPartnerId] = useState("");
  const [teamA, setTeamA] = useState("");
  const [teamB, setTeamB] = useState("");
  const [giveAwayIds, setGiveAwayIds] = useState<string[]>([]);
  const [selectedTradeId, setSelectedTradeId] = useState<string | null>(null);

  const projection = useMemo(() => (league && snapshot ? projectLeague(league, snapshot) : null), [league, snapshot]);
  const teamNames = useMemo(() => new Map(league?.teams.map((team) => [team.id, team.name]) ?? []), [league]);

  const resolvedYourId = yourTeamId || league?.selectedTeamId || league?.teams[0]?.id || "";
  const resolvedPartner = partnerId || league?.teams.find((team) => team.id !== resolvedYourId)?.id || "";
  const resolvedA = teamA || resolvedYourId;
  const resolvedB = teamB || league?.teams.find((team) => team.id !== resolvedA)?.id || "";

  const packageSize = clampPackageSize(maxEachSide);
  const strengths = useMemo(() => (league && projection && canRecommend(snapshot, projection) ? analyzeTeamStrengths(league, projection) : []), [league, projection, snapshot]);
  const yourStrength = strengths.find((row) => row.teamId === (mode === "two-team" ? resolvedA : resolvedYourId));

  const givePool = useMemo(() => {
    if (!projection) return [] as RosPlayer[];
    const fromId = mode === "give-away" ? resolvedYourId : resolvedA;
    return tradeablePlayers(projection, fromId).sort((a, b) => rosMedian(b) - rosMedian(a) || a.name.localeCompare(b.name));
  }, [projection, mode, resolvedYourId, resolvedA]);

  const recommendations = useMemo(() => {
    if (!league || !projection || !canRecommend(snapshot, projection)) return [] as TradeRecommendation[];
    const base = { fairness, limit: 10, maxEachSide: packageSize };
    if (mode === "two-team") {
      if (!resolvedA || !resolvedB) return [];
      return recommendTrades(league, projection, resolvedA, resolvedB, base);
    }
    if (mode === "give-away") {
      if (!resolvedYourId || !resolvedPartner || !giveAwayIds.length) return [];
      return recommendTrades(league, projection, resolvedYourId, resolvedPartner, { ...base, forcedGiveIds: giveAwayIds, limit: 12 });
    }
    if (!resolvedYourId) return [];
    return recommendForTeam(league, projection, resolvedYourId, { ...base, partnerId: partnerId || null, limit: 12 });
  }, [league, projection, snapshot, mode, fairness, packageSize, resolvedA, resolvedB, resolvedYourId, resolvedPartner, partnerId, giveAwayIds]);

  const selected = recommendations.find((trade) => trade.id === selectedTradeId) ?? recommendations[0] ?? null;

  const leftFocusId = mode === "two-team" ? resolvedA : resolvedYourId;
  const leftName = teamNames.get(leftFocusId) ?? "Your team";
  const rightName = selected ? (teamNames.get(selected.right.teamId) ?? "Partner") : teamNames.get(mode === "two-team" ? resolvedB : resolvedPartner) ?? "Partner";

  const focusSide = selected && selected.left.teamId === leftFocusId ? selected.left : selected?.right.teamId === leftFocusId ? selected.right : selected?.left;
  const gapOverlay = useMemo(() => {
    if (!yourStrength || !selected || !focusSide || focusSide.teamId !== yourStrength.teamId) return null;
    return gapOverlayForSide(yourStrength, focusSide);
  }, [yourStrength, selected, focusSide]);
  const strengthOverlay = useMemo(() => (selected && strengths.length ? strengthOverlayForTrade(strengths, selected) : null), [selected, strengths]);

  function toggleGive(id: string) {
    setGiveAwayIds((ids) => {
      if (ids.includes(id)) return ids.filter((item) => item !== id);
      if (ids.length >= packageSize) return [...ids.slice(ids.length - packageSize + 1), id];
      return [...ids, id];
    });
    setSelectedTradeId(null);
  }

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-5 px-4 py-8">
      <header className="space-y-2">
        <p className="text-[11px] font-semibold tracking-[0.14em] text-muted-foreground uppercase">Lab · not in nav</p>
        <h1 className="text-2xl font-semibold tracking-tight">Trade recommender</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Experimental: import a league (same browser store as the{" "}
          <Link href="/lab/league" className="underline">
            league lab
          </Link>
          ), spot positional weaknesses, and search ROS-based trade packages that help your side while staying within a fairness budget you control.
        </p>
        <p className="border border-warning-border bg-warning-surface p-2 text-sm text-warning-foreground">
          <strong>Experimental:</strong> recommendations are frontend-only heuristics on fitted normals. They are not validated win probabilities, and current injuries are not modeled.
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

      {!league ? (
        <LeagueConnectForms existingLeague={null} onSave={save} onError={setError} working={working} setWorking={setWorking} />
      ) : (
        <>
          <section className="space-y-3 border border-border bg-card p-3" aria-label="Linked league">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold">{league.name}</h2>
                <p className="text-sm text-muted-foreground">
                  {league.provider === "sleeper" ? "Sleeper" : "ESPN"} · {league.season} · {leagueSettingsLabel(league.rosterSettings)}
                  {snapshot ? ` · ROS through week ${snapshot.cutoffWeek}` : ""}
                </p>
              </div>
            </div>
            {store.leagues.length > 1 && (
              <label className="block text-xs font-semibold">
                Saved league
                <select value={league.id} onChange={(event) => activate(event.target.value)} className={`${control} mt-1 block`}>
                  {store.leagues.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name} · {item.season}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <details className="text-sm">
              <summary className="cursor-pointer font-semibold">Link another league</summary>
              <div className="mt-3">
                <LeagueConnectForms existingLeague={league} onSave={save} onError={setError} working={working} setWorking={setWorking} />
              </div>
            </details>
          </section>

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
            <>
              <section className="space-y-3 border border-border bg-card p-3" aria-label="Recommendation controls">
                <div role="group" aria-label="Recommendation mode" className="flex flex-wrap gap-1">
                  {(
                    [
                      ["suggest", "Help my team"],
                      ["two-team", "Any two teams"],
                      ["give-away", "Players I give"],
                    ] as const
                  ).map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      aria-pressed={mode === key}
                      onClick={() => {
                        setMode(key);
                        setSelectedTradeId(null);
                      }}
                      className={`border px-3 py-2 text-sm font-semibold ${mode === key ? "border-ring bg-primary text-primary-foreground" : "border-border bg-card text-text-secondary"}`}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  {mode !== "two-team" ? (
                    <>
                      <label className="block text-xs font-semibold">
                        Your team
                        <select
                          value={resolvedYourId}
                          onChange={(event) => {
                            setYourTeamId(event.target.value);
                            setGiveAwayIds([]);
                            setSelectedTradeId(null);
                          }}
                          className={`${control} mt-1 block w-full`}
                        >
                          {league.teams.map((team) => (
                            <option key={team.id} value={team.id}>
                              {team.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="block text-xs font-semibold">
                        {mode === "give-away" ? "Trade with" : "Counterparty (optional)"}
                        <select
                          value={mode === "suggest" ? partnerId : resolvedPartner}
                          onChange={(event) => {
                            setPartnerId(event.target.value);
                            setSelectedTradeId(null);
                          }}
                          className={`${control} mt-1 block w-full`}
                        >
                          {mode === "suggest" && <option value="">All other teams</option>}
                          {league.teams
                            .filter((team) => team.id !== resolvedYourId)
                            .map((team) => (
                              <option key={team.id} value={team.id}>
                                {team.name}
                              </option>
                            ))}
                        </select>
                      </label>
                    </>
                  ) : (
                    <>
                      <label className="block text-xs font-semibold">
                        Favored team
                        <select
                          value={resolvedA}
                          onChange={(event) => {
                            setTeamA(event.target.value);
                            setSelectedTradeId(null);
                          }}
                          className={`${control} mt-1 block w-full`}
                        >
                          {league.teams.map((team) => (
                            <option key={team.id} value={team.id}>
                              {team.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="block text-xs font-semibold">
                        Other team
                        <select
                          value={resolvedB}
                          onChange={(event) => {
                            setTeamB(event.target.value);
                            setSelectedTradeId(null);
                          }}
                          className={`${control} mt-1 block w-full`}
                        >
                          {league.teams
                            .filter((team) => team.id !== resolvedA)
                            .map((team) => (
                              <option key={team.id} value={team.id}>
                                {team.name}
                              </option>
                            ))}
                        </select>
                      </label>
                    </>
                  )}
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="block space-y-2 text-xs font-semibold">
                    <span className="flex flex-wrap items-baseline justify-between gap-2">
                      <span>Fairness {fairness.toFixed(2)}</span>
                      <span className="font-normal text-muted-foreground">
                        0 = even · other Δ floor {otherDeltaFloor(fairness).toFixed(0)} pts · 1 = max unfair favoring {leftName}
                      </span>
                    </span>
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.05}
                      value={fairness}
                      aria-valuemin={0}
                      aria-valuemax={1}
                      aria-valuenow={fairness}
                      aria-label="Fairness toward your team"
                      onChange={(event) => {
                        setFairness(Number(event.target.value));
                        setSelectedTradeId(null);
                      }}
                      className="w-full"
                    />
                  </label>
                  <fieldset className="space-y-2">
                    <legend className="text-xs font-semibold">Max players each side</legend>
                    <div className="flex flex-wrap gap-1" role="group" aria-label="Max players each side">
                      {[1, 2, 3].map((size) => (
                        <button
                          key={size}
                          type="button"
                          aria-pressed={packageSize === size}
                          onClick={() => {
                            setMaxEachSide(size);
                            setGiveAwayIds((ids) => ids.slice(0, size));
                            setSelectedTradeId(null);
                          }}
                          className={`border px-3 py-2 text-sm font-semibold ${packageSize === size ? "border-ring bg-primary text-primary-foreground" : "border-border bg-card text-text-secondary"}`}
                        >
                          {size}
                        </button>
                      ))}
                    </div>
                    <p className="text-xs font-normal text-muted-foreground">
                      Searches 1–{packageSize} for-{packageSize === 1 ? "1" : `1…${packageSize}`} packages
                      {packageSize === MAX_PACKAGE_SIZE ? ` (3-packs use the top ${THREE_PACK_POOL} ROS means per roster)` : ""}.
                    </p>
                  </fieldset>
                </div>

                {mode === "give-away" && (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold">Players to trade away (up to {packageSize})</p>
                    <ul className="grid gap-1 sm:grid-cols-2">
                      {givePool.map((player) => {
                        const on = giveAwayIds.includes(player.playerId);
                        return (
                          <li key={player.playerId}>
                            <button
                              type="button"
                              aria-pressed={on}
                              onClick={() => toggleGive(player.playerId)}
                              className={`w-full border px-2 py-1.5 text-left text-sm ${on ? "border-ring bg-muted font-semibold" : "border-border bg-card"}`}
                            >
                              {player.name}{" "}
                              <span className="text-xs font-normal text-muted-foreground">
                                {player.position} · {rosMedian(player).toFixed(1)}
                              </span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                    {!giveAwayIds.length && (
                      <p className="text-sm text-muted-foreground">
                        Select up to {packageSize} player{packageSize === 1 ? "" : "s"} you are willing to send.
                      </p>
                    )}
                  </div>
                )}
              </section>

              {yourStrength && (
                <div className="grid gap-4 lg:grid-cols-2">
                  <WeaknessChart
                    gaps={yourStrength.positions}
                    teamName={teamNames.get(yourStrength.teamId) ?? "Team"}
                    overlay={gapOverlay}
                  />
                  <LeagueStrengthBars
                    strengths={strengths}
                    teamNames={teamNames}
                    focusId={yourStrength.teamId}
                    overlay={strengthOverlay}
                  />
                </div>
              )}

              <TradeScatter trades={recommendations} leftName={leftName} rightLabel={mode === "suggest" && !partnerId ? "partner" : rightName} />

              <section className="space-y-3" aria-live="polite" aria-label="Recommended trades">
                <div className="flex flex-wrap items-end justify-between gap-2">
                  <div>
                    <h2 className="text-lg font-semibold">Recommended packages</h2>
                    <p className="text-xs text-muted-foreground">
                      Ranked by expected help to {leftName} under the fairness slider. Only packages that clear the fairness filters are listed.
                    </p>
                  </div>
                  <p className="text-xs text-muted-foreground">{recommendations.length} shown</p>
                </div>

                {!recommendations.length ? (
                  <p className="border border-border bg-card p-3 text-sm text-muted-foreground">
                    No packages cleared the fairness filters
                    {mode === "give-away" && !giveAwayIds.length ? " — pick players to send first" : ""}. Try raising fairness, changing the partner, or picking different give-aways.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {recommendations.map((trade, index) => {
                      const active = (selected?.id ?? "") === trade.id;
                      const partner = teamNames.get(trade.right.teamId) ?? trade.right.teamId;
                      return (
                        <li key={trade.id}>
                          <button
                            type="button"
                            onClick={() => setSelectedTradeId(trade.id)}
                            className={`w-full border p-3 text-left ${active ? "border-ring bg-muted" : "border-border bg-card"}`}
                          >
                            <div className="flex flex-wrap items-start justify-between gap-2">
                              <p className="text-sm font-semibold">
                                #{index + 1} · vs {partner}
                              </p>
                              <p className="text-xs text-muted-foreground">score {trade.score.toFixed(1)}</p>
                            </div>
                            <div className="mt-2 grid gap-2 sm:grid-cols-2">
                              <PackageLine season={league.season} label={`${leftName} sends`} players={trade.left.give} />
                              <PackageLine season={league.season} label={`${partner} sends`} players={trade.right.give} />
                            </div>
                            <div className="mt-2 flex flex-wrap gap-3 text-xs tabular-nums">
                              <span className={trade.left.deltaMean >= 0 ? "text-success" : "text-destructive"}>
                                {leftName} {signed(trade.left.deltaMean)} · P(help) {formatPct(trade.left.pHelp)}
                              </span>
                              <span className={trade.right.deltaMean >= 0 ? "text-success" : "text-destructive"}>
                                {partner} {signed(trade.right.deltaMean)} · P(hurt) {formatPct(trade.right.pHurt)}
                              </span>
                            </div>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </section>

              {selected && (
                <>
                  <TradeImpactCurves trade={selected} leftName={leftName} rightName={rightName} />
                  <section className="grid gap-3 sm:grid-cols-2" aria-label="Selected trade lineup change">
                    <LineupDelta season={league.season} title={`${leftName} lineup`} before={selected.left.beforeLineup} after={selected.left.afterLineup} delta={selected.left.deltaMean} />
                    <LineupDelta season={league.season} title={`${rightName} lineup`} before={selected.right.beforeLineup} after={selected.right.afterLineup} delta={selected.right.deltaMean} />
                  </section>
                </>
              )}
            </>
          )}
        </>
      )}

      <section className="space-y-2 border border-border bg-card p-3" aria-labelledby="trade-rec-caveats">
        <h2 id="trade-rec-caveats" className="text-sm font-semibold">
          How recommendations work
        </h2>
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
          <li>Each roster maps to rest-of-season players the same way as the league lab. Kickers, defenses, IR, and taxi spots are out of the pool.</li>
          <li>Team strength is the optimized starter lineup mean; uncertainty is a normal fit from each starter&apos;s mean and 5th–95th gap.</li>
          <li>
            P(help) / P(hurt) use the change in lineup totals with shared starters canceling, so only players who enter or leave the starting lineup contribute variance.
          </li>
          <li>
            Fairness 0 keeps the other team near even (about −2 ROS mean points of hurt allowed, with a soft package-gap budget). Fairness 1 widens that floor toward roughly −120 points and weights your gain more heavily.
          </li>
          <li>
            Package size is user-controlled (1–{MAX_PACKAGE_SIZE} per side). Three-player packages only enumerate the top {THREE_PACK_POOL} ROS means on each roster so the search stays responsive. This does not search three-team trades, faab, or draft picks.{" "}
            <Link href="/trades" className="underline">
              Manual trade analysis
            </Link>{" "}
            is still available for custom packages.
          </li>
          <li>
            Selecting a recommendation overlays before/after position gaps and league ROS means with ±1σ error bars from the same fitted normals used for P(help)/P(hurt).
          </li>
        </ul>
      </section>
    </main>
  );
}

function PackageLine({ season, label, players }: { season: number; label: string; players: RosPlayer[] }) {
  return (
    <p className="text-sm">
      <span className="text-xs font-semibold text-muted-foreground">{label}</span>
      <span className="mt-0.5 block">
        {players.length
          ? players.map((player, index) => (
              <span key={player.playerId}>
                {index > 0 ? ", " : ""}
                <PlayerComparisonLink playerId={player.playerId} season={season}>
                  {player.name}
                </PlayerComparisonLink>
                <span className="text-xs text-muted-foreground"> ({formatPoints(player.mean)})</span>
              </span>
            ))
          : "—"}
      </span>
    </p>
  );
}

function LineupDelta({
  season,
  title,
  before,
  after,
  delta,
}: {
  season: number;
  title: string;
  before: TradeRecommendation["left"]["beforeLineup"];
  after: TradeRecommendation["left"]["afterLineup"];
  delta: number;
}) {
  return (
    <div className="border border-border bg-card p-3">
      <p className="text-sm font-semibold">
        {title}{" "}
        <span className={`tabular-nums ${delta >= 0 ? "text-success" : "text-destructive"}`}>{signed(delta)}</span>
      </p>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        <MiniLineup season={season} caption="Before" lineup={before} />
        <MiniLineup season={season} caption="After" lineup={after} />
      </div>
    </div>
  );
}

function MiniLineup({ season, caption, lineup }: { season: number; caption: string; lineup: TradeRecommendation["left"]["beforeLineup"] }) {
  return (
    <table className="w-full text-left text-xs">
      <caption className="pb-1 text-left font-semibold">
        {caption} · {lineup.total.toFixed(1)} med
      </caption>
      <tbody>
        {lineup.assignments.map((spot, index) => (
          <tr key={`${spot.slot}-${index}`}>
            <th scope="row" className="border-t border-border py-1 pr-1 font-normal text-muted-foreground">
              {spot.slot}
            </th>
            <td className="border-t border-border py-1">
              {spot.player ? (
                <PlayerComparisonLink playerId={spot.player.playerId} season={season}>
                  {spot.player.name}
                </PlayerComparisonLink>
              ) : (
                "Empty"
              )}
            </td>
            <td className="border-t border-border py-1 tabular-nums">{spot.player ? formatPoints(spot.player.mean) : "0.0"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
