import { Suspense } from "react";
import { RuntimePlayerPage } from "@/components/player/RuntimePlayerPage";

export default function PlayersPage() {
  return <Suspense fallback={<main className="p-4">Loading player…</main>}><RuntimePlayerPage /></Suspense>;
}
