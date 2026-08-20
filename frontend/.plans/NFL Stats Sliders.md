Ramp-and-hold is specified once below, then reused in the **Min n** column as `base × min(w, 4)`. `w` is the calendar week.

**Min n formula**

\[
\min\_n = n_{\text{base}} \times \min(w, 4)
\]

- Weeks 1–4 of the season REG sample: ramp  
- Week 5+: hold at \(4 n_{\text{base}}\)  
- `w` is the **as-of NFL week** being viewed, not weeks since the player's debut. A Week 10 starter faces the hold (`4 n_{\text{base}}`) immediately.  
- Enable when **season-to-date** cumulative denom \(\ge \min\_n\)  
- Ignore `PRE`; ignore NGS `week == 0` in weekly plots  
- Rate stats use the **denominator** as the count; NGS stats also require a non-null NGS row that week  

Join keys: box score / PBP = `player_id` (GSIS); NGS = `player_gsis_id` → `player_id`; PFR / snaps = `pfr_player_id` → `gsis_id` via `ff_playerids`.

---

### Quarterback (QB)

| Stat                | Data Type   | Best Dist.           | Conjugate  | (Typical) / [Min, Max] | nflverse availability                             | Grain       | Unit          | Denom                         | Min n (ramp–hold)                                       | Source                            | Start yr    | Plot               | Zero mass                     | Join key                       |
| ------------------- | ----------- | -------------------- | ---------- | ---------------------- | ------------------------------------------------- | ----------- | ------------- | ----------------------------- | ------------------------------------------------------- | --------------------------------- | ----------- | ------------------ | ----------------------------- | ------------------------------ |
| Pass Attempts       | Discrete    | ZI-Poisson / NegBin  | Gamma      | (25–40) / [0, 70]      | **All logged**                                    | player-week | count         | — (this *is* denom for rates) | `base=8 att` → 8/16/24/**32**                           | `player_stats`                    | 1999        | Hist               | Med (backups)                 | `player_id`                    |
| Completions         | Discrete    | Binomial \| attempts | Beta       | (15–25) / [0, 45]      | **All logged**                                    | player-week | count         | attempts                      | same as attempts                                        | `player_stats`                    | 1999        | Hist               | Low                           | `player_id`                    |
| Passing Yards       | Continuous  | Hurdle + Log-Normal  | NIG (log)  | (175–275) / [−10, 554] | **All logged**                                    | player-week | yards         | attempts                      | `base=8 att` → hold **32**                              | `player_stats`                    | 1999        | KDE (yds>0) + hist | Med                           | `player_id`                    |
| Passing TDs         | Discrete    | ZI-Poisson           | Gamma      | (0–3) / [0, 7]         | **All logged**                                    | player-week | count         | games w/ att                  | `base=1` → hold **4**                                   | `player_stats`                    | 1999        | Hist               | **High**                      | `player_id`                    |
| Interceptions       | Discrete    | ZI-Poisson           | Gamma      | (0–2) / [0, 7]         | **All logged**                                    | player-week | count         | games w/ att                  | `base=1` → hold **4**                                   | `player_stats`                    | 1999        | Hist               | **High**                      | `player_id`                    |
| Sacks Taken         | Discrete    | ZI-Poisson           | Gamma      | (1–3) / [0, 12]        | **All logged**                                    | player-week | count         | games w/ att                  | `base=1` → hold **4**                                   | `player_stats`                    | 1999        | Hist               | **High**                      | `player_id`                    |
| Completion %        | Cont. (0–1) | Beta                 | Beta-Binom | (0.60–0.70) / [0, 1]   | **Usage-qualified**                               | player-week | percent       | attempts                      | `base=10 att` → hold **40**                             | derive `player_stats`             | 1999        | KDE bounded        | Low                           | `player_id`                    |
| Passer Rating       | Continuous  | Normal (bounded)     | NIG        | (80–105) / [0, 158.3]  | **Compute all usage QBs**; NGS rating is NGS-only | player-week | rating        | attempts                      | `base=10 att` → hold **40**                             | compute from box; optional NGS    | 1999 / 2016 | KDE                | Low                           | `player_id` / `player_gsis_id` |
| TTT                 | Continuous  | Log-Normal           | NIG        | (2.5–2.9s) / [1.5, 6]  | **NGS-qualified**                                 | player-week | seconds       | NGS pass attempts (implicit)  | `base=1 NGS row` → hold **4**                           | `nextgen_stats` passing           | 2016        | KDE                | None                          | `player_gsis_id`               |
| IAY                 | Continuous  | Normal               | NIG        | (7.0–9.5) / [0, 25]    | **NGS-qualified**                                 | player-week | yards/att     | NGS week                      | `base=1 NGS row` → hold **4**                           | NGS passing                       | 2016        | KDE                | None                          | `player_gsis_id`               |
| CAY                 | Continuous  | Normal               | NIG        | (5.0–7.5) / [0, 20]    | **NGS-qualified**                                 | player-week | yards/att     | NGS week                      | `base=1 NGS row` → hold **4**                           | NGS passing                       | 2016        | KDE                | None                          | `player_gsis_id`               |
| AGG %               | Cont. (0–1) | Beta                 | Beta-Binom | (0.10–0.20) / [0, 1]   | **NGS-qualified**                                 | player-week | percent       | NGS week                      | `base=1 NGS row` → hold **4**                           | NGS `aggressiveness`              | 2016        | KDE bounded        | Low                           | `player_gsis_id`               |
| CPOE                | Continuous  | Normal               | NIG        | (−4–+4%) / [−25, +25]  | **Mostly usage**; NGS CPOE stricter               | player-week | pp (or %)     | attempts                      | `base=10 att` → hold **40**; also require non-null CPOE | `player_stats.passing_cpoe` / NGS | 1999 / 2016 | KDE                | Low                           | `player_id`                    |
| Passing EPA         | Continuous  | Normal / t           | NIG        | (−8–+12) / [−40, +40]  | **Usage-qualified**                               | player-week | EPA           | attempts                      | `base=8 att` → hold **32**                              | `player_stats`                    | 1999        | KDE                | Low                           | `player_id`                    |
| PACR                | Continuous  | Gamma                | Gamma      | (0.8–1.2) / [0, ~3]    | **Usage-qualified**                               | player-week | ratio         | passing_air_yards             | `base=8 att` → hold **32**                              | `player_stats`                    | 1999        | KDE                | Low                           | `player_id`                    |
| Expected Cmp %      | Cont. (0–1) | Beta                 | Beta-Binom | (0.62–0.70) / [0, 1]   | **NGS-qualified**                                 | player-week | percent       | NGS week                      | `base=1 NGS row` → hold **4**                           | NGS                               | 2016        | KDE bounded        | None                          | `player_gsis_id`               |
| Air Yards Diff.     | Continuous  | Normal               | NIG        | (−2–+1) / [−10, +8]    | **NGS-qualified**                                 | player-week | yards         | NGS week                      | `base=1 NGS row` → hold **4**                           | NGS                               | 2016        | KDE                | None                          | `player_gsis_id`               |
| Air Yards to Sticks | Continuous  | Normal               | NIG        | (−1–+2) / [−8, +8]     | **NGS-qualified**                                 | player-week | yards         | NGS week                      | `base=1 NGS row` → hold **4**                           | NGS                               | 2016        | KDE                | None                          | `player_gsis_id`               |
| Deep Att (20+/40+)  | Discrete    | ZI-Poisson           | Gamma      | (2–8) / [0, 20]        | **All logged**                                    | player-week | count         | attempts                      | `base=8 att` → hold **32**                              | `passing_20`, `passing_40`        | 1999        | Hist               | Med                           | `player_id`                    |
| Rush Att/Yds/TDs    | Mixed       | same as RB           | —          | dual-threat            | **All logged**; gray pocket QBs                   | player-week | count / yards | carries                       | `base=3 car` → hold **12**                              | `player_stats`                    | 1999        | Hist / KDE         | **High** if few designed runs | `player_id`                    |
| Offensive Snap %    | Cont. (0–1) | Beta                 | Beta-Binom | (0.95–1.00) / [0, 1]   | **Snap-qualified**                                | player-week | percent       | off. snaps                    | `base=1 snap-row` → hold **4**                          | `snap_counts`                     | 2012        | KDE bounded        | Low                           | `pfr_player_id`→GSIS           |

---

### Backfield (RB & FB)

| Stat | Data Type | Best Dist. | Conjugate | (Typical) / [Min, Max] | nflverse availability | Grain | Unit | Denom | Min n | Source | Start yr | Plot | Zero mass | Join key |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Rush Attempts | Discrete | ZI-Poisson / NegBin | Gamma | (10–20) / [0, 45] | **All logged** | player-week | count | — | `base=5 car` → hold **20** | `player_stats.carries` | 1999 | Hist | Med | `player_id` |
| Rushing Yards | Continuous | Hurdle + Log-Normal | NIG (log) | (40–100) / [−15, 296] | **All logged** | player-week | yards | carries | `base=5 car` → hold **20** | `player_stats` | 1999 | KDE (yds>0) | Med | `player_id` |
| Rushing TDs | Discrete | ZI-Poisson | Gamma | (0–1) / [0, 6] | **All logged** | player-week | count | games w/ car | `base=1` → hold **4** | `player_stats` | 1999 | Hist | **High** | `player_id` |
| Fumbles | Discrete | ZI-Poisson | Gamma | (0–1) / [0, 7] | **All logged** | player-week | count | touches | `base=1` → hold **4** | `rushing_fumbles` / `fumbles_lost_total` | 1999 | Hist | **High** | `player_id` |
| Broken Tackles | Discrete | ZI-Poisson | Gamma | (0–4) / [0, 16] | **PFR-charted 2018+** (not curated yet) | player-week | count | carries | `base=5 car` → hold **20** + PFR row | `pfr_advstats` rush | 2018 | Hist | **High** | `pfr_player_id` |
| Yards After Contact | Continuous | Gamma | Gamma | (15–50) / [0, 175] | **PFR-charted 2018+** | player-week | yards | carries | `base=5 car` → hold **20** | PFR rush | 2018 | KDE | Low–Med | `pfr_player_id` |
| TLOS | Continuous | Log-Normal | NIG | (2.6–3.1s) / [1.5, 5] | **NGS-qualified** | player-week | seconds | NGS rush week | `base=1 NGS row` → hold **4** | NGS rushing | 2016 | KDE | None | `player_gsis_id` |
| RYOE | Continuous | Normal | NIG | (−0.5–+1.5) / [−10, +15] | **NGS-qualified** | player-week | yards or ypc | NGS week | `base=1 NGS row` → hold **4**; prefer per-att | NGS `rush_yards_over_expected[_per_att]` | 2016 | KDE | Low | `player_gsis_id` |
| 8+D % | Cont. (0–1) | Beta | Beta-Binom | (0.10–0.35) / [0, 1] | **NGS-qualified** | player-week | percent | NGS week | `base=1 NGS row` → hold **4** | NGS | 2016 | KDE bounded | Low | `player_gsis_id` |
| Rushing EPA | Continuous | Normal / t | NIG | (−4–+6) / [−20, +20] | **Usage-qualified** | player-week | EPA | carries | `base=5 car` → hold **20** | `player_stats` | 1999 | KDE | Low | `player_id` |
| Yards / Carry | Continuous | Normal | NIG | (3.5–5.5) / [−5, 20] | **Usage-qualified** | player-week | ypc | carries | `base=5 car` → hold **20** | derive | 1999 | KDE | Low | `player_id` |
| NGS Efficiency | Continuous | Log-Normal | NIG | (~3.5–4.5) | **NGS-qualified** | player-week | ratio | NGS week | `base=1 NGS row` → hold **4** | NGS `efficiency` | 2016 | KDE | None | `player_gsis_id` |
| Expected Rush Yds | Continuous | Normal | NIG | (30–90) | **NGS-qualified** | player-week | yards | NGS week | `base=1 NGS row` → hold **4** | NGS | 2016 | KDE | None | `player_gsis_id` |
| Targets / Rec / Rec Yds | Mixed | Pois / Binom / LogN | Gamma/Beta/NIG | pass-catching | **All logged** | player-week | count / yards | targets | `base=2 tgt` → hold **8** | `player_stats` | 1999 | Hist / KDE | **High** for non-receiving backs | `player_id` |
| Target Share / WOPR | Cont. (0–1) | Beta | Beta-Binom | (0.05–0.15) / [0, 0.40] | **Usage-qualified** | player-week | share | team targets (built-in) | `base=2 tgt` → hold **8** | `player_stats` | 1999 | KDE bounded | Med | `player_id` |
| Offensive Snap % | Cont. (0–1) | Beta | Beta-Binom | (0.40–0.80) / [0, 1] | **Snap-qualified** | player-week | percent | off. snaps | `base=1 snap-row` → hold **4** | `snap_counts` | 2012 | KDE bounded | Low | `pfr_player_id` |
| RZ Touches | Discrete | ZI-Poisson | Gamma | (0–4) / [0, 12] | **PBP, usage-qualified** | player-week | count | games | `base=1` → hold **4** | `pbp` | 1999 | Hist | **High** | `rusher/receiver_player_id` |
| Opportunity / xFP | Continuous | Gamma | Gamma | varies | **Usage-qualified** | player-week | FP / yards | games | `base=1` → hold **4** | `ff_opportunity` | 2006 | KDE | Low | `player_id` |

---

### Pass Catchers (WR & TE)

| Stat | Data Type | Best Dist. | Conjugate | (Typical) / [Min, Max] | nflverse availability | Grain | Unit | Denom | Min n | Source | Start yr | Plot | Zero mass | Join key |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Targets | Discrete | ZI-Poisson / NegBin | Gamma | (3–10) / [0, 21] | **All logged** | player-week | count | — | `base=3 tgt` → hold **12** | `player_stats` | 1999 | Hist | Med | `player_id` |
| Receptions | Discrete | Binomial \| targets | Beta | (2–7) / [0, 21] | **All logged** | player-week | count | targets | same as targets | `player_stats` | 1999 | Hist | Med | `player_id` |
| Receiving Yards | Continuous | Hurdle + Log-Normal | NIG (log) | (30–85) / [−10, 336] | **All logged** | player-week | yards | targets | `base=3 tgt` → hold **12** | `player_stats` | 1999 | KDE (yds>0) | Med | `player_id` |
| Receiving TDs | Discrete | ZI-Poisson | Gamma | (0–1) / [0, 5] | **All logged** | player-week | count | games | `base=1` → hold **4** | `player_stats` | 1999 | Hist | **High** | `player_id` |
| Drops | Discrete | Binomial \| targets | Beta | (0–1) / [0, 5] | **PFR partial 2018+**; FTN 2022+ | player-week | count | targets | `base=3 tgt` → hold **12** + charted row | PFR rec / FTN `is_drop` | 2018 / 2022 | Hist | **High** | `pfr_player_id` / PBP ids |
| YAC (total) | Continuous | Gamma | Gamma | (10–40) / [0, 175] | **All logged** | player-week | yards | receptions | `base=2 rec` → hold **8** | `receiving_yards_after_catch` | 1999 | KDE | Med | `player_id` |
| Avg YAC | Continuous | Gamma | Gamma | (3–7) / [0, 20] | **NGS-qualified** | player-week | yards/tgt | NGS rec week | `base=1 NGS row` → hold **4** | NGS receiving | 2016 | KDE | None | `player_gsis_id` |
| Separation | Continuous | Gamma / Log-Normal | NIG | (2.4–3.6) / [0, 9] | **NGS-qualified** | player-week | yards | NGS week | `base=1 NGS row` → hold **4** | NGS `avg_separation` | 2016 | KDE | None | `player_gsis_id` |
| TAY / aDOT | Continuous | Normal | NIG | (8.5–14.5) / [0, 35] | **NGS avg**; totals for all | player-week | yards | targets / NGS | totals: `base=3 tgt` → hold **12**; NGS avg: `base=1 NGS row` → hold **4** | `receiving_air_yards` / NGS IAY | 1999 / 2016 | KDE | Low | `player_id` / GSIS |
| xYAC | Continuous | Gamma | Gamma | (8–35 avg scale) | **NGS-qualified** | player-week | yards (avg) | NGS week | `base=1 NGS row` → hold **4** | NGS `avg_expected_yac` | 2016 | KDE | None | `player_gsis_id` |
| YAC OE | Continuous | Normal | NIG | (−1–+2) | **NGS-qualified** | player-week | yards | NGS week | `base=1 NGS row` → hold **4** | NGS `avg_yac_above_expectation` | 2016 | KDE | None | `player_gsis_id` |
| Cushion | Continuous | Gamma | Gamma | (5–8) / [0, 15] | **NGS-qualified** | player-week | yards | NGS week | `base=1 NGS row` → hold **4** | NGS `avg_cushion` | 2016 | KDE | None | `player_gsis_id` |
| Catch % | Cont. (0–1) | Beta | Beta-Binom | (0.55–0.75) / [0, 1] | **Usage-qualified** | player-week | percent | targets | `base=3 tgt` → hold **12** | derive / NGS catch % | 1999 | KDE bounded | Low | `player_id` |
| Target Share | Cont. (0–1) | Beta | Beta-Binom | (0.10–0.30) | **Usage-qualified** | player-week | share | team targets | `base=3 tgt` → hold **12** | `target_share` | 1999 | KDE bounded | Med | `player_id` |
| Air Yards Share | Cont. (0–1) | Beta | Beta-Binom | (0.10–0.40) | **Usage** + NGS share | player-week | share | team air yards | `base=3 tgt` → hold **12** | `air_yards_share` / NGS | 1999 / 2016 | KDE bounded | Med | `player_id` |
| WOPR | Continuous | Gamma | Gamma | (0.20–0.70) | **Usage-qualified** | player-week | index | targets | `base=3 tgt` → hold **12** | `wopr` | 1999 | KDE | Med | `player_id` |
| RACR | Continuous | Log-Normal | NIG | (0.7–1.4) | **Usage-qualified** | player-week | ratio | rec air yards | `base=3 tgt` → hold **12** | `racr` | 1999 | KDE | Low | `player_id` |
| Receiving EPA | Continuous | Normal / t | NIG | (−4–+10) | **Usage-qualified** | player-week | EPA | targets | `base=3 tgt` → hold **12** | `receiving_epa` | 1999 | KDE | Low | `player_id` |
| Offensive Snap % | Cont. (0–1) | Beta | Beta-Binom | (0.50–0.95) | **Snap-qualified** | player-week | percent | off. snaps | `base=1 snap-row` → hold **4** | `snap_counts` | 2012 | KDE bounded | Low | `pfr_player_id` |
| RZ Targets | Discrete | ZI-Poisson | Gamma | (0–3) / [0, 10] | **PBP** | player-week | count | games | `base=1` → hold **4** | `pbp` | 1999 | Hist | **High** | `receiver_player_id` |
| Route % | Cont. (0–1) | Beta | Beta-Binom | (0.40–0.95) | **Partial** participation/FTN | player-week | percent | routes / off snaps | `base=1 charted row` → hold **4** | `participation` / `ftn_charting` | 2016 / 2022 | KDE bounded | Med | GSIS on play |

---

### Offensive Line (T / G / C)

| Stat | Data Type | Best Dist. | Conjugate | (Typical) / [Min, Max] | nflverse availability | Grain | Unit | Denom | Min n | Source | Start yr | Plot | Zero mass | Join key |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Snaps Played | Discrete | Poisson (truncated) | Gamma | (55–75) / [0, 100] | **Snap-qualified** | player-week | count | — | `base=1 snap-row` → hold **4** | `snap_counts` | 2012 | Hist | Low | `pfr_player_id` |
| Snap % | Cont. (0–1) | Beta | Beta-Binom | (0.90–1.00) / [0, 1] | **Snap-qualified** | player-week | percent | off. snaps | `base=1 snap-row` → hold **4** | `snap_counts.offense_pct` | 2012 | KDE bounded | Low | `pfr_player_id` |
| Sacks Allowed | Discrete | ZI-Poisson | Gamma | (0–1) / [0, 6] | **Not in nflverse (player OL)** | — | count | pass snaps | — (always gray) | — | — | — | — | — |
| Pressures Allowed | Discrete | ZI-Poisson | Gamma | (0–3) / [0, 12] | **Not in nflverse (player OL)** | — | count | pass snaps | — (always gray) | — | — | — | — | — |
| Penalties | Discrete | ZI-Poisson | Gamma | (0–2) / [0, 6] | **Partial, noisy** | player-week | count | snap-weeks | `base=1` → hold **4** | `player_stats.penalties` | 1999 | Hist | **High** | `player_id` |
| Penalty Yards | Discrete | ZI-Gamma | Gamma | (0–15) / [0, 50] | **Partial** | player-week | yards | snap-weeks | `base=1` → hold **4** | `penalty_yards` | 1999 | Hist | **High** | `player_id` |
| Block Win Rate | Cont. (0–1) | Beta | Beta-Binom | (0.85–0.95) | **Not in nflverse** | — | percent | — | — (always gray) | — | — | — | — | — |

---

### Defensive Front (ED / DT / LB)

| Stat | Data Type | Best Dist. | Conjugate | (Typical) / [Min, Max] | nflverse availability | Grain | Unit | Denom | Min n | Source | Start yr | Plot | Zero mass | Join key |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Tackles Solo | Discrete | NegBin | Gamma | (2–6) / [0, 16] | **All logged** | player-week | count | def snaps / games | `base=1` → hold **4** | `def_tackles_solo` | 1999 | Hist | Med | `player_id` |
| Tackles Ast | Discrete | NegBin | Gamma | (1–4) / [0, 12] | **All logged** | player-week | count | games | `base=1` → hold **4** | `def_tackle_assists` | 1999 | Hist | Med | `player_id` |
| Combined Tackles | Discrete | NegBin | Gamma | (3–8) / [0, 24] | **All logged** / PFR | player-week | count | games | `base=1` → hold **4** | sum or PFR `def_tackles_combined` | 1999 / 2018 | Hist | Low–Med | `player_id` / PFR |
| Sacks | Discrete | ZI-Poisson | Gamma | (0–1) / [0, 7] | **All logged** | player-week | count | games | `base=1` → hold **4** | `def_sacks` | 1999 | Hist | **High** | `player_id` |
| TFL | Discrete | ZI-Poisson | Gamma | (0–2) / [0, 6] | **All logged** | player-week | count | games | `base=1` → hold **4** | `def_tackles_for_loss` | 1999 | Hist | **High** | `player_id` |
| QB Hits | Discrete | ZI-Poisson | Gamma | (0–3) / [0, 12] | **All logged** | player-week | count | games | `base=1` → hold **4** | `def_qb_hits` | 1999 | Hist | **High** | `player_id` |
| Pressures | Discrete | ZI-Poisson | Gamma | (0–4) / [0, 15] | **PFR 2018+ (not ingested yet)** | player-week | count | games + PFR row | `base=1` → hold **4** | `pfr_advstats` def | 2018 | Hist | **High** | `pfr_player_id` |
| Forced Fumbles | Discrete | ZI-Poisson | Gamma | (0–1) / [0, 4] | **All logged** | player-week | count | games | `base=1` → hold **4** | `def_fumbles_forced` | 1999 | Hist | **High** | `player_id` |
| INTs | Discrete | ZI-Poisson | Gamma | (0–0) / [0, 3] | **All logged** | player-week | count | games | `base=1` → hold **4** | `def_interceptions` | 1999 | Hist | **High** | `player_id` |
| Hurries / Hits (PFR) | Discrete | ZI-Poisson | Gamma | (0–3) | **PFR-charted** | player-week | count | games | `base=1` → hold **4** | PFR def | 2018 | Hist | **High** | `pfr_player_id` |
| Missed Tackles | Discrete | ZI-Poisson | Gamma | (0–2) / [0, 7] | **PFR-charted** | player-week | count | games | `base=1` → hold **4** | PFR `def_missed_tackles` | 2018 | Hist | **High** | `pfr_player_id` |
| Def Snap % | Cont. (0–1) | Beta | Beta-Binom | (0.50–0.95) | **Snap-qualified** | player-week | percent | def snaps | `base=1 snap-row` → hold **4** | `snap_counts.defense_pct` | 2012 | KDE bounded | Low | `pfr_player_id` |

---

### Secondary (CB / FS / SS)

| Stat | Data Type | Best Dist. | Conjugate | (Typical) / [Min, Max] | nflverse availability | Grain | Unit | Denom | Min n | Source | Start yr | Plot | Zero mass | Join key |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Interceptions | Discrete | ZI-Poisson | Gamma | (0–1) / [0, 4] | **All logged** | player-week | count | games | `base=1` → hold **4** | `def_interceptions` | 1999 | Hist | **High** | `player_id` |
| Passes Defended | Discrete | ZI-Poisson | Gamma | (0–2) / [0, 6] | **All logged** | player-week | count | games | `base=1` → hold **4** | `def_pass_defended` | 1999 | Hist | **High** | `player_id` |
| Targets Allowed | Discrete | Poisson / NegBin | Gamma | (2–8) / [0, 18] | **PFR 2018+ (ingest def)** | player-week | count | — (denom for coverage rates) | `base=2 tgt allwd` → hold **8** | PFR `def_targets` | 2018 | Hist | Med | `pfr_player_id` |
| Completions Allowed | Discrete | Binomial \| tgt allwd | Beta | (1–5) / [0, 15] | **PFR-charted** | player-week | count | targets allowed | same as targets allowed | `def_completions_allowed` | 2018 | Hist | Med | `pfr_player_id` |
| Rec Yds Allowed | Continuous | Log-Normal | NIG (log) | (20–60) / [0, 250] | **PFR-charted** | player-week | yards | targets allowed | `base=2` → hold **8** | `def_yards_allowed` | 2018 | KDE | Med | `pfr_player_id` |
| Missed Tackles | Discrete | ZI-Poisson | Gamma | (0–2) / [0, 7] | **PFR-charted** | player-week | count | games | `base=1` → hold **4** | `def_missed_tackles` | 2018 | Hist | **High** | `pfr_player_id` |
| Cmp % Allowed | Cont. (0–1) | Beta | Beta-Binom | (0.50–0.70) | **PFR-charted** | player-week | percent | targets allowed | `base=4 tgt allwd` → hold **16** | `def_completion_pct` | 2018 | KDE bounded | Low | `pfr_player_id` |
| Rating Allowed | Continuous | Normal | NIG | (70–110) / [0, 158.3] | **PFR-charted** | player-week | rating | targets allowed | `base=4` → hold **16** | `def_passer_rating_allowed` | 2018 | KDE | Low | `pfr_player_id` |
| aDOT Allowed | Continuous | Normal | NIG | (7–14) / [0, 30] | **PFR-charted** | player-week | yards | targets allowed | `base=4` → hold **16** | `def_adot` | 2018 | KDE | None | `pfr_player_id` |
| TDs Allowed | Discrete | ZI-Poisson | Gamma | (0–1) / [0, 3] | **PFR-charted** | player-week | count | targets allowed | `base=2` → hold **8** | `def_receiving_td_allowed` | 2018 | Hist | **High** | `pfr_player_id` |
| Tackles | Discrete | NegBin | Gamma | (2–7) / [0, 16] | **All logged** | player-week | count | games | `base=1` → hold **4** | `def_tackles_*` | 1999 | Hist | Med | `player_id` |
| Def Snap % | Cont. (0–1) | Beta | Beta-Binom | (0.70–1.00) | **Snap-qualified** | player-week | percent | def snaps | `base=1 snap-row` → hold **4** | `snap_counts` | 2012 | KDE bounded | Low | `pfr_player_id` |

---

### Special Teams (K / P / Returners)

| Stat | Data Type | Best Dist. | Conjugate | (Typical) / [Min, Max] | nflverse availability | Grain | Unit | Denom | Min n | Source | Start yr | Plot | Zero mass | Join key |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FG Attempts | Discrete | Poisson | Gamma | (1–3) / [0, 8] | **All logged K** | player-week | count | — | `base=1 FGA` → hold **4** | `fg_att` | 1999 | Hist | Med | `player_id` |
| FG Made | Discrete | Binomial \| FGA | Beta | (1–3) / [0, 8] | **All logged K** | player-week | count | fg_att | same as FGA | `fg_made` | 1999 | Hist | Med | `player_id` |
| FG % | Cont. (0–1) | Beta | Beta-Binom | (0.80–0.95) / [0, 1] | **Usage-qualified** | player-week *or* rolling | percent | fg_att | `base=1 FGA` → hold **4** (noisy; 8 hold is nicer if you want stability) | `fg_pct` | 1999 | KDE bounded | Low | `player_id` |
| XP Made / Att | Discrete | Binomial | Beta | (1–3) / [0, 10] | **All logged K** | player-week | count | pat_att | `base=1 XPA` → hold **4** | `pat_made`, `pat_att` | 1999 | Hist | Med | `player_id` |
| FG by Distance | Discrete / rate | Binomial / bucket | Beta | varies | **All logged K** | player-week | count or % | att in bucket | `base=1 bucket-att` → hold **4** | `fg_made_40_49`, etc. | 1999 | Hist | **High** per bucket | `player_id` |
| Longest FG | Discrete | Empirical | — | (40–55) / [0, 70+] | **All logged K** | player-week | yards | FGA>0 | `base=1 FGA` → hold **4** | `fg_long` | 1999 | Hist | Med | `player_id` |
| Punts | Discrete | Poisson | Gamma | (3–6) / [0, 16] | **All logged P** | player-week | count | — | `base=2 punts` → hold **8** | `pt_att` | 1999 | Hist | Low | `player_id` |
| Gross Punt Yds | Continuous | Normal | NIG | (130–280) / [0, 685] | **All logged P** | player-week | yards | punts | `base=2` → hold **8** | `pt_yards` | 1999 | KDE | Low | `player_id` |
| Net Punt Yds | Continuous | Normal | NIG | (110–250) | **All logged P** | player-week | yards | punts | `base=2` → hold **8** | `pt_net_yards` | 1999 | KDE | Low | `player_id` |
| Inside 20 | Discrete | Binomial \| punts | Beta | (1–3) / [0, 8] | **All logged P** | player-week | count | punts | `base=2` → hold **8** | `pt_inside_20` | 1999 | Hist | Med | `player_id` |
| TB / Fair Catch | Discrete | Binomial | Beta | (0–2) | **All logged P** | player-week | count | punts | `base=2` → hold **8** | `pt_touchback`, `pt_fair_caught` | 1999 | Hist | **High** | `player_id` |
| Kick/Punt Returns | Discrete | ZI-Poisson | Gamma | (1–4) / [0, 11] | **All logged returners** | player-week | count | — | `base=1 ret` → hold **4** | `kickoff_returns`, `punt_returns` | 1999 | Hist | Med | `player_id` |
| Return Yards | Continuous | Hurdle + Log-Normal | NIG (log) | (20–75) / [−10, 305] | **All logged** | player-week | yards | returns | `base=1 ret` → hold **4** | `*_return_yards` | 1999 | KDE | Med | `player_id` |
| Return TDs | Discrete | ZI-Poisson | Gamma | (0–0) / [0, 2] | **All logged** | player-week | count | returns | `base=1 ret` → hold **4** | `pt_return_tds`, `special_teams_tds` | 1999 | Hist | **High** | `player_id` |

---

### Ramp–hold defaults (development cheat sheet)

Use w = NFL week number:

| Role of \(n_{\text{base}}\) | Suggested \(n_{\text{base}}\) | Hold at week 5+ |
| --- | --- | --- |
| Passer *rate* (Cmp%, rating, CPOE) | 10 attempts / player-week | **40 attempts** |
| Passer *volume* (attempts, EPA) | 8 attempts | **32** |
| RB *rate* (YPC, YAC, broken tackles) | 5 carries | **20** |
| WR/TE *rate* (catch %, aDOT, WOPR) | 3 targets | **12** |
| Coverage *rate* (cmp% / rating allowed) | 4 targets allowed | **16** |
| Coverage *volume* | 2 targets allowed | **8** |
| Kicker FG% | 1 FGA (or 2 if you want less noise) | **4** (or **8**) |
| Punter rates | 2 punts | **8** |
| NGS averages (already volume-gated) | 1 NGS row | **4** NGS rows YTD |
| Rare counts (TD, INT, sack, drop, FF) | 1 REG game-row | **4** game-rows YTD |

**Zero mass = High** → histogram with an explicit 0 bin; do not KDE those. **NGS / PFR missing** → gray, do not impute 0 (that would look like a real zero INT/drop).