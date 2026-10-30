"use client";
import Link from "next/link";
import { playerComparisonHref } from "@/lib/player-navigation";

export function PlayerComparisonLink({ playerId, season, children, className = "hover:underline" }: {
  playerId: string; season?: number; children: React.ReactNode; className?: string;
}) {
  return <Link href={playerComparisonHref(playerId, season)} className={className}
    onClick={event => event.stopPropagation()} onKeyDown={event => event.stopPropagation()}>{children}</Link>;
}
