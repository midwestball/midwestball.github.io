"use client";

import { useState } from "react";
import { formatStatValue } from "@/lib/catalog/format";
import type { ValueFormat } from "@/lib/catalog/types";

type Bin = { lower: number; upper: number; count: number };
type Marker = { name: string; value: number; color: string };

/** Observed counts; bars never interpolate within a bin. */
export function HistogramChart({ label, bins, format, markers = [], interactive = false, shadeColor = "#71717a" }: {
  label: string; bins: Bin[]; format: ValueFormat; markers?: Marker[];
  interactive?: boolean; shadeColor?: string;
}) {
  const [activeBin, setActiveBin] = useState<number | null>(null);
  const [activeMarker, setActiveMarker] = useState<number | null>(null);
  if (!bins.length) return null;
  const left = bins[0].lower, right = bins[bins.length - 1].upper;
  const width = right - left, max = Math.max(1, ...bins.map(b => b.count));
  const x = (v: number) => 36 + 548 * (v - left) / width;
  const cumulative: number[] = [];
  for (const bin of bins) cumulative.push((cumulative.at(-1) ?? 0) + bin.count);
  const total = cumulative.at(-1) ?? 0;
  const selected = activeBin != null && activeBin < bins.length ? activeBin : null;
  const marker = activeMarker != null ? markers[activeMarker] : null;
  const pct = (count: number) => total > 0 ? `${(count * 100 / total).toFixed(1)}%` : "—";
  const range = (bin: Bin, i: number) => `${formatStatValue(format, bin.lower)} ≤ value ${i === bins.length - 1 ? "≤" : "<"} ${formatStatValue(format, bin.upper)}`;
  const friendlyRange = (bin: Bin, i: number) => `${formatStatValue(format, bin.lower)} to ${i === bins.length - 1 ? "" : "under "}${formatStatValue(format, bin.upper)}`;
  const silver = shadeColor === "rgb(168, 169, 173)";

  return <figure className="w-full" aria-label={`${label} observed distribution`}>
    {interactive && <div className="min-h-12 text-xs leading-4 text-zinc-600" role="status" aria-live="polite">
      {marker ? <>
        <p className="font-medium text-zinc-800">{marker.name}: {formatStatValue(format, marker.value)} {label}</p>
        <p>The line marks this player’s result.</p>
      </> : selected == null ? "Hover over a bar or the player’s line for details." : <>
        <p className="font-medium text-zinc-800">{friendlyRange(bins[selected], selected)} · {bins[selected].count.toLocaleString("en-US")} {bins[selected].count === 1 ? "performance" : "performances"}</p>
        <p><strong>{pct(bins[selected].count)}</strong> of performances in this range · <strong>{pct(cumulative[selected])}</strong> {selected === bins.length - 1 ? "at or below" : "below"} {formatStatValue(format, bins[selected].upper)}</p>
      </>}
    </div>}
    <svg viewBox="0 0 600 220" role={interactive ? "group" : "img"} aria-label={`Histogram of ${label}; vertical axis is the number of observations`} className="w-full" onMouseLeave={() => { setActiveBin(null); setActiveMarker(null); }}>
      <line x1="36" x2="584" y1="190" y2="190" stroke="#71717a" />
      {bins.map((bin, i) => <g key={i}>
        <rect x={x(bin.lower)} y={190 - 160 * bin.count / max} width={Math.max(0, x(bin.upper) - x(bin.lower) - 1)} height={160 * bin.count / max} fill={interactive && selected != null && i <= selected ? (silver && selected === i ? "#626367" : shadeColor) : "#a1a1aa"} fillOpacity={interactive ? (selected != null && i <= selected && silver ? 1 : selected === i ? 0.95 : 0.55) : 1} pointerEvents="none" />
        {interactive ? <rect x={x(bin.lower)} y="20" width={Math.max(0, x(bin.upper) - x(bin.lower))} height="170" fill="transparent" tabIndex={0} role="button" aria-label={`${range(bin, i)}: ${bin.count} performances, ${pct(bin.count)} in this range, ${pct(cumulative[i])} in this range or below`} onMouseEnter={() => { setActiveMarker(null); setActiveBin(i); }} onFocus={() => { setActiveMarker(null); setActiveBin(i); }} onBlur={() => setActiveBin(null)} onClick={() => { setActiveMarker(null); setActiveBin(i); }} /> : <title>{`${range(bin, i)}: ${bin.count} observations`}</title>}
      </g>)}
      {markers.map((m, i) => m.value >= left && m.value <= right ? <g key={`${m.name}-${i}`}>
        <line x1={x(m.value)} x2={x(m.value)} y1="20" y2="190" stroke={m.color} strokeWidth="2" strokeDasharray="4 3" pointerEvents="none" />
        {interactive ? <rect x={Math.max(36, x(m.value) - 7)} y="20" width={Math.min(584, x(m.value) + 7) - Math.max(36, x(m.value) - 7)} height="170" fill="transparent" tabIndex={0} role="button" aria-label={`${m.name}: ${formatStatValue(format, m.value)} ${label}; player result line`} onMouseEnter={() => { setActiveBin(null); setActiveMarker(i); }} onFocus={() => { setActiveBin(null); setActiveMarker(i); }} onBlur={() => setActiveMarker(null)} onClick={() => { setActiveBin(null); setActiveMarker(i); }} /> : <title>{`${m.name}: ${formatStatValue(format, m.value)}`}</title>}
      </g> : null)}
      <text x="36" y="211" fontSize="11" fill="#52525b">{formatStatValue(format, left)}</text>
      <text x="584" y="211" fontSize="11" fill="#52525b" textAnchor="end">{formatStatValue(format, right)}</text>
      <text x="30" y="32" fontSize="11" fill="#52525b" textAnchor="end">{max}</text>
    </svg>
    {markers.length > 0 && <p className="text-xs text-zinc-600">{markers.map(m => `${m.name}: ${formatStatValue(format, m.value)}`).join(" · ")}</p>}
    <details className="text-xs text-zinc-600"><summary className="cursor-pointer">Show histogram counts</summary>
      <p>Ranges include the lower edge and exclude the upper edge, except the final range includes both.{interactive && " Percentages are shares of qualifying player performances."}</p>
      <table className="mt-1 w-full text-left"><caption className="sr-only">{label} histogram bins</caption><thead><tr><th>Range</th><th>Observations</th>{interactive && <><th>In bar</th><th>Bar or less</th></>}</tr></thead><tbody>{bins.map((bin, i) => <tr key={i}><td>{range(bin, i)}</td><td>{bin.count}</td>{interactive && <><td>{pct(bin.count)}</td><td>{pct(cumulative[i])}</td></>}</tr>)}</tbody></table>
    </details>
  </figure>;
}
