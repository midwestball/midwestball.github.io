"use client";

import { useId, useMemo, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatStatValue } from "@/lib/catalog/format";
import {
  CHART_PLOT,
  insertValuePoint,
  percentileColor,
  percentileContrastText,
  type Point,
  type StatPayload,
} from "@/lib/distribution";
import { isStatReady } from "@/lib/stat-status";
import { cn } from "@/lib/utils";

const LABEL_STEP = 24;
const RIGHT_MARGIN = 108;

export type OverlayMarker = {
  playerId: string;
  name: string;
  color: string;
  stat: StatPayload;
};

/** "Josh Allen" → "J. Allen" */
export function shortPlayerName(full: string): string {
  const parts = full.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return full;
  if (parts.length === 1) return parts[0]!;
  const first = parts[0]![0]?.toUpperCase() ?? "";
  const last = parts[parts.length - 1]!;
  return `${first}. ${last}`;
}

type CurveRow = {
  x: number;
  league: number;
  shaded: number | null;
};

type Crosshair = {
  x: number;
  y: number;
};

function tickDensity(value: number): string {
  return value >= 10 ? value.toFixed(0) : value.toFixed(1);
}

function XAxisValueLabel({
  viewBox,
  value,
}: {
  viewBox?: { x?: number; y?: number; width?: number; height?: number };
  value: string;
}) {
  if (viewBox?.x == null || viewBox?.y == null || viewBox.height == null) {
    return null;
  }
  return (
    <text
      x={viewBox.x}
      y={viewBox.y + viewBox.height + 14}
      textAnchor="middle"
      fill="#52525b"
      fontSize={11}
      fontWeight={600}
    >
      {value}
    </text>
  );
}

function YAxisValueLabel({
  viewBox,
  value,
}: {
  viewBox?: { x?: number; y?: number; width?: number; height?: number };
  value: string;
}) {
  if (viewBox?.x == null || viewBox?.y == null) return null;
  return (
    <text
      x={(viewBox.x ?? 0) - 6}
      y={viewBox.y + 4}
      textAnchor="end"
      fill="#52525b"
      fontSize={11}
      fontWeight={600}
    >
      {value}
    </text>
  );
}

type MarkerLabelProps = {
  viewBox?: { x?: number; y?: number; width?: number; height?: number };
  shortName: string;
  color: string;
  stackIndex: number;
  active: boolean;
  onHover: (active: boolean) => void;
  onToggle: () => void;
};

function MarkerLabel({
  viewBox,
  shortName,
  color,
  stackIndex,
  active,
  onHover,
  onToggle,
}: MarkerLabelProps) {
  if (viewBox?.x == null || viewBox?.y == null) return null;
  const x = viewBox.x + 8;
  const y = viewBox.y + 14 + stackIndex * LABEL_STEP;
  // Invisible hit pad — text stays tight; hover/click target is easier to catch.
  const hitPadX = 10;
  const hitPadY = 10;
  const textW = Math.min(100, shortName.length * 7 + 8);
  const hitW = textW + hitPadX * 2;
  const hitH = 14 + hitPadY * 2;

  return (
    <g
      role="button"
      tabIndex={0}
      aria-pressed={active}
      aria-label={shortName}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
      onClick={(event) => {
        event.stopPropagation();
        onToggle();
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onToggle();
        }
      }}
      style={{ cursor: "pointer" }}
    >
      <rect
        x={x - hitPadX}
        y={y - 11 - hitPadY}
        width={hitW}
        height={hitH}
        fill="transparent"
        pointerEvents="all"
      />
      <rect
        x={x - 2}
        y={y - 11}
        width={textW}
        height={14}
        fill={active ? "rgba(255,255,255,0.92)" : "rgba(255,255,255,0.55)"}
        stroke={active ? color : "transparent"}
        strokeWidth={1}
        pointerEvents="none"
      />
      <text
        x={x}
        y={y}
        fill={color}
        fontSize={11}
        fontWeight={active ? 700 : 600}
        style={{ userSelect: "none" }}
        pointerEvents="none"
      >
        {shortName}
      </text>
    </g>
  );
}

export function CompareOverlayChart({
  markers,
  fills,
}: {
  markers: OverlayMarker[];
  fills: Map<string, string>;
}) {
  const reactId = useId().replace(/:/g, "");
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [pinnedId, setPinnedId] = useState<string | null>(null);
  const [crosshair, setCrosshair] = useState<Crosshair | null>(null);
  const focusId = hoveredId ?? pinnedId;

  const readyMarkers = useMemo(() => {
    return markers
      .filter(
        (m) =>
          isStatReady(m.stat) &&
          m.stat.playerValue != null &&
          m.stat.percentile != null &&
          m.stat.curve.length > 0,
      )
      .map((m) => ({
        ...m,
        color: fills.get(m.playerId) ?? m.color,
        shortName: shortPlayerName(m.name),
        value: m.stat.playerValue as number,
        percentile: m.stat.percentile as number,
      }))
      .sort((a, b) => {
        if (b.percentile !== a.percentile) return b.percentile - a.percentile;
        return a.playerId.localeCompare(b.playerId);
      });
  }, [markers, fills]);

  const template = readyMarkers[0]?.stat;
  const focusMarker =
    readyMarkers.find((m) => m.playerId === focusId) ?? null;

  const curveData: CurveRow[] = useMemo(() => {
    if (!template) return [];
    let curve: Point[] = template.curve;
    if (focusMarker) {
      curve = insertValuePoint(curve, focusMarker.value);
    }
    const shadeRight = !template.higherIsBetter;
    const cut = focusMarker?.value;
    return curve.map((point) => ({
      x: Number(point.x.toFixed(4)),
      league: point.y,
      shaded:
        cut == null
          ? null
          : shadeRight
            ? point.x >= cut - 1e-9
              ? point.y
              : null
            : point.x <= cut + 1e-9
              ? point.y
              : null,
    }));
  }, [template, focusMarker]);

  if (!template || readyMarkers.length === 0) {
    return (
      <div className="rounded-none border border-zinc-200 bg-zinc-50 px-3 py-6 text-center text-sm text-zinc-500">
        No ready distributions for this row yet.
      </div>
    );
  }

  const shadeId = `compare-shade-${reactId}`;
  const focusColor = focusMarker?.color ?? "#a1a1aa";
  const badgeColor =
    focusMarker != null ? percentileColor(focusMarker.percentile) : undefined;
  const badgeText =
    focusMarker != null
      ? percentileContrastText(focusMarker.percentile)
      : undefined;
  const standingNote = template.higherIsBetter ? "or lower" : "or higher";

  return (
    <div className="space-y-2">
      <p className="text-[11px] leading-4 text-zinc-400">
        {focusMarker ? (
          <>
            <span className="font-semibold text-zinc-600">
              {focusMarker.shortName}
            </span>
            {" · "}
            <span
              className="rounded-none px-1 py-0.5 font-semibold tabular-nums"
              style={{ backgroundColor: badgeColor, color: badgeText }}
            >
              {Math.round(focusMarker.percentile)}%
            </span>
            {` of the league has a ${template.label} of ${formatStatValue(template.format, focusMarker.value)} ${standingNote}.`}
          </>
        ) : (
          "Hover or click a name to shade that player’s standing on the league curve."
        )}
      </p>

      <div style={{ height: CHART_PLOT.height }} className="w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={curveData}
            margin={{
              top: CHART_PLOT.top,
              right: RIGHT_MARGIN,
              left: 0,
              bottom: 0,
            }}
            onMouseMove={(state) => {
              if (focusId) {
                setCrosshair(null);
                return;
              }
              const payload = (
                state as { activePayload?: Array<{ payload?: CurveRow }> }
              ).activePayload;
              const row = payload?.[0]?.payload;
              if (row == null || row.league == null) {
                setCrosshair(null);
                return;
              }
              setCrosshair({ x: row.x, y: row.league });
            }}
            onMouseLeave={() => setCrosshair(null)}
          >
            <defs>
              <linearGradient id={shadeId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={focusColor} stopOpacity={0.35} />
                <stop offset="100%" stopColor={focusColor} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke="#e4e4e7" />
            <XAxis
              dataKey="x"
              type="number"
              domain={[template.xMin, template.xMax]}
              tickLine={false}
              axisLine={false}
              tick={{ fill: "#71717a", fontSize: 11 }}
              tickFormatter={(value: number) =>
                formatStatValue(template.format, value)
              }
              minTickGap={24}
              padding={{ left: 0, right: 0 }}
            />
            <YAxis
              width={CHART_PLOT.left}
              domain={[0, template.yMax]}
              tickLine={false}
              axisLine={false}
              tick={{ fill: "#71717a", fontSize: 11 }}
              tickFormatter={tickDensity}
            />
            {/* Keeps activePayload tracking without rendering the old standing/density box. */}
            <Tooltip content={() => null} cursor={false} isAnimationActive={false} />
            <Area
              type="linear"
              dataKey="league"
              stroke="#a1a1aa"
              strokeWidth={1.5}
              fill="rgba(244, 244, 245, 0.9)"
              fillOpacity={1}
              isAnimationActive
              animationDuration={450}
            />
            {focusMarker ? (
              <Area
                type="linear"
                dataKey="shaded"
                stroke={focusColor}
                strokeWidth={2}
                fill={`url(#${shadeId})`}
                connectNulls={false}
                isAnimationActive
                animationDuration={300}
              />
            ) : null}
            {crosshair != null && focusId == null ? (
              <>
                <ReferenceLine
                  x={crosshair.x}
                  stroke="#a1a1aa"
                  strokeDasharray="3 3"
                  strokeWidth={1}
                  label={(props) => (
                    <XAxisValueLabel
                      {...props}
                      value={formatStatValue(template.format, crosshair.x)}
                    />
                  )}
                />
                <ReferenceLine
                  y={crosshair.y}
                  stroke="#a1a1aa"
                  strokeDasharray="3 3"
                  strokeWidth={1}
                  label={(props) => (
                    <YAxisValueLabel
                      {...props}
                      value={tickDensity(crosshair.y)}
                    />
                  )}
                />
              </>
            ) : null}
            {readyMarkers.map((marker, stackIndex) => {
              const active = focusId === marker.playerId;
              return (
                <ReferenceLine
                  key={marker.playerId}
                  x={marker.value}
                  stroke={marker.color}
                  strokeDasharray={active ? undefined : "4 4"}
                  strokeWidth={active ? 2 : 1.5}
                  opacity={focusId && !active ? 0.35 : 1}
                  label={(props) => (
                    <MarkerLabel
                      {...props}
                      shortName={marker.shortName}
                      color={marker.color}
                      stackIndex={stackIndex}
                      active={active}
                      onHover={(on) => {
                        setHoveredId(on ? marker.playerId : null);
                        if (on) setCrosshair(null);
                      }}
                      onToggle={() =>
                        setPinnedId((current) =>
                          current === marker.playerId ? null : marker.playerId,
                        )
                      }
                    />
                  )}
                />
              );
            })}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {readyMarkers.map((marker, stackIndex) => {
          const active = focusId === marker.playerId;
          return (
            <button
              key={marker.playerId}
              type="button"
              onMouseEnter={() => {
                setHoveredId(marker.playerId);
                setCrosshair(null);
              }}
              onMouseLeave={() => setHoveredId(null)}
              onClick={() =>
                setPinnedId((current) =>
                  current === marker.playerId ? null : marker.playerId,
                )
              }
              className={cn(
                "text-left text-[11px] font-semibold tabular-nums",
                active ? "text-zinc-900" : "text-zinc-500 hover:text-zinc-800",
              )}
              style={{ color: active ? marker.color : undefined }}
            >
              <span className="mr-1 text-zinc-400">{stackIndex + 1}.</span>
              {marker.shortName}
            </button>
          );
        })}
      </div>
    </div>
  );
}
