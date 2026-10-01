"use client";
import { useState } from "react";

/**
 * A deliberately small numeric field for the points threshold. It commits on blur
 * or Enter, and follows the chart while the user drags the line.
 */
export function ProjectionPointsInput({
  points,
  min,
  max,
  onCommit,
}: {
  points: number;
  min: number;
  max: number;
  onCommit: (points: number) => void;
}) {
  // A null draft means "follow the threshold", so chart drags stay in sync while
  // the user is typing without an effect that would fight their keystrokes.
  const [draft, setDraft] = useState<string | null>(null);
  const [error, setError] = useState("");
  const text = draft ?? points.toFixed(1);

  const commit = () => {
    const parsed = Number(text);
    if (draft === null || text.trim() === "" || !Number.isFinite(parsed)) {
      setError(`Enter a number between ${min.toFixed(1)} and ${max.toFixed(1)}.`);
      return;
    }
    if (parsed < min || parsed > max) {
      setError(`Enter ${min.toFixed(1)} to ${max.toFixed(1)}.`);
      return;
    }
    setError("");
    setDraft(null);
    onCommit(Number(parsed.toFixed(1)));
  };

  return (
    <div className="flex items-center gap-2">
      <label htmlFor="projection-points" className="text-sm text-zinc-600">
        Fantasy points
      </label>
      <input
        id="projection-points"
        aria-label="Fantasy points threshold"
        aria-describedby={error ? "projection-points-error" : undefined}
        aria-invalid={error ? true : undefined}
        value={text}
        inputMode="decimal"
        size={5}
        onChange={(event) => {
          setDraft(event.target.value);
          setError("");
        }}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") commit();
        }}
        className="w-20 rounded-none border border-zinc-300 px-2 py-1 text-sm tabular-nums"
      />
      {error ? (
        <p id="projection-points-error" role="alert" className="text-xs text-red-700">
          {error}
        </p>
      ) : null}
    </div>
  );
}
