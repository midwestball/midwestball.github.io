# Ballnet ETL brief: Knowball visualization store

**Audience:** an agent working in the **ballnet** (public Python pipeline / DS) repo.  
**Companion file:** attach `.plans/NFL Stats Sliders.md` from knowball (ramp–hold, nflverse sources, min-n, plot type, zero mass). This brief is the **locked Knowball contract**. Where the two disagree on UI shape, **this brief wins**. Where they disagree on nflverse column names or min-n, **the sliders plan wins** for computation.

Knowball is a public Next.js app that **only renders JSON**. It has no Python, no `@supabase/supabase-js`, and no mock KDE generation. Ballnet owns ingest, joins, ramp–hold, KDEs, percentiles, Supabase, and publishing. Fantasy draft optimization belongs in private **ffoptim**, not this pipeline.

---

## 1. System split (do not invert)

| Repo | Owns | Must not own |
|---|---|---|
| **ballnet** | nflverse ingest, joins, qualification, densities, percentiles, Supabase viz store, published JSON | Knowball UI, Recharts, catalog labels |
| **knowball** | Position catalog (`stat.id`, domains, `kind`, `higherIsBetter`, format), `ExpandableStatRow` | Database clients, ingest, inventing slider rows |

**Publish path (required for v1):**

1. Compute into a **normalized visualization store** in Supabase (tables below).
2. Join into one **`PlayerPageJson` per player per season** (and `asOfWeek`) with `schemaVersion: 1`.
3. Write that JSON to **Supabase Storage** (or equivalent static objects). Knowball will fetch the file. Search can later use a tiny **player index JSON** — still not a SQL client in the Next app.

Do **not** duplicate the league KDE onto every player row in Postgres. Curves live once in `league_distributions` (`league_ytd` scope). Page JSON **may** embed them for a single fetch.

Build the pipeline as a **DAG** with a durable weekly panel spine so later products (highlights, player-own densities, similarity, teams) hang off Stages A–B without redesign — see §§10, 12, and 15. Do **not** implement those products in v1.

Superseded ideas (ignore if you see them in old checklists): Knowball talking to Postgres; Observable Plot; frontend ramp–hold greying; storing raw weekly box scores in the **public** viz schema.

---

## 2. What Knowball actually renders (skeleton today)

Until Ballnet JSON exists, player pages call:

```ts
hydratePlayerStats(player.position, [])
```

That walks the **full position catalog** and paints every row gray (`availability: "pending"`). Empty snapshots must still appear. Do not omit stats.

When JSON exists, Knowball will:

1. Load `PlayerPageJson`.
2. Call `hydratePlayerStats(position, json.stats)`.
3. Overlay snapshots **by `id`**. Extra Ballnet ids are ignored. Missing ids stay `pending`.
4. `alwaysUnavailable` catalog flags become `not_in_nflverse` **even if Ballnet sends a row**.

Locked UI math (Ballnet must match):

- Percentile slider is **0–100**, already **oriented so 100 is good**. Knowball does **not** invert again.
- Inclusive CDF \(P(X \le x)\). Caption is “of the league has a STAT of VALUE or lower/higher”, never “better than N%”.
- Rate stats in JSON are **0–1** when catalog `format === "percent"`. UI multiplies by 100 for display.
- CPOE uses `percent_pts`: store as **percentage points** (e.g. `+2.4`), not `0.024`.
- Chart x-axis = raw stat on `[xMin, xMax]`. Chart y-axis = **KDE density** (∫y dx ≈ 1). Do not label y as “% of the league”.
- Every catalog id → Gaussian KDE with **reflection at catalog bounds**. Catalog `kind: discrete` is formatting metadata only; do not emit histograms.
- High zero-mass count stats still get a reflected KDE (no separate 0-bin histogram).
- Missing NGS/PFR: `missing_source`. **Never impute 0**.

Knowball `kind` is **either** `continuous` **or** `discrete` per `stat.id` for formatting. It does **not** select a chart shape. For catalog-continuous hurdle stats (passing/rushing/receiving/return yards), emit a **single reflected KDE** on the qualified sample (reflection at `lowerBound`, typically 0). Do not emit a second histogram for that id.

---

## 3. JSON contracts (exact types Knowball already has)

Source of truth in knowball: `web/src/lib/payload.ts`, `web/src/lib/distribution.ts`, `web/src/lib/catalog/hydrate.ts`.

### 3.1 `PlayerPageJson`

```ts
{
  schemaVersion: 1;      // required on every published object; bump only on breaking changes
  player: {
    id: string;          // GSIS player_id, e.g. "00-0033873"
    name: string;        // display_name
    position: string;    // PositionCode below
    team: string;        // current/as-of team abbreviation
    seasons: number[];   // seasons this player has viz data for, ascending
  };
  season: number;
  asOfWeek: number;      // NFL week being viewed (REG week number)
  stats: JsonStatSnapshot[];
  // Additive optional keys later (Knowball must ignore unknowns until wired):
  // overallPercentile?: number;
  // highlightRefs?: …;
}
```

**Additive envelope rule:** Knowball ignores unknown top-level keys. Ballnet may add optional fields in a later schema minor bump without breaking v1 consumers. Do **not** remove or rename locked fields without bumping `schemaVersion` and coordinating a Knowball change.

Storage object key convention (required):

```
pages/{season}/w{asOfWeek}/{player_id}.json
```

Example: `pages/2025/w8/00-0033873.json`

Also publish a **current** pointer the frontend can default to:

```
pages/current/{player_id}.json
```

Overwrite this when the latest REG week is recomputed.

Do **not** embed per-player weekly densities into every `PlayerPageJson` (payload bloat). Those belong under reserved `dists/` paths when that product ships (section 15).

### 3.2 `JsonStatSnapshot`

| Field | Type | Rules |
|---|---|---|
| `id` | string | **Must** match catalog id (section 8). |
| `playerValue` | number | Raw stat in catalog units. Rates 0–1 for `percent`. |
| `percentile` | number | 0–100, **already oriented** (`higherIsBetter` applied in Ballnet). |
| `qualified` | boolean | `denom_ytd >= min_n` and source present. If false, Knowball maps to `insufficient_sample` unless `unavailableReason` is set. |
| `denomYtd` | number? | Season-to-date denominator used in ramp–hold. |
| `kind` | `"continuous"` \| `"discrete"` | Catalog metadata (formatting). Must match catalog `kind` for that id. Does **not** select histogram vs KDE. |
| `xMin`, `xMax` | number | Prefer catalog domains so charts stay comparable. Override only if a season truly exceeds the locked domain; then expand both league curve and all players for that `(season, week, group, stat)`. |
| `yMax` | number | Max KDE density on the league curve (Knowball y-axis). |
| `lowerBound`, `upperBound` | number? | Reflection walls. Copy from catalog when present. |
| `curve` | `{x, y}[]` | Required for `ready`. Dense grid (recommend 256–512 points) spanning `[xMin, xMax]`. |
| `unavailableReason` | omit \| `insufficient_sample` \| `missing_source` \| `not_in_nflverse` | See section 6. Do not send `"ready"` or `"pending"` here. |

Hydration gotchas:

- No snapshot → `pending` (row still shown).
- Snapshot with `unavailableReason` → that status.
- Snapshot `qualified: false` and no reason → `insufficient_sample`.
- Snapshot qualified but empty `curve` → `pending` (treat as publish bug).
- Catalog `alwaysUnavailable: true` → `not_in_nflverse`, ignore snapshot.

Qualified **ready** rows still must include the **league** curve (copied from `league_distributions` at publish time — or merged from `league/*.json`). Player pages only store a scalar overlay; do not embed the league shape on every page.

### 3.3 Player index JSON (search)

Knowball search currently filters a fixture list. Publish:

```
index/players.json
```

```ts
{
  schemaVersion: 1;
  players: Array<{
    id: string;           // GSIS
    name: string;
    position: string;     // PositionCode
    team: string;
    seasons: number[];
    // overallPercentile?: number;  // additive later
  }>;
}
```

If a transitional flat array is easier for a first cut, wrap it before Knowball goes live — prefer the envelope with `schemaVersion` from day one.

### 3.4 Position codes Knowball accepts

Unknown codes throw in `positionGroupOf`. Map nflverse `position` into this set before publish.

| Code | Group (`position_group` in DB) |
|---|---|
| `QB` | `qb` |
| `RB`, `FB` | `backfield` |
| `WR`, `TE` | `pass_catcher` |
| `T`, `OT`, `G`, `OG`, `C` | `ol` |
| `ED`, `EDGE`, `DE`, `DT`, `NT`, `LB`, `ILB`, `OLB` | `def_front` |
| `CB`, `FS`, `SS`, `S` | `secondary` |
| `K` | `kicker` |
| `P` | `punter` |
| `KR`, `PR` | `returner` |

Mapping notes:

- nflverse `OL` / `OT` / `OG` / `C` / `T` / `G` → OL codes above (`OT`→`T` or keep `OT`; both are `ol`).
- `DE`/`OLB` pass-rushers → `def_front`. Do not put OLB coverage specialists on the WR catalog.
- Return specialists who are also WR: publish **two pages only if** you have two roster positions; otherwise use the **primary** nflverse position for the player page. `KR`/`PR` catalogs are for dedicated returner pages. Dual-role players should use their offensive/defensive catalog; return stats are **not** on WR/RB catalogs today.

---

## 4. Ramp–hold, sample, and universe (compute in Ballnet)

Formula (locked):

\[
\min_n = n_{\text{base}} \times \min(w, 4)
\]

- `w` = **as-of NFL week being viewed**, not weeks since the player’s debut.
- Weeks 1–4: ramp. Week 5+: hold at \(4 n_{\text{base}}\).
- A Week 10 starter still faces the hold immediately.
- Enable / `qualified = true` iff **season-to-date cumulative denom** \(\ge \min_n\).
- Ignore `season_type = PRE`.
- Ignore NGS `week == 0` in weekly plots / YTD NGS counts.
- Rate stats: denom is the **count column**, not games, unless the catalog `denom` says games.
- NGS stats also require a **non-null NGS row** that week (and YTD count of such rows for min-n).
- PFR-charted stats require a **charted row**; missing row → `missing_source`, not 0.

`n_base` is catalog `minNBase` (section 8). Hold values from the sliders cheat sheet:

| Role | \(n_{\text{base}}\) | Hold (week 5+) |
|---|---|---|
| Passer rate (Cmp%, rating, CPOE) | 10 attempts | 40 |
| Passer volume (attempts, EPA, PACR, deep att) | 8 attempts | 32 |
| QB designed rush | 3 carries | 12 |
| RB rate (YPC, YAC, broken tackles) | 5 carries | 20 |
| WR/TE rate | 3 targets | 12 |
| Backfield receiving | 2 targets | 8 |
| Coverage rate (cmp% / rating / aDOT allowed) | 4 targets allowed | 16 |
| Coverage volume | 2 targets allowed | 8 |
| Kicker FG% | 1 FGA | 4 |
| Punter rates | 2 punts | 8 |
| NGS averages | 1 NGS row | 4 NGS rows YTD |
| Rare counts (TD, INT, sack, drop, FF, etc.) | 1 REG game-row | 4 game-rows YTD |
| Snap % | 1 snap-row | 4 snap-rows YTD |

**League distribution universe** for a `(season, as_of_week, position_group, stat_id)`:

- Same **position group** (QB vs QB, WR+TE together, RB+FB together, etc.).
- REG games only, weeks `1..as_of_week`.
- Each peer contributes **one season-to-date value** (not a cloud of weekly points), after applying the same qualification rule.
- Unqualified peers are **excluded from the density**, not plotted at 0.
- `n_sample` = number of qualified peers in that density.

**Player value** for the overlay: that player’s YTD value through `as_of_week`, same aggregation.

Grain in the sliders plan is **player-week** for source rows; the **published Leg 1 viz grain** is **player-season-as-of-week** (YTD).

**Weekly panel is the spine (invariant):** Persist a durable canonical player-week panel (parquet or `raw`, never public `viz`) keyed so every later product can recompute without re-joining nflverse differently. YTD pages, weekly highlights / z-scores, player-own densities, and trajectory features must **read that panel**. Do not treat weeklies as throwaway intermediates that only exist inside a single YTD job.

---

## 5. Joins (nflverse)

Canonical player key in Knowball and viz tables: **GSIS** `player_id`.

| Source family | Join |
|---|---|
| Box / `player_stats` / PBP | `player_id` (GSIS) |
| NGS | `player_gsis_id` → `player_id` |
| PFR / snap counts | `pfr_player_id` → GSIS via `ff_playerids` (or equivalent id map) |

If a join fails: `missing_source` for stats that need that source. Do not drop the player from `players`.

---

## 6. Availability state machine

| Condition | `qualified` | `unavailable_reason` | Knowball `availability` |
|---|---|---|---|
| Catalog `alwaysUnavailable` | omit row or send anything | ignored | `not_in_nflverse` |
| Season `< startYear` or source not ingested yet | false | `not_in_nflverse` or `missing_source` | that reason |
| Source row null (NGS/PFR/snaps/FTN) | false | `missing_source` | `missing_source` |
| Source present, `denom_ytd < min_n` | false | `insufficient_sample` (or omit reason) | `insufficient_sample` |
| Qualified, curve present | true | null | `ready` |
| No row published for that id | — | — | `pending` |

OL pass-protection ids (`sacks_allowed`, `pressures_allowed`, `block_win_rate`) must **not** be filled from guesswork. Either omit snapshots or send `not_in_nflverse`. Knowball will gray them anyway.

---

## 7. Densities (how to fill `curve`)

### Distribution scopes (do not overload one table)

Same `curve` JSON shape; different **scope**. v1 only builds `league_ytd`. Reserve the names so later work does not jam player-weekly samples into `league_distributions`.

| `distribution_scope` | Sample | v1? | Used for |
|---|---|---|---|
| `league_ytd` | Peers’ YTD values in the position group | **yes** | Player page sliders |
| `player_weekly` | One player’s weekly values (qualified weeks) | later | Compare individual distributions |
| `league_weekly` | All peer-weeks in the window | later | Weekly rarity / “1 in N” / z-score peers |

v1 writes only `viz.league_distributions` (= `league_ytd`). Sketch for later: `viz.player_distributions` with PK `(player_id, season, as_of_week, stat_id)` and the same curve column — **do not implement in v1**.

### Every catalog id (KDE)

- Gaussian KDE on the qualified peer YTD values.
- **Reflect** at `lowerBound` / `upperBound` when the catalog sets them (percents 0–1, rating 0–158.3, seconds floors, etc.). Discrete count ids usually have no catalog walls; still evaluate on `[xMin, xMax]` and normalize.
- Evaluate on a uniform grid on `[xMin, xMax]`.
- Normalize so \(\int y\,dx \approx 1\).
- `yMax` = max grid `y` (Knowball sets the chart domain from this).
- `zeroMass: "none"` NGS stats: do not invent zeros; only players with NGS rows enter the sample.
- Catalog `kind` / `binWidth` do **not** select a histogram. Do not emit `bins` or `samples`.

### Percentiles

For player value \(x\):

1. Inclusive CDF on the **same** league curve Knowball will plot: \(p = P(X \le x)\) (knowball `kdeCdf` trapezoid).
2. If catalog `higherIsBetter === false`, store `percentile = 100 * (1 - p)`, else `percentile = 100 * p`.
3. Clamp to `[0, 100]`.

Knowball hover **recomputes** CDF from the embedded curve, then orients with `higherIsBetter` from the **catalog**, not from the JSON. Ballnet must use the same `higherIsBetter` as the catalog or slider vs tooltip will disagree.

### Shared scoring primitives (implement once; reuse later)

Keep these as library functions in Ballnet — highlights, rarity copy, and compare products must call them rather than inventing parallel math:

| Primitive | Role |
|---|---|
| Oriented percentile / inclusive CDF | Already required for Leg 1 |
| Z-score vs a peer sample | Weekly “best games” / breakouts (later) |
| Tail → `one_in_n` | “1 in a thousand”-style framing from CDF/tail (later); Knowball/Mason only present the number |

### Value aggregation (YTD)

Unless a stat is already an NGS weekly average (then: volume-weighted or mean of weekly NGS rows with non-null — prefer **volume-weighted** by the implicit NGS attempt/rush/target count when the column exists; otherwise mean of qualified weekly NGS rows):

- Counts / yards / EPA: **sum** weeks 1..w REG.
- Rates (Cmp%, YPC, catch %, snap %): **ratio of sums** (e.g. completions/attempts), not average of weekly rates.
- Shares (target share, WOPR): use nflverse season-to-date if provided; else recompute from weekly with team denoms summed.
- Passer rating: recompute from YTD box components, not average of weekly ratings.
- Longest FG: **max** of weekly `fg_long`.
- Snap %: snaps played / team offensive (or defensive) snaps YTD from `snap_counts`.

---

## 8. Catalog `stat.id` list (Ballnet cannot invent rows)

Copy these ids **exactly**. Mixed plan rows (e.g. “Rush Att/Yds/TDs”) are **split**.

`minNBase` is \(n_{\text{base}}\). `kind` / `format` / `higherIsBetter` / domains must match. `percent` → store 0–1.

### 8.1 Quarterback (`position_group = qb`) — 23 ids

| id | kind | format | higherIsBetter | xMin–xMax | minNBase | denom | startYear | source | notes |
|---|---|---|---|---|---|---|---|---|---|
| `pass_attempts` | discrete | count | true | 0–70, bw 1 | 8 | attempts | 1999 | `player_stats` | this **is** the denom for passer rates |
| `completions` | discrete | count | true | 0–45, bw 1 | 8 | attempts | 1999 | `player_stats` | |
| `passing_yards` | continuous | yards | true | −10–554, lb 0 | 8 | attempts | 1999 | `player_stats` | KDE + reflection at 0 |
| `passing_tds` | discrete | count | true | 0–7, bw 1 | 1 | games with attempts | 1999 | `player_stats` | high zero mass |
| `interceptions` | discrete | count | **false** | 0–7, bw 1 | 1 | games with attempts | 1999 | `player_stats` | |
| `sacks_taken` | discrete | count | **false** | 0–12, bw 1 | 1 | games with attempts | 1999 | `player_stats` | |
| `completion_pct` | continuous | percent | true | 0–1 | 10 | attempts | 1999 | derive | 0–1 |
| `passer_rating` | continuous | rating | true | 0–158.3 | 10 | attempts | 1999 | compute from box; NGS rating optional/not this id | NFL rating formula |
| `cpoe` | continuous | percent_pts | true | −25–25 | 10 | attempts | 1999/2016 | `player_stats.passing_cpoe` / NGS | require non-null CPOE; **percentage points** |
| `passing_epa` | continuous | one_decimal | true | −40–40 | 8 | attempts | 1999 | `player_stats` | |
| `pacr` | continuous | ratio | true | 0–3, lb 0 | 8 | passing air yards | 1999 | `player_stats` | |
| `time_to_throw` | continuous | seconds | **false** | 1.5–6, lb 1.5 | 1 | NGS pass attempts | 2016 | NGS passing | missing NGS ≠ 0 |
| `iay` | continuous | one_decimal | true | 0–25, lb 0 | 1 | NGS week | 2016 | NGS passing | |
| `cay` | continuous | one_decimal | true | 0–20, lb 0 | 1 | NGS week | 2016 | NGS passing | |
| `aggressiveness` | continuous | percent | true | 0–1 | 1 | NGS week | 2016 | NGS `aggressiveness` | 0–1 |
| `expected_completion_pct` | continuous | percent | true | 0–1 | 1 | NGS week | 2016 | NGS | 0–1 |
| `air_yards_diff` | continuous | one_decimal | true | −10–8 | 1 | NGS week | 2016 | NGS | |
| `air_yards_to_sticks` | continuous | one_decimal | true | −8–8 | 1 | NGS week | 2016 | NGS | |
| `deep_attempts` | discrete | count | true | 0–20, bw 1 | 8 | attempts | 1999 | `passing_20` (20+ only; no separate 40+ id) | |
| `rush_attempts` | discrete | count | true | 0–20, bw 1 | 3 | carries | 1999 | `player_stats` | split from mixed rush row |
| `rushing_yards` | continuous | yards | true | −15–150, lb 0 | 3 | carries | 1999 | `player_stats` | |
| `rushing_tds` | discrete | count | true | 0–4, bw 1 | 3 | carries | 1999 | `player_stats` | |
| `offensive_snap_pct` | continuous | percent | true | 0–1 | 1 | offensive snaps | 2012 | `snap_counts` via PFR id | 0–1 |

### 8.2 Backfield (`backfield`, RB & FB) — 22 ids

| id | kind | format | higherIsBetter | xMin–xMax | minNBase | denom | startYear | source |
|---|---|---|---|---|---|---|---|---|
| `rush_attempts` | discrete | count | true | 0–45, bw 1 | 5 | carries | 1999 | `player_stats.carries` |
| `rushing_yards` | continuous | yards | true | −15–296, lb 0 | 5 | carries | 1999 | `player_stats` |
| `rushing_tds` | discrete | count | true | 0–6, bw 1 | 1 | games with carries | 1999 | `player_stats` |
| `yards_per_carry` | continuous | two_decimal | true | −5–20 | 5 | carries | 1999 | derive |
| `rushing_epa` | continuous | one_decimal | true | −20–20 | 5 | carries | 1999 | `player_stats` |
| `fumbles` | discrete | count | **false** | 0–7, bw 1 | 1 | touches | 1999 | `rushing_fumbles` / `fumbles_lost_total` |
| `broken_tackles` | discrete | count | true | 0–16, bw 1 | 5 | carries | 2018 | `pfr_advstats` rush; need PFR row |
| `yards_after_contact` | continuous | yards | true | 0–175, lb 0 | 5 | carries | 2018 | PFR rush |
| `time_to_los` | continuous | seconds | **false** | 1.5–5, lb 1.5 | 1 | NGS rush week | 2016 | NGS rushing TLOS |
| `ryoe` | continuous | one_decimal | true | −10–15 | 1 | NGS week | 2016 | prefer per-attempt RYOE |
| `eight_plus_defenders_pct` | continuous | percent | true | 0–1 | 1 | NGS week | 2016 | NGS |
| `ngs_efficiency` | continuous | ratio | true | 0–8, lb 0 | 1 | NGS week | 2016 | NGS `efficiency` |
| `expected_rush_yards` | continuous | yards | true | 0–200, lb 0 | 1 | NGS week | 2016 | NGS |
| `targets` | discrete | count | true | 0–15, bw 1 | 2 | targets | 1999 | `player_stats` |
| `receptions` | discrete | count | true | 0–12, bw 1 | 2 | targets | 1999 | `player_stats` |
| `receiving_yards` | continuous | yards | true | −10–150, lb 0 | 2 | targets | 1999 | `player_stats` |
| `target_share` | continuous | percent | true | 0–0.4 | 2 | team targets | 1999 | `player_stats` |
| `wopr` | continuous | ratio | true | 0–0.5, lb 0 | 2 | targets | 1999 | `player_stats` |
| `red_zone_touches` | discrete | count | true | 0–12, bw 1 | 1 | games | 1999 | PBP `rusher`/`receiver_player_id`, RZ |
| `expected_fantasy_points` | continuous | one_decimal | true | 0–40, lb 0 | 1 | games | 2006 | `ff_opportunity` |
| `offensive_snap_pct` | continuous | percent | true | 0–1 | 1 | offensive snaps | 2012 | `snap_counts` |

Same string ids as QB for rush/receiving/snap **are OK** because league curves are keyed by **position_group**.

### 8.3 Pass catchers (`pass_catcher`, WR & TE) — 22 ids

| id | kind | format | higherIsBetter | xMin–xMax | minNBase | denom | startYear | source |
|---|---|---|---|---|---|---|---|---|
| `targets` | discrete | count | true | 0–21, bw 1 | 3 | targets | 1999 | `player_stats` |
| `receptions` | discrete | count | true | 0–21, bw 1 | 3 | targets | 1999 | `player_stats` |
| `receiving_yards` | continuous | yards | true | −10–336, lb 0 | 3 | targets | 1999 | `player_stats` |
| `receiving_tds` | discrete | count | true | 0–5, bw 1 | 1 | games | 1999 | `player_stats` |
| `drops` | discrete | count | **false** | 0–5, bw 1 | 3 | targets | 2018/2022 | PFR rec and/or FTN `is_drop`; need charted row |
| `yac` | continuous | yards | true | 0–175, lb 0 | 2 | receptions | 1999 | `receiving_yards_after_catch` |
| `avg_yac` | continuous | one_decimal | true | 0–20, lb 0 | 1 | NGS rec week | 2016 | NGS receiving |
| `expected_yac` | continuous | one_decimal | true | 0–20, lb 0 | 1 | NGS week | 2016 | NGS `avg_expected_yac` |
| `yac_oe` | continuous | one_decimal | true | −8–8 | 1 | NGS week | 2016 | NGS `avg_yac_above_expectation` |
| `separation` | continuous | one_decimal | true | 0–9, lb 0 | 1 | NGS week | 2016 | NGS `avg_separation` |
| `cushion` | continuous | one_decimal | true | 0–15, lb 0 | 1 | NGS week | 2016 | NGS `avg_cushion` |
| `adot` | continuous | one_decimal | true | 0–35, lb 0 | 3 | targets | 1999/2016 | totals from `receiving_air_yards`; NGS IAY if using NGS avg path — this id is catalog minN 3 (targets), so prefer YTD air yards / targets for 1999+; NGS-only avg is `missing_source` pre-2016 |
| `catch_pct` | continuous | percent | true | 0–1 | 3 | targets | 1999 | derive |
| `target_share` | continuous | percent | true | 0–0.5 | 3 | team targets | 1999 | `target_share` |
| `air_yards_share` | continuous | percent | true | 0–0.6 | 3 | team air yards | 1999 | `air_yards_share` |
| `wopr` | continuous | ratio | true | 0–1, lb 0 | 3 | targets | 1999 | `wopr` |
| `racr` | continuous | ratio | true | 0–3, lb 0 | 3 | receiving air yards | 1999 | `racr` |
| `receiving_epa` | continuous | one_decimal | true | −15–20 | 3 | targets | 1999 | `receiving_epa` |
| `red_zone_targets` | discrete | count | true | 0–10, bw 1 | 1 | games | 1999 | PBP `receiver_player_id` |
| `route_pct` | continuous | percent | true | 0–1 | 1 | offensive snaps | 2016/2022 | `participation` / `ftn_charting`; missing chart → `missing_source` |
| `offensive_snap_pct` | continuous | percent | true | 0–1 | 1 | offensive snaps | 2012 | `snap_counts` |

### 8.4 Offensive line (`ol`) — 7 ids

| id | kind | format | higherIsBetter | xMin–xMax | minNBase | denom | startYear | source |
|---|---|---|---|---|---|---|---|---|
| `snaps_played` | discrete | count | true | 0–100, bw **5** | 1 | snap-weeks | 2012 | `snap_counts` |
| `snap_pct` | continuous | percent | true | 0–1 | 1 | offensive snaps | 2012 | `snap_counts.offense_pct` |
| `sacks_allowed` | discrete | count | false | 0–6, bw 1 | **null** | pass snaps | — | **always gray** |
| `pressures_allowed` | discrete | count | false | 0–12, bw 1 | **null** | pass snaps | — | **always gray** |
| `block_win_rate` | continuous | percent | true | 0–1 | **null** | pass snaps | — | **always gray** |
| `penalties` | discrete | count | false | 0–6, bw 1 | 1 | snap-weeks | 1999 | `player_stats.penalties` (noisy) |
| `penalty_yards` | discrete | yards | false | 0–50, bw **5** | 1 | snap-weeks | 1999 | `penalty_yards` |

Do not invent OL sacks/pressures/win rate from team-level data.

### 8.5 Defensive front (`def_front`, ED/DT/LB) — 12 ids

| id | kind | format | higherIsBetter | xMin–xMax | minNBase | denom | startYear | source |
|---|---|---|---|---|---|---|---|---|
| `tackles_solo` | discrete | count | true | 0–16, bw 1 | 1 | games | 1999 | `def_tackles_solo` |
| `tackles_ast` | discrete | count | true | 0–12, bw 1 | 1 | games | 1999 | `def_tackle_assists` |
| `tackles_combined` | discrete | count | true | 0–24, bw 1 | 1 | games | 1999/2018 | sum or PFR `def_tackles_combined` |
| `missed_tackles` | discrete | count | **false** | 0–7, bw 1 | 1 | games | 2018 | PFR `def_missed_tackles` |
| `sacks` | discrete | **one_decimal** | true | 0–7, bw **0.5** | 1 | games | 1999 | `def_sacks` (half-sacks) |
| `tackles_for_loss` | discrete | count | true | 0–6, bw 1 | 1 | games | 1999 | `def_tackles_for_loss` |
| `qb_hits` | discrete | count | true | 0–12, bw 1 | 1 | games | 1999 | `def_qb_hits` |
| `pressures` | discrete | count | true | 0–15, bw 1 | 1 | games | 2018 | `pfr_advstats` def |
| `hurries` | discrete | count | true | 0–10, bw 1 | 1 | games | 2018 | PFR def |
| `forced_fumbles` | discrete | count | true | 0–4, bw 1 | 1 | games | 1999 | `def_fumbles_forced` |
| `interceptions` | discrete | count | true | 0–3, bw 1 | 1 | games | 1999 | `def_interceptions` |
| `defensive_snap_pct` | continuous | percent | true | 0–1 | 1 | defensive snaps | 2012 | `snap_counts.defense_pct` |

### 8.6 Secondary (`secondary`) — 12 ids

| id | kind | format | higherIsBetter | xMin–xMax | minNBase | denom | startYear | source |
|---|---|---|---|---|---|---|---|---|
| `interceptions` | discrete | count | true | 0–4, bw 1 | 1 | games | 1999 | `def_interceptions` |
| `passes_defended` | discrete | count | true | 0–6, bw 1 | 1 | games | 1999 | `def_pass_defended` |
| `targets_allowed` | discrete | count | **false** | 0–18, bw 1 | 2 | targets allowed | 2018 | PFR `def_targets` |
| `completions_allowed` | discrete | count | **false** | 0–15, bw 1 | 2 | targets allowed | 2018 | `def_completions_allowed` |
| `receiving_yards_allowed` | continuous | yards | **false** | 0–250, lb 0 | 2 | targets allowed | 2018 | `def_yards_allowed` |
| `tds_allowed` | discrete | count | **false** | 0–3, bw 1 | 2 | targets allowed | 2018 | `def_receiving_td_allowed` |
| `completion_pct_allowed` | continuous | percent | **false** | 0–1 | 4 | targets allowed | 2018 | `def_completion_pct` |
| `rating_allowed` | continuous | rating | **false** | 0–158.3 | 4 | targets allowed | 2018 | `def_passer_rating_allowed` |
| `adot_allowed` | continuous | one_decimal | **false** | 0–30, lb 0 | 4 | targets allowed | 2018 | `def_adot` |
| `tackles_combined` | discrete | count | true | 0–16, bw 1 | 1 | games | 1999 | `def_tackles_*` |
| `missed_tackles` | discrete | count | **false** | 0–7, bw 1 | 1 | games | 2018 | PFR |
| `defensive_snap_pct` | continuous | percent | true | 0–1 | 1 | defensive snaps | 2012 | `snap_counts` |

### 8.7 Kicker (`kicker`) — 7 ids

| id | kind | format | higherIsBetter | xMin–xMax | minNBase | denom | startYear | source |
|---|---|---|---|---|---|---|---|---|
| `fg_attempts` | discrete | count | true | 0–8, bw 1 | 1 | FGA | 1999 | `fg_att` |
| `fg_made` | discrete | count | true | 0–8, bw 1 | 1 | FGA | 1999 | `fg_made` |
| `fg_pct` | continuous | percent | true | 0–1 | 1 | FGA | 1999 | derive |
| `fg_long` | discrete | yards | true | 0–70, bw **5** | 1 | FGA | 1999 | `fg_long` (YTD **max**) |
| `fg_40_49` | discrete | count | true | 0–4, bw 1 | 1 | attempts in bucket | 1999 | `fg_made_40_49` |
| `xp_attempts` | discrete | count | true | 0–10, bw 1 | 1 | XPA | 1999 | `pat_att` |
| `xp_made` | discrete | count | true | 0–10, bw 1 | 1 | XPA | 1999 | `pat_made` |

Sliders plan also mentions other FG buckets (`fg_made_50_59`, etc.). Knowball **only** has `fg_40_49`. Do not publish extra FG-bucket ids until the catalog adds them.

### 8.8 Punter (`punter`) — 6 ids

| id | kind | format | higherIsBetter | xMin–xMax | minNBase | denom | startYear | source |
|---|---|---|---|---|---|---|---|---|
| `punts` | discrete | count | true | 0–16, bw 1 | 2 | punts | 1999 | `pt_att` |
| `gross_punt_yards` | continuous | yards | true | 0–685, lb 0 | 2 | punts | 1999 | `pt_yards` |
| `net_punt_yards` | continuous | yards | true | 0–600, lb 0 | 2 | punts | 1999 | `pt_net_yards` |
| `inside_20` | discrete | count | true | 0–8, bw 1 | 2 | punts | 1999 | `pt_inside_20` |
| `touchbacks` | discrete | count | **false** | 0–6, bw 1 | 2 | punts | 1999 | `pt_touchback` |
| `fair_catches` | discrete | count | true | 0–8, bw 1 | 2 | punts | 1999 | `pt_fair_caught` |

### 8.9 Returner (`returner`) — 5 ids

| id | kind | format | higherIsBetter | xMin–xMax | minNBase | denom | startYear | source |
|---|---|---|---|---|---|---|---|---|
| `kick_returns` | discrete | count | true | 0–11, bw 1 | 1 | returns | 1999 | `kickoff_returns` |
| `punt_returns` | discrete | count | true | 0–11, bw 1 | 1 | returns | 1999 | `punt_returns` |
| `kick_return_yards` | continuous | yards | true | −10–305, lb 0 | 1 | kick returns | 1999 | `*_return_yards` |
| `punt_return_yards` | continuous | yards | true | −10–200, lb 0 | 1 | punt returns | 1999 | |
| `return_tds` | discrete | count | true | 0–2, bw 1 | 1 | returns | 1999 | `pt_return_tds`, `special_teams_tds` |

---

## 9. Supabase construction

Two layers. **Do not** put raw nflverse weeklies in the public viz schema.

### 9.1 Project layout

| Layer | Purpose | Who reads |
|---|---|---|
| **Local / private** (DuckDB, parquet, or schema `raw`) | nflverse extracts, id maps, weekly fact tables | Ballnet only |
| **Schema `viz`** (this section) | Normalized visualization store | Ballnet service role |
| **Storage buckets** | Denormalized `PlayerPageJson` + `players.json` | Public read (anon); Ballnet write |

Knowball will **not** use the Postgres REST API. RLS on `viz` should **deny anon**. Storage objects for pages/index should be **public read** (or signed URLs if you later want to hide them).

Recommended schemas:

- `raw` — optional; only if you insist on landing nflverse in Postgres. Otherwise keep parquet in ballnet.
- `viz` — required visualization store.
- `storage` buckets: `knowball-public`.

### 9.2 Required `viz` tables

#### `viz.players`

One row per GSIS player that may appear in search or player routes.

| Column | Type | Notes |
|---|---|---|
| `player_id` | text **PK** | GSIS |
| `display_name` | text | `PlayerBio.name` |
| `position` | text | PositionCode (section 3.4) |
| `team` | text | Latest known team abbr |
| `pfr_player_id` | text null | For snap/PFR joins |
| `headshot_url` | text null | optional, unused by skeleton |
| `updated_at` | timestamptz | |

#### `viz.player_seasons`

| Column | Type | Notes |
|---|---|---|
| `player_id` | text | FK → `players` |
| `season` | int | |
| `team` | text | Team for that season (last team if traded: last REG week ≤ as-of, or season-end) |
| `position` | text | PositionCode used for catalog hydration that season |
| PK | `(player_id, season)` | |

`PlayerBio.seasons` = distinct seasons in this table (or those with any `player_stat_values` rows).

#### `viz.league_distributions`

**One league shape per season / week / position group / stat.** Not per player. This table is **`distribution_scope = league_ytd` only** — do not store player-weekly curves here.

| Column | Type | Notes |
|---|---|---|
| `season` | int | |
| `as_of_week` | int | REG week 1–18 (or 22 if you include postseason later; **Knowball default is season YTD REG only** — do not mix POST into REG densities) |
| `position_group` | text | `qb` \| `backfield` \| `pass_catcher` \| `ol` \| `def_front` \| `secondary` \| `kicker` \| `punter` \| `returner` |
| `stat_id` | text | Catalog id |
| `kind` | text | catalog metadata `continuous` \| `discrete` |
| `x_min` | float8 | |
| `x_max` | float8 | |
| `y_max` | float8 | |
| `lower_bound` | float8 null | |
| `upper_bound` | float8 null | |
| `curve` | jsonb | `[{ "x": number, "y": number }, ...]` |
| `n_sample` | int | Qualified peers |
| `computed_at` | timestamptz | |
| PK | `(season, as_of_week, position_group, stat_id)` | |

Exactly one non-null `curve` per row. Histograms are not part of the contract.

**Later (do not create in v1):** `viz.player_distributions` — PK `(player_id, season, as_of_week, stat_id)`, same shape columns, `distribution_scope = player_weekly`. Publish path preferred: `dists/players/…` JSON even if the table exists.

#### `viz.player_stat_values`

Scalar overlay only.

| Column | Type | Notes |
|---|---|---|
| `player_id` | text | |
| `season` | int | |
| `as_of_week` | int | |
| `stat_id` | text | |
| `player_value` | float8 null | null if unavailable |
| `percentile` | float8 null | 0–100 oriented; null if not ready |
| `denom_ytd` | float8 null | |
| `min_n` | float8 null | `n_base * min(w, 4)` actually applied |
| `qualified` | boolean | |
| `unavailable_reason` | text null | `insufficient_sample` \| `missing_source` \| `not_in_nflverse` |
| PK | `(player_id, season, as_of_week, stat_id)` | |

Do **not** store `curve` here.

#### `viz.publish_manifest` (recommended)

Tracks which Storage objects are current.

| Column | Type |
|---|---|
| `player_id` | text |
| `season` | int |
| `as_of_week` | int |
| `storage_path` | text |
| `sha256` | text |
| `published_at` | timestamptz |
| PK | `(player_id, season, as_of_week)` |

#### `viz.meta_current_week` (recommended, single row)

| Column | Type | Notes |
|---|---|---|
| `id` | int PK check = 1 | singleton |
| `season` | int | e.g. 2025 |
| `as_of_week` | int | latest completed REG week you have computed |
| `updated_at` | timestamptz | |

### 9.3 DDL (run in Ballnet migrations; not in knowball)

```sql
create schema if not exists viz;

create table viz.players (
  player_id text primary key,
  display_name text not null,
  position text not null,
  team text not null,
  pfr_player_id text,
  headshot_url text,
  updated_at timestamptz not null default now()
);

create table viz.player_seasons (
  player_id text not null references viz.players (player_id),
  season int not null,
  team text not null,
  position text not null,
  primary key (player_id, season)
);

create table viz.league_distributions (
  season int not null,
  as_of_week int not null,
  position_group text not null,
  stat_id text not null,
  kind text not null check (kind in ('continuous', 'discrete')),
  x_min double precision not null,
  x_max double precision not null,
  y_max double precision not null,
  lower_bound double precision,
  upper_bound double precision,
  curve jsonb not null,
  n_sample int not null,
  computed_at timestamptz not null default now(),
  primary key (season, as_of_week, position_group, stat_id)
);

create table viz.player_stat_values (
  player_id text not null references viz.players (player_id),
  season int not null,
  as_of_week int not null,
  stat_id text not null,
  player_value double precision,
  percentile double precision,
  denom_ytd double precision,
  min_n double precision,
  qualified boolean not null,
  unavailable_reason text check (
    unavailable_reason is null
    or unavailable_reason in (
      'insufficient_sample',
      'missing_source',
      'not_in_nflverse'
    )
  ),
  primary key (player_id, season, as_of_week, stat_id)
);

create index player_stat_values_lookup
  on viz.player_stat_values (season, as_of_week, player_id);

create table viz.publish_manifest (
  player_id text not null,
  season int not null,
  as_of_week int not null,
  storage_path text not null,
  sha256 text,
  published_at timestamptz not null default now(),
  primary key (player_id, season, as_of_week)
);

create table viz.meta_current_week (
  id int primary key default 1 check (id = 1),
  season int not null,
  as_of_week int not null,
  updated_at timestamptz not null default now()
);

alter table viz.players enable row level security;
alter table viz.player_seasons enable row level security;
alter table viz.league_distributions enable row level security;
alter table viz.player_stat_values enable row level security;
alter table viz.publish_manifest enable row level security;
alter table viz.meta_current_week enable row level security;
-- no anon policies: service_role only
```

### 9.4 Storage bucket `knowball-public`

**Reserved prefixes — do not invent random paths later:**

| Path prefix | Content | v1? |
|---|---|---|
| `pages/` | `PlayerPageJson` | **yes** |
| `index/` | Search index + current week pointer | **yes** |
| `highlights/` | Home best-of-week / season boards | later |
| `teams/` | Team strength snapshots | later |
| `dists/players/` | Per-player distribution JSON (`player_weekly` scope) | later |
| `similarity/` | Trajectory neighbors / embeddings metadata | later |

v1 required objects:

| Path | Content |
|---|---|
| `index/players.json` | Search index (`schemaVersion` envelope) |
| `index/current.json` | `{ "schemaVersion": 1, "season", "asOfWeek" }` mirroring `meta_current_week` |
| `pages/{season}/w{week}/{player_id}.json` | `PlayerPageJson` |
| `pages/current/{player_id}.json` | Latest week for that player |

Public read; write with service role.

### 9.5 Optional `raw` tables (only if landing in Postgres)

If you keep nflverse in files, skip this. If you land in Supabase for ops, use a **private** schema and **never** expose it to Knowball.

Minimum internal facts (column names can follow nflverse; these are Ballnet-private):

| Table | Grain | Why |
|---|---|---|
| `raw.id_map` | player | GSIS, PFR, name, position |
| `raw.player_week_box` | player-week REG | `player_stats` subset of columns needed for catalog stats |
| `raw.ngs_passing_week` | player-week | TTT, IAY, CAY, aggressiveness, xComp, air yards diffs, CPOE |
| `raw.ngs_rushing_week` | player-week | TLOS, RYOE, 8+D, efficiency, expected rush yards |
| `raw.ngs_receiving_week` | player-week | avg YAC, xYAC, YAC OE, separation, cushion, IAY |
| `raw.snap_week` | player-week | offense/defense snaps and pct |
| `raw.pfr_rush_week` | player-week | broken tackles, YAC (contact) |
| `raw.pfr_rec_week` | player-week | drops |
| `raw.pfr_def_week` | player-week | pressures, hurries, missed tackles, coverage allowed stats |
| `raw.pbp_rz_week` | player-week | RZ rushes/targets |
| `raw.ftn_week` | player-week | drops / routes if used |
| `raw.ff_opportunity_week` | player-week | xFP |

These are **ETL inputs**, not Knowball contracts. Do not copy them into `viz`.

---

## 10. ETL pipeline (implement this)

Treat stages as a **DAG**, not a one-shot script that only exists to emit `PlayerPageJson`. Use `uv` for Python in ballnet.

**Shared spine (always):** A → B → C  
**Leg 1 player pages (v1):** D → E → F → G  
**Later products hang off B/C — do not fold them into G:**

| Stage | Depends on | When |
|---|---|---|
| H — Highlights / z-score boards | B (weekly panel) | later → `highlights/` |
| I — Player weekly densities | B | later → `dists/players/` + optional `viz.player_distributions` |
| J — Similarity / trajectories | B (+ multi-season features) | later → `similarity/` |
| K — Team aggregates | E/F + roster definition | later → `teams/` |

### Stage A — Ingest

Pull nflverse (or local cache) for seasons you will publish (minimum **1999** box, **2012** snaps, **2016** NGS, **2018** PFR adv, **2006** ff_opportunity, **2022** FTN if used for drops/routes).

Filter `season_type == 'REG'`. Drop NGS `week == 0`.

### Stage B — Canonical weekly panel (**spine**)

One row per `(player_id, season, week)` with all box columns plus joined NGS/PFR/snaps (left joins). Preserve nulls.

**Persist this panel.** It is the input for YTD, highlights, player-own densities, and trajectories. Re-running later stages must not require a different nflverse join path.

### Stage C — YTD as-of-week panel

For each `as_of_week` in `1..W` (and at least the current week for production):

- Aggregate per section 7.
- Compute `denom_ytd` and `min_n`.
- Set `qualified` / `unavailable_reason`.

### Stage D — League densities (`league_ytd` only)

For each `(season, as_of_week, position_group, stat_id)`:

- Collect qualified peer YTD values.
- Fit reflected KDE.
- Upsert `viz.league_distributions`.

Skip densities with `n_sample < 5` still **write the row** but player overlays may be `insufficient_sample` if the player also fails min-n; if the player qualifies uniquely early, you still need a league shape — use whatever qualified peers exist (can be small in week 1).

### Stage E — Player overlays

Upsert `viz.player_stat_values` for every catalog id for that player’s `position_group` **except** you may omit `alwaysUnavailable` ids.

Every **other** catalog id should have a row (qualified or not) so publish does not emit accidental `pending` once you are live. `pending` means “Ballnet has not run”, not “player sat”.

### Stage F — Bios

Upsert `viz.players` and `viz.player_seasons`. Rebuild `index/players.json` (with `schemaVersion`).

### Stage G — Publish `PlayerPageJson`

For each player-season-week:

```text
stats[] = for each catalog id in statsForPosition(position):
  if alwaysUnavailable: omit (Knowball will gray)
  else join player_stat_values + league_distributions
       copy curve/xMin/xMax/yMax/kind/bounds onto snapshot
       (prefer shared `league/*.json` merge — do not embed curve on every page)
```

Include `schemaVersion: 1`. Write Storage object. Update `publish_manifest` and `pages/current/`.

Do **not** compute highlights, team averages, similarity, or player-weekly KDEs inside this stage.

### Cadence

After each completed REG week: rerun C–G for that `as_of_week` (and only that week if YTD is incremental-safe). Historical weeks are immutable once the season is over unless you fix a bug. When H/I/J/K exist, they should be separately schedulable jobs off the same Stage B output.

Season dropdown on the player page reloads the **same player** for another `season` (default current). For a past season, `asOfWeek` should be the **final REG week** of that season (or week 18/17 depending on year). Put that in `pages/{season}/w{final}/{id}.json` and also as that season’s “current” if you add `pages/{season}/current/{id}.json` later. Minimum: `PlayerPageJson.asOfWeek` must be the week the densities were computed for.

---

## 11. Validation (do this before calling it done)

1. Snapshot `id` set ⊆ catalog ids for that position; no extras required.
2. Every non-`alwaysUnavailable` catalog id has a `player_stat_values` row after a full run.
3. `kind` matches catalog.
4. `percent` values ∈ [0, 1] (allow tiny float error).
5. Every `curve` monotonic x; integral ≈ 1 (including formerly discrete ids).
6. `higherIsBetter: false` stats: high raw interceptions → **low** stored percentile.
7. Missing NGS player: `unavailable_reason = missing_source`, `player_value` null, **not** 0.
8. Week 1 passer with 9 attempts on a rate stat with `minNBase=10`: unqualified (`min_n=10`).
9. Week 5 passer with 32 attempts on volume stats with `minNBase=8`: qualified (`min_n=32`).
10. OL `sacks_allowed` never `ready`.
11. Knowball hydrate: fixture player + one real JSON → ready rows chart; missing ids still listed.

---

## 12. v1 out of scope / v2 contracts (deferred products)

**Do not implement these in the first ETL ship.** Do structure Stages A–B and Storage prefixes so they plug in without redesign.

| Product | v1 | Later publish (JSON-first; still no Knowball Postgres) |
|---|---|---|
| Home best-of-week (z-scores, breakouts) | skip | `highlights/{season}/w{week}.json` from weekly panel + z-score / rarity primitives |
| Best of season / all-time boards | skip | `highlights/{season}/season.json`, `highlights/all-time/…` |
| “1 in N” rarity framing | skip | Fields on highlight (or tooltip) payloads from shared tail → `one_in_n` |
| Overall player percentile | skip | Additive `overallPercentile` on page/index JSON (recipe defined in Ballnet) |
| Team starting average percentile | skip | `teams/{season}/w{week}.json` after roster/starter definition |
| Compare **individual** player distributions | skip | `dists/players/{id}/{season}/w{week}.json` (`player_weekly` scope) or a thin compare object; Knowball fetches A+B |
| Trajectory similarity | skip | `similarity/{id}.json` neighbors; embeddings stay in Ballnet |
| Draft matrices / Clerk / Stripe / premium RLS | skip | Old checklist Leg 2 — unrelated to Leg 1 viz |
| Last-10 / all-time **player page** windows | skip | Unless a human asks; default remains season YTD |
| Knowball PostgREST / `@supabase/supabase-js` | **never for Leg 1** | Publish more JSON instead |
| Inventing catalog ids (extra FG buckets, OL win rate, 40+ deep) | skip | Catalog change in knowball first |

Still forbidden forever for this architecture: embedding Knowball with a Postgres client “just for compare,” or folding highlight/similarity logic into Stage G.

---

## 13. Files to keep open while implementing

| File (in knowball) | Why |
|---|---|
| `.plans/NFL Stats Sliders.md` | Sources, min-n, zero mass, joins |
| `web/src/lib/payload.ts` | JSON types |
| `web/src/lib/distribution.ts` | curve shapes, CDF used in UI |
| `web/src/lib/catalog/*.ts` | ids, domains, `higherIsBetter`, format |
| `web/src/lib/catalog/hydrate.ts` | overlay rules |
| `web/src/lib/stat-status.ts` | gray-row copy / ready predicate |
| `docs/architecture/data-contracts.md` | store vs JSON |
| `docs/adr/2026-08-19-visualization-json-store.md` | why two tables + files |

---

## 14. Definition of done

Ballnet can, for a chosen `season` + `as_of_week`:

1. Fill `viz.players`, `viz.player_seasons`, `viz.league_distributions`, `viz.player_stat_values`.
2. Persist the Stage B weekly panel so a later job could recompute without a new nflverse join design.
3. Upload `index/players.json` and at least one real GSIS `PlayerPageJson` (`schemaVersion: 1`) that hydrates a QB (and one other group) in Knowball without code changes except pointing the fetch URL at Storage.
4. Gray rows behave: NGS-missing, sample-short, and OL-unavailable are distinguishable via `unavailableReason` / omitted snapshots / `alwaysUnavailable`.
5. Storage only uses reserved prefixes (`pages/`, `index/` for v1). No highlight/team/dist/similarity objects required yet.

`overallPercentile`, highlights, player-weekly densities, and similarity are **not** part of Definition of Done.

---

## 15. Extensibility invariants (do not violate)

1. **JSON-first forever for Knowball Leg 1.** Ballnet may use Postgres/parquet freely; Knowball only fetches Storage (or static) JSON.
2. **Weekly panel is the spine.** All future scoring products read Stage B (or a thin derivative), not one-off nflverse scrapes.
3. **Do not overload `league_distributions`.** Player-own and peer-week densities use `distribution_scope` / separate tables or paths (`player_weekly`, `league_weekly`).
4. **Additive publish envelopes.** Every object carries `schemaVersion`. Unknown keys are allowed for forward compatibility; breaking renames require a version bump + Knowball change.
5. **Reserved Storage prefixes.** New products get new prefixes from the table in §9.4 — never dump ad-hoc files at the bucket root.
6. **Shared scoring library.** Percentile/CDF, z-score, and `one_in_n` live once in Ballnet.
7. **No payload bloat on player pages.** Do not ship every player’s weekly KDE inside `PlayerPageJson`; publish `dists/` (or compare JSON) when that UI exists.
8. **Catalog remains the id authority.** Ballnet does not invent slider rows; new stats start as knowball catalog ids.