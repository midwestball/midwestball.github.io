"use client";
import { useEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { legacyPlayerComparisonHref } from "@/lib/player-navigation";

export function LegacyPlayerRedirect({ playerId }: { playerId?: string }) {
  const router = useRouter();
  const params = useSearchParams();
  const target = legacyPlayerComparisonHref(new URLSearchParams(params.toString()), playerId);
  useEffect(() => { router.replace(`${target}${window.location.hash}`, { scroll: false }); }, [router, target]);
  return <main className="p-4 text-sm text-muted-foreground">Opening comparison… <Link href={target} className="underline">Open comparison</Link></main>;
}
