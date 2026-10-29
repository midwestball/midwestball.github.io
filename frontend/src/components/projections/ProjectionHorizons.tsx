"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { ProjectionsPageClient } from "./ProjectionsPageClient";
import { RosProjections } from "./RosProjections";

export function ProjectionHorizons() {
  const search = useSearchParams();
  const router = useRouter();
  const ros = search.get("horizon") === "ros";
  function choose(next: boolean) {
    const url = new URL(window.location.href);
    if (next) url.searchParams.set("horizon", "ros"); else url.searchParams.delete("horizon");
    router.push(`${url.pathname}${url.search}`, { scroll: false });
  }
  return <><div className="border-b border-zinc-200 bg-white"><div className="mx-auto flex max-w-5xl gap-1 px-4 py-2" role="group" aria-label="Projection horizon">
    {[false, true].map(value => <button key={String(value)} aria-pressed={ros === value} onClick={() => choose(value)} className={`border px-3 py-2 text-sm font-semibold ${ros === value ? "border-zinc-900 bg-zinc-900 text-white" : "border-zinc-300 text-zinc-600 hover:bg-zinc-100"}`}>{value ? "Rest of season" : "Upcoming week"}</button>)}
  </div></div>{ros ? <RosProjections /> : <ProjectionsPageClient />}</>;
}
