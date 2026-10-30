import { Suspense } from "react";
import { LegacyPlayerRedirect } from "@/components/player/LegacyPlayerRedirect";

export default function PlayersPage() {
  return <Suspense fallback={<main className="p-4">Opening comparison…</main>}><LegacyPlayerRedirect /></Suspense>;
}
