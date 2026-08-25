import type { PlayerBio } from "@/lib/payload";

/** Lab-only placeholders (layout experiments). Not part of Ballnet publish. */
export const DEMO_PLAYERS: PlayerBio[] = [
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

export function searchPlayers(
  players: PlayerBio[],
  query: string,
): PlayerBio[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return players;
  return players.filter((player) => {
    return (
      player.name.toLowerCase().includes(needle) ||
      player.position.toLowerCase().includes(needle) ||
      player.team.toLowerCase().includes(needle)
    );
  });
}
