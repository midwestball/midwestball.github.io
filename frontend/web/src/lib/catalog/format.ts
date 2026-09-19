import type { ValueFormat } from "./types";

export function formatStatValue(format: ValueFormat, value: number): string {
  switch (format) {
    case "count":
    case "yards":
      return String(Math.round(value));
    case "one_decimal":
      return value.toFixed(1);
    case "two_decimal":
      return value.toFixed(2);
    case "percent":
      return `${(value * 100).toFixed(1)}%`;
    case "percent_pts":
      return `${value.toFixed(1)}%`;
    case "rating":
      return value.toFixed(1);
    case "seconds":
      return `${value.toFixed(2)}s`;
    case "ratio":
      return value.toFixed(2);
  }
}
