import { GROUP_LABEL, positionGroupOf } from "@/lib/catalog";
import { hydratePlayerStats } from "@/lib/catalog/hydrate";
import { getPlayer } from "@/data/players";
import { QbLabClient } from "./QbLabClient";

const PLAYER_ID = "demo-qb";

export default function QbLayoutLabPage() {
  const player = getPlayer(PLAYER_ID);
  if (!player) return null;

  const stats = hydratePlayerStats(player.position, []);
  const groupLabel = GROUP_LABEL[positionGroupOf(player.position)];

  return (
    <QbLabClient player={player} groupLabel={groupLabel} stats={stats} />
  );
}
