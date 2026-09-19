"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { FantasyPosRankKind } from "@/lib/payload";

const FINISH_AMONG: Record<string, string> = {
  QB: "QBs",
  WR: "WRs",
  RB: "RBs",
  TE: "TEs",
};

export function fantasyRankTooltipCopy(
  kind: FantasyPosRankKind,
  position: string,
): string {
  if (kind === "consensus") return "Rank according to fantasy consensus";
  const among = FINISH_AMONG[position] ?? `${position}s`;
  return `PPR finish among ${among} that season`;
}

type PositionRankLabelProps = {
  position: string;
  rank?: number;
  kind?: FantasyPosRankKind;
};

export function PositionRankLabel({
  position,
  rank,
  kind,
}: PositionRankLabelProps) {
  const [pinned, setPinned] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const rootRef = useRef<HTMLSpanElement>(null);
  const tooltipId = useId();
  const open = pinned || hovered || focused;

  const hasRank =
    rank != null && Number.isFinite(rank) && rank >= 1 && kind != null;
  const copy = hasRank ? fantasyRankTooltipCopy(kind, position) : "";

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: PointerEvent) {
      if (rootRef.current?.contains(event.target as Node)) return;
      setPinned(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  if (!hasRank) {
    return <span>{position}</span>;
  }

  return (
    <span ref={rootRef} className="relative inline-flex items-baseline">
      <span>{position}</span>
      <button
        type="button"
        aria-label={`${position} ${rank}. ${copy}`}
        aria-expanded={open}
        aria-describedby={open ? tooltipId : undefined}
        onPointerDown={(event) => {
          event.stopPropagation();
        }}
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          setPinned((current) => {
            const next = !current;
            if (!next) {
              setFocused(false);
              event.currentTarget.blur();
            }
            return next;
          });
        }}
        onKeyDown={(event) => {
          if (
            event.key === "Enter" ||
            event.key === " " ||
            event.key === "Escape"
          ) {
            event.stopPropagation();
          }
          if (event.key === "Escape") {
            setPinned(false);
            setFocused(false);
          }
        }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onFocus={() => setFocused(true)}
        onBlur={() => {
          setFocused(false);
          setPinned(false);
        }}
        className="relative ml-px inline-flex cursor-pointer border-0 bg-transparent p-0 align-baseline text-zinc-500 outline-none hover:text-zinc-700 focus-visible:text-zinc-800"
      >
        <sub className="tabular-nums">{rank}</sub>
        {open ? (
          <span
            id={tooltipId}
            role="tooltip"
            className="absolute top-full left-0 z-50 mt-1 w-max max-w-[12.5rem] rounded-none border border-zinc-200 bg-white px-2 py-1.5 text-left text-xs font-normal normal-case leading-4 tracking-normal text-zinc-600 shadow-none"
            onClick={(event) => event.stopPropagation()}
          >
            {copy}
          </span>
        ) : null}
      </button>
    </span>
  );
}
