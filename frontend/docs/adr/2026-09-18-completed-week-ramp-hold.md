### Context
Mid-week YTD publishes (Thursday of week N) must include those boxes, but multiplying ramp–hold by `asOfWeek` immediately greys out everyone who has only played the prior week.

### Decision
Ballnet keeps `asOfWeek` as the latest REG week in the YTD slice and computes `completedWeek` as the last consecutive REG week where every scheduled game has scores (floored at 1, capped at `asOfWeek`). Qualification is `min_n = n_base × min(completedWeek, 5)`. Pages, league, leaderboards, and `index/{current,seasons}.json` publish `completedWeek`; Knowball search uses that field for the min-volume floor and never inspects the NFL schedule.

### Consequences
- **Required:** Recompute `completedWeek` from `data/raw/schedules_{season}.parquet` at Stage C. Do not bump it because a single game in week N is final.
- **Required:** Knowball must not invent `completedWeek`. Missing field on legacy JSON equals `asOfWeek`.
- **Deprecated:** Using `asOfWeek` as the ramp–hold multiplier, and treating “latest kickoff in the past” as a completed week.
