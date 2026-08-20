import type { PositionCode, PositionGroup } from "./types";

export const POSITION_TO_GROUP: Record<PositionCode, PositionGroup> = {
  QB: "qb",
  RB: "backfield",
  FB: "backfield",
  WR: "pass_catcher",
  TE: "pass_catcher",
  T: "ol",
  OT: "ol",
  G: "ol",
  OG: "ol",
  C: "ol",
  ED: "def_front",
  EDGE: "def_front",
  DE: "def_front",
  DT: "def_front",
  NT: "def_front",
  LB: "def_front",
  ILB: "def_front",
  OLB: "def_front",
  CB: "secondary",
  FS: "secondary",
  SS: "secondary",
  S: "secondary",
  K: "kicker",
  P: "punter",
  KR: "returner",
  PR: "returner",
};

export const GROUP_LABEL: Record<PositionGroup, string> = {
  qb: "Quarterback",
  backfield: "Backfield",
  pass_catcher: "Pass catcher",
  ol: "Offensive line",
  def_front: "Defensive front",
  secondary: "Secondary",
  kicker: "Kicker",
  punter: "Punter",
  returner: "Returner",
};

export function isPositionCode(value: string): value is PositionCode {
  return value in POSITION_TO_GROUP;
}

export function positionGroupOf(position: string): PositionGroup {
  if (!isPositionCode(position)) {
    throw new Error(`Unknown position code: ${position}`);
  }
  return POSITION_TO_GROUP[position];
}
