"use client";

import { useState } from "react";
import Link from "next/link";
import { StatStack, type StatStackLayout } from "@/components/stat-row/variants";
import type { PlayerBio } from "@/lib/payload";
import type { StatPayload } from "@/lib/distribution";

const PLAYER_ID = "demo-qb";

const VARIATIONS: {
  id: string;
  layout: StatStackLayout;
  title: string;
  note: string;
}[] = [
  {
    id: "original",
    layout: "cards",
    title: "Original · individual cards",
    note: "Each slider is its own square bordered panel.",
  },
  {
    id: "flush",
    layout: "flush",
    title: "A · Flush on the page",
    note: "No card chrome. Rows sit on the page background with hairline dividers. Section labels stay. Use the density sliders above.",
  },
  {
    id: "section-card",
    layout: "section-card",
    title: "B · One card per section",
    note: "Efficiency, Production, Volume, etc. each get a single square container. Rows inside are divided, not individually boxed.",
  },
  {
    id: "ruled",
    layout: "ruled",
    title: "C · Ruled list",
    note: "No fills or shadows. A bottom rule under each row, last rule omitted.",
  },
  {
    id: "sheet",
    layout: "sheet",
    title: "D · Single sheet",
    note: "The whole stack is one square panel. Section labels live inside it.",
  },
];

function DensityField({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="flex min-w-[11rem] flex-1 flex-col gap-1">
      <span className="flex justify-between text-[11px] font-medium text-zinc-600">
        <span>{label}</span>
        <span className="tabular-nums text-zinc-900">{value}px</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={1}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="h-1.5 w-full cursor-pointer appearance-none rounded-none bg-zinc-200 accent-zinc-900"
      />
    </label>
  );
}

export function QbLabClient({
  player,
  groupLabel,
  stats,
}: {
  player: PlayerBio;
  groupLabel: string;
  stats: StatPayload[];
}) {
  const [rowPaddingY, setRowPaddingY] = useState(6);
  const [sectionGap, setSectionGap] = useState(12);
  const [headingGap, setHeadingGap] = useState(4);

  const density = {
    sliderPlacement: "inline" as const,
    rowPaddingY,
    sectionGap,
    headingGap,
  };

  return (
    <div>
      <div className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-3xl flex-col gap-3 px-4 py-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold tracking-[0.2em] text-zinc-500 uppercase">
              Layout lab · {groupLabel}
            </p>
            <h1 className="mt-0.5 text-3xl font-semibold tracking-tight">
              {player.name}
            </h1>
            <p className="mt-1 max-w-xl text-sm leading-5 text-zinc-600">
              Same QB catalog as the player page. Every variation here puts the
              slider beside the stat name. Density sliders apply to all blocks
              below. The live profile is unchanged.
            </p>
            <p className="mt-2 text-sm text-zinc-500">
              <Link
                href={`/players/${PLAYER_ID}`}
                className="font-medium text-zinc-900 underline"
              >
                Back to the live QB page
              </Link>
            </p>
          </div>
          <div className="rounded-none border border-zinc-200 bg-zinc-50 px-3 py-2">
            <p className="text-lg font-semibold">{player.name}</p>
            <p className="text-sm text-zinc-500">
              {player.position} · {player.team} · 2025
            </p>
            <p className="mt-1 text-xs text-zinc-400">Layout experiments only</p>
          </div>
        </div>
      </div>

      <div className="sticky top-0 z-20 border-b border-zinc-200 bg-zinc-100/95 backdrop-blur">
        <div className="mx-auto max-w-3xl space-y-2 px-4 py-2">
          <div className="flex gap-2 overflow-x-auto text-xs">
            {VARIATIONS.map((variation) => (
              <a
                key={variation.id}
                href={`#${variation.id}`}
                className="shrink-0 rounded-none border border-zinc-200 bg-white px-2 py-1 font-medium text-zinc-600 hover:border-zinc-300 hover:text-zinc-900"
              >
                {variation.title.split(" · ")[0]}
              </a>
            ))}
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <DensityField
              label="Row padding"
              value={rowPaddingY}
              min={0}
              max={16}
              onChange={setRowPaddingY}
            />
            <DensityField
              label="Section gap"
              value={sectionGap}
              min={0}
              max={32}
              onChange={setSectionGap}
            />
            <DensityField
              label="Heading gap"
              value={headingGap}
              min={0}
              max={20}
              onChange={setHeadingGap}
            />
          </div>
        </div>
      </div>

      <main className="mx-auto max-w-3xl space-y-10 px-4 py-6">
        {VARIATIONS.map((variation) => (
          <div key={variation.id} id={variation.id} className="scroll-mt-36">
            <div className="mb-4">
              <p className="text-xs font-semibold tracking-[0.2em] text-zinc-500 uppercase">
                Variation
              </p>
              <h2 className="mt-1 text-xl font-semibold tracking-tight">
                {variation.title}
              </h2>
              <p className="mt-1 max-w-xl text-sm leading-6 text-zinc-600">
                {variation.note}
              </p>
            </div>
            <StatStack
              stats={stats}
              layout={variation.layout}
              {...density}
            />
          </div>
        ))}
      </main>
    </div>
  );
}
