import type { PlayerBio } from "@/lib/payload";

/** Routing fixtures only — no values, curves, or percentiles. */
export const PLAYER_INDEX: PlayerBio[] = [
  {
    id: "demo-qb",
    name: "Demo Quarterback",
    position: "QB",
    team: "KNB",
    seasons: [2023, 2024, 2025],
  },
  {
    id: "demo-rb",
    name: "Demo Running Back",
    position: "RB",
    team: "KNB",
    seasons: [2023, 2024, 2025],
  },
  {
    id: "demo-fb",
    name: "Demo Fullback",
    position: "FB",
    team: "KNB",
    seasons: [2024, 2025],
  },
  {
    id: "demo-wr",
    name: "Demo Wide Receiver",
    position: "WR",
    team: "KNB",
    seasons: [2023, 2024, 2025],
  },
  {
    id: "demo-te",
    name: "Demo Tight End",
    position: "TE",
    team: "KNB",
    seasons: [2023, 2024, 2025],
  },
  {
    id: "demo-ot",
    name: "Demo Tackle",
    position: "T",
    team: "KNB",
    seasons: [2023, 2024, 2025],
  },
  {
    id: "demo-edge",
    name: "Demo Edge",
    position: "ED",
    team: "KNB",
    seasons: [2023, 2024, 2025],
  },
  {
    id: "demo-cb",
    name: "Demo Cornerback",
    position: "CB",
    team: "KNB",
    seasons: [2023, 2024, 2025],
  },
  {
    id: "demo-k",
    name: "Demo Kicker",
    position: "K",
    team: "KNB",
    seasons: [2023, 2024, 2025],
  },
  {
    id: "demo-p",
    name: "Demo Punter",
    position: "P",
    team: "KNB",
    seasons: [2023, 2024, 2025],
  },
  {
    id: "demo-kr",
    name: "Demo Returner",
    position: "KR",
    team: "KNB",
    seasons: [2024, 2025],
  },
];

export const CURRENT_SEASON = 2025;

export function getPlayer(id: string): PlayerBio | undefined {
  return PLAYER_INDEX.find((player) => player.id === id);
}

export function searchPlayers(query: string): PlayerBio[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return PLAYER_INDEX;
  return PLAYER_INDEX.filter((player) => {
    return (
      player.name.toLowerCase().includes(needle) ||
      player.position.toLowerCase().includes(needle) ||
      player.team.toLowerCase().includes(needle)
    );
  });
}
