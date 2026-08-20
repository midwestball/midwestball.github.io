import { BACKFIELD_STATS } from "./backfield";
import { DEF_FRONT_STATS } from "./def-front";
import { OL_STATS } from "./ol";
import { PASS_CATCHER_STATS } from "./pass-catcher";
import { positionGroupOf } from "./positions";
import { QB_STATS } from "./qb";
import { SECONDARY_STATS } from "./secondary";
import { KICKER_STATS, PUNTER_STATS, RETURNER_STATS } from "./special-teams";
import type { PositionGroup, StatDefinition } from "./types";

export const STATS_BY_GROUP: Record<PositionGroup, StatDefinition[]> = {
  qb: QB_STATS,
  backfield: BACKFIELD_STATS,
  pass_catcher: PASS_CATCHER_STATS,
  ol: OL_STATS,
  def_front: DEF_FRONT_STATS,
  secondary: SECONDARY_STATS,
  kicker: KICKER_STATS,
  punter: PUNTER_STATS,
  returner: RETURNER_STATS,
};

export function statsForPosition(position: string): StatDefinition[] {
  return STATS_BY_GROUP[positionGroupOf(position)];
}

export {
  GROUP_LABEL,
  POSITION_TO_GROUP,
  isPositionCode,
  positionGroupOf,
} from "./positions";
export { formatStatValue } from "./format";
export type {
  PositionCode,
  PositionGroup,
  StatDefinition,
  ValueFormat,
  ZeroMass,
} from "./types";
