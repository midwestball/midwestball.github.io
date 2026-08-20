# Routing

| Route | Role |
|---|---|
| `/` | Weekly highlights placeholder. |
| `/search` | Client filter over the player index. Default context is current season. |
| `/players/[id]?season=` | Position catalog stack + season `<select>` at the bottom. Changing season reloads the same page. |
| `/ballnet` | Public stub. Not the ML app. |

Player pages hydrate `statsForPosition(player.position)` with an empty snapshot list until Ballnet JSON exists. Do not add last-10 / all-time windows unless a human asks.

`web/src/data/players.ts` is a routing fixture list (id, name, position, team, seasons) — not league samples.
