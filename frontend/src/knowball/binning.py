"""Histogram binning using Doane's rule (extends Sturges for skewed data)."""

from __future__ import annotations

import math

import polars as pl


def doane_bin_count(values: pl.Series) -> int:
    """Return the number of histogram bins per Doane's formula."""
    n = values.len()
    if n < 2:
        return 1

    mean = values.mean()
    if mean is None:
        return 1

    deviations = values - mean
    m2 = (deviations.pow(2).sum()) / n
    if m2 == 0:
        return 1

    m3 = (deviations.pow(3).sum()) / n
    g1 = m3 / (m2 ** 1.5)
    sigma_g1 = math.sqrt(6 * (n - 2) / ((n + 1) * (n + 3)))
    if sigma_g1 == 0:
        # n == 2: skewness SE undefined; fall back to Sturges
        return max(1, int(math.ceil(1 + math.log2(n))))
    else:
        k = 1 + math.log2(n) + math.log2(1 + abs(g1) / sigma_g1)
        return max(1, int(math.ceil(k)))


def histogram_bins(
    df: pl.DataFrame,
    metric: str,
    *,
    bin_count: int | None = None,
) -> pl.DataFrame:
    """
    Bin a metric column into histogram intervals.

    Returns a DataFrame with columns: bin_start, bin_end, count.
    """
    values_df = df.select(pl.col(metric).drop_nulls().alias("value"))
    if values_df.is_empty():
        return pl.DataFrame(
            schema={"bin_start": pl.Float64, "bin_end": pl.Float64, "count": pl.Int64}
        )

    values = values_df["value"]
    k = bin_count if bin_count is not None else doane_bin_count(values)
    vmin = float(values.min())  # type: ignore[arg-type]
    vmax = float(values.max())  # type: ignore[arg-type]

    if vmin == vmax:
        return pl.DataFrame(
            {"bin_start": [vmin], "bin_end": [vmax], "count": [values.len()]}
        )

    width = (vmax - vmin) / k
    edges = [vmin + i * width for i in range(k + 1)]

    counts: list[int] = []
    for i in range(k):
        lo, hi = edges[i], edges[i + 1]
        if i < k - 1:
            count = values_df.filter(
                (pl.col("value") >= lo) & (pl.col("value") < hi)
            ).height
        else:
            count = values_df.filter(
                (pl.col("value") >= lo) & (pl.col("value") <= hi)
            ).height
        counts.append(count)

    return pl.DataFrame(
        {
            "bin_start": edges[:-1],
            "bin_end": edges[1:],
            "count": counts,
        }
    )
