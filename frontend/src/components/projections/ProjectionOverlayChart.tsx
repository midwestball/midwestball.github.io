"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ProjectionEntityDistribution, ProjectionEntitySummary } from "@/lib/projections";
import { pdfAtPoints } from "@/lib/projection-math";
import { assignTeamLineColors } from "@/lib/team-colors";
import { projectionStyle } from "./ProjectionSummaryCards";

/** How close, in pixels, the cursor must be to grab the threshold line. */
const GRAB_PX = 12;
/** Chart geometry. The plot area is inset by the Y axis on the left and the right margin. */
const YAXIS_WIDTH = 44;
// The top margin leaves room for the threshold value printed above the plot.
const MARGIN = { top: 26, right: 12, bottom: 10, left: 0 } as const;
const PLOT_LEFT = YAXIS_WIDTH + MARGIN.left;

/**
 * The threshold line wears near-black so it never reads as a team curve, and the
 * numbers underneath are badged with the same value to tie the two together.
 */
export const THRESHOLD_COLOR = "#18181b";

/** Keep a threshold inside the published grid. */
export function clampThreshold(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/** Arrow-key movement for the threshold handle. Shift moves five points at a time. */
export function thresholdNudge(key: string, current: number, shiftKey: boolean, min: number, max: number): number | null {
  const step = shiftKey ? 5 : 1;
  if (key === "ArrowLeft") return clampThreshold(current - step, min, max);
  if (key === "ArrowRight") return clampThreshold(current + step, min, max);
  if (key === "Home") return min;
  if (key === "End") return max;
  return null;
}

/** Snap a dragged value to the grid and clamp it. */
export function snapThreshold(value: number, min: number, max: number): number {
  return Number(clampThreshold(value, min, max).toFixed(1));
}

/** Is the cursor close enough to the threshold line to count as hovering it? */
export function isOverThreshold(value: number | null, threshold: number, pxPerUnit: number): boolean {
  if (value == null || !Number.isFinite(value) || !(pxPerUnit > 0)) return false;
  return Math.abs(value - threshold) * pxPerUnit <= GRAB_PX;
}

/** Map a cursor position inside the plot area to a fantasy-point value. */
export function valueFromClientX(clientX: number, rectLeft: number, rectWidth: number, min: number, max: number): number | null {
  const plotWidth = rectWidth - PLOT_LEFT - MARGIN.right;
  if (plotWidth <= 0) return null;
  const px = clientX - rectLeft - PLOT_LEFT;
  return clampThreshold(min + (px / plotWidth) * (max - min), min, max);
}

export function ProjectionOverlayChart({
  grid,
  entities,
  curves,
  focus,
  threshold,
  onFocus,
  onThresholdChange,
}: {
  grid: number[];
  entities: ProjectionEntitySummary[];
  curves: Map<string, ProjectionEntityDistribution>;
  focus: string | null;
  threshold: number;
  onFocus: (id: string) => void;
  onThresholdChange: (points: number) => void;
}) {
  const colors = assignTeamLineColors(entities);
  const min = grid[0]!;
  const max = grid.at(-1)!;
  const plotRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  // The pending value lives in a ref as well as state: the release handler is a DOM
  // event, and committing from inside a state updater would run twice under StrictMode.
  const pendingRef = useRef<number | null>(null);
  const [dragValue, setDragValue] = useState<number | null>(null);
  const [handleFocused, setHandleFocused] = useState(false);
  const [hovered, setHovered] = useState(false);
  const hoverRef = useRef(false);
  const [plotBox, setPlotBox] = useState<{ width: number; height: number } | null>(null);
  const draggingNow = dragValue != null;
  const activeThreshold = dragValue ?? threshold;

  const commit = useCallback((v: number) => onThresholdChange(snapThreshold(v, min, max)), [min, max, onThresholdChange]);
  const setDrag = useCallback((value: number | null) => { pendingRef.current = value; setDragValue(value); }, []);

  // Recharts' event payload has no chart width, so the pixel mapping is measured here
  // rather than inferred from its state.
  const valueAt = useCallback((clientX: number) => {
    const rect = plotRef.current?.getBoundingClientRect();
    if (!rect) return null;
    return valueFromClientX(clientX, rect.left, rect.width, min, max);
  }, [min, max]);

  useEffect(() => {
    const el = plotRef.current;
    if (!el) return;
    const measure = () => {
      const rect = el.getBoundingClientRect();
      setPlotBox((prev) =>
        prev && prev.width === rect.width && prev.height === rect.height
          ? prev
          : { width: rect.width, height: rect.height },
      );
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // A soft band over the line hints that it can be grabbed. State is only written
  // when the answer changes, so ordinary mouse movement does not re-render.
  const handleHoverMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const plotWidth = (plotBox?.width ?? 0) - PLOT_LEFT - MARGIN.right;
    const pxPerUnit = plotWidth / (max - min || 1);
    const near = isOverThreshold(valueAt(event.clientX), activeThreshold, pxPerUnit);
    if (near !== hoverRef.current) {
      hoverRef.current = near;
      setHovered(near);
    }
  };

  const clearHover = () => {
    if (!hoverRef.current) return;
    hoverRef.current = false;
    setHovered(false);
  };

  const beginDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    const rect = plotRef.current?.getBoundingClientRect();
    if (!rect) return;
    const value = valueAt(event.clientX);
    if (value == null) return;
    const plotWidth = rect.width - PLOT_LEFT - MARGIN.right;
    if (!isOverThreshold(value, threshold, plotWidth / (max - min || 1))) return;
    dragging.current = true;
    setDrag(value);
    event.preventDefault();
  };

  useEffect(() => {
    if (!draggingNow) return;
    const move = (event: PointerEvent) => {
      const value = valueAt(event.clientX);
      if (value != null) setDrag(value);
    };
    const release = () => {
      const pending = pendingRef.current;
      dragging.current = false;
      setDrag(null);
      if (pending != null) onThresholdChange(snapThreshold(pending, min, max));
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", release);
    window.addEventListener("pointercancel", release);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", release);
      window.removeEventListener("pointercancel", release);
    };
  }, [draggingNow, min, max, onThresholdChange, setDrag, valueAt]);

  const showBand = hovered || draggingNow || handleFocused;

  const data = grid.map((x, i) => {
    const row: Record<string, number | null> = { x };
    entities.forEach((e) => { row[e.entityKey] = curves.get(e.entityKey)?.pdf[i] ?? null; });
    const f = focus ? curves.get(focus) : undefined;
    // Shade the upper tail: the decision is "at least this many points".
    row.shaded = f && x >= activeThreshold ? f.pdf[i]! : null;
    return row;
  });
  if (focus && curves.has(focus) && activeThreshold > min && activeThreshold < max && !grid.includes(activeThreshold)) {
    const row: Record<string, number | null> = { x: activeThreshold };
    entities.forEach((e) => { const c = curves.get(e.entityKey); row[e.entityKey] = c ? pdfAtPoints(grid, c.pdf, activeThreshold) : null; });
    row.shaded = pdfAtPoints(grid, curves.get(focus)!.pdf, activeThreshold);
    data.push(row);
    data.sort((a, b) => (a.x as number) - (b.x as number));
  }

  return (
    <div className="h-80 border border-zinc-200 bg-white p-2">
      <div
        ref={plotRef}
        data-testid="threshold-plot"
        className="relative h-72"
        style={{ touchAction: "none", cursor: hovered || draggingNow ? "ew-resize" : undefined }}
        onPointerDown={beginDrag}
        onPointerMove={handleHoverMove}
        onPointerLeave={clearHover}
      >
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={MARGIN}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="x" type="number" domain={[min, max]} tickFormatter={(v) => Number(v).toFixed(0)} label={{ value: "Fantasy points", position: "insideBottom", offset: -5 }} />
            <YAxis tickFormatter={(v) => Number(v).toFixed(2)} width={YAXIS_WIDTH} />
            {/* Recharts' own series tooltip is suppressed; the threshold is read from the line. */}
            <Tooltip content={() => null} cursor={false} isAnimationActive={false} />
            <Area dataKey="shaded" stroke="none" fill="#71717a" fillOpacity={0.22} isAnimationActive={false} />
            {entities.map((e, i) => {
              const style = projectionStyle(i);
              return (
                <Line
                  key={e.entityKey}
                  dataKey={e.entityKey}
                  name={e.name}
                  stroke={colors.get(e.entityKey) ?? style.color}
                  strokeDasharray={style.dash}
                  strokeWidth={focus === e.entityKey ? 3 : 2}
                  dot={false}
                  connectNulls
                  isAnimationActive={false}
                  onClick={() => onFocus(e.entityKey)}
                />
              );
            })}
            <ReferenceLine
              x={activeThreshold}
              stroke={THRESHOLD_COLOR}
              strokeWidth={draggingNow ? 3 : 2}
              strokeDasharray={draggingNow || hovered ? undefined : "4 3"}
              label={(props: { x?: number; y?: number }) => {
                // Recharts anchors a reference-line label at the MIDDLE of the
                // line by default, so props.y is not the top of the plot. Only
                // props.x is used (the rect is zero-width, so it is the line's x);
                // the vertical placement is computed from our own margin.
                const x = props.x ?? 0;
                const topY = MARGIN.top;
                return (
                  <g
                    role="slider"
                    tabIndex={0}
                    aria-label="Focused threshold fantasy points"
                    aria-valuemin={min}
                    aria-valuemax={max}
                    aria-valuenow={Number(activeThreshold.toFixed(1))}
                    aria-valuetext={`${activeThreshold.toFixed(1)} points`}
                    style={{ cursor: "ew-resize", outline: "none" }}
                    onFocus={() => setHandleFocused(true)}
                    onBlur={() => setHandleFocused(false)}
                    onKeyDown={(event) => {
                      const next = thresholdNudge(event.key, threshold, event.shiftKey, min, max);
                      if (next == null) return;
                      event.preventDefault();
                      commit(next);
                    }}
                  >
                    {/* Invisible grab strip, plus a soft band that hints the line is draggable. */}
                    <rect x={x - GRAB_PX} y={topY - 13} width={GRAB_PX * 2} height={26} fill="transparent" />
                    {/* Value printed above the plot, on the line's own x. The white
                        stroke is a halo so it stays readable over the top edge. */}
                    <text
                      x={plotBox ? Math.min(Math.max(x, 20), plotBox.width - 20) : x}
                      y={topY - 6}
                      textAnchor="middle"
                      fontSize={11}
                      fontWeight={600}
                      fill={THRESHOLD_COLOR}
                      stroke="#ffffff"
                      strokeWidth={3}
                      paintOrder="stroke"
                      aria-hidden="true"
                    >
                      {activeThreshold.toFixed(1)}
                    </text>
                    {showBand && plotBox ? (
                      <rect
                        x={x - GRAB_PX}
                        y={MARGIN.top}
                        width={GRAB_PX * 2}
                        height={Math.max(0, plotBox.height - MARGIN.top - MARGIN.bottom)}
                        fill={THRESHOLD_COLOR}
                        opacity={draggingNow ? 0.12 : 0.07}
                        data-testid="threshold-band"
                      />
                    ) : null}
                  </g>
                );
              }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 px-1 text-[11px] text-zinc-500">
        Drag the vertical line, or focus it and use the arrow keys, to move the focused threshold.
      </p>
    </div>
  );
}
