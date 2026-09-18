### Context
Knowball needs a season-scoped fantasy position rank on the position label, but the Next app must not compute Expert Consensus Rank or PPR standings — those belong in Ballnet’s published JSON.

### Decision
Ballnet `fantasy_rank.py` attaches optional `fantasyPosRank` and `fantasyPosRankKind` (`"consensus"` | `"finish"`) on player pages, search leaderboards, and highlight rows for QB/WR/RB/TE only. Live season uses FantasyPros weekly ECR via `nfl.load_ff_rankings("week")`; closed seasons use REG PPR finish (competition rank). Knowball renders `PositionRankLabel` with locked tooltip copy and never invents a missing rank.

### Consequences
- **Required:** Omit the fields for FB/OL/defense/K/P and for null GSIS / zero-PPR players. Do not put ranks on `index/players.json`. Do not overload highlight `rank` (z-score board order).
- **Required:** Tooltip copy is kind-specific: consensus → `Rank according to fantasy consensus`; finish → `PPR finish among {QBs|WRs|RBs|TEs} that season`.
- **Required:** After `index/current.json` advances to `Y+1`, republish year `Y` at its final REG week so last year’s pages switch from consensus to finish.
- **Deprecated:** Computing fantasy ranks in the Next app, or showing dynasty / overall / superflex ECR as this subscript.
