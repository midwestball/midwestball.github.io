"""Stage E — oriented empirical midranks on Stage C rows."""

from __future__ import annotations

import time
from dataclasses import dataclass

import polars as pl

from ballnet.catalog.registry import stats_for_group
from ballnet.density import empirical_percentile, load_densities
from ballnet.paths import YTD_DIR, ensure_data_dirs


@dataclass(frozen=True)
class PercentileResult:
    path: str
    rows: int
    seconds: float


def attach_percentiles(
    season: int,
    as_of_week: int,
    *,
    position_group: str = "qb",
) -> PercentileResult:
    """Write Stage C panel with `percentile` filled from qualified peer counts."""
    if position_group not in {
        "qb",
        "backfield",
        "pass_catcher",
        "ol",
        "def_front",
        "secondary",
        "kicker",
        "punter",
        "returner",
    }:
        raise NotImplementedError(f"percentiles unknown group {position_group}")
    ensure_data_dirs()
    t0 = time.perf_counter()

    ytd_path = YTD_DIR / f"ytd_{position_group}_{season}_w{as_of_week}.parquet"
    long = pl.read_parquet(ytd_path)
    if "aggregation_version" not in long.columns or (long.height and set(long["aggregation_version"].to_list()) != {"observed-v2"}):
        raise ValueError("Stage C data predates observed-v2; rebuild before attaching percentiles")
    dens_by_id = load_densities(season, as_of_week, position_group=position_group)
    higher = {s.id: s.higher_is_better for s in stats_for_group(position_group)}

    percentiles: list[float | None] = []
    for row in long.to_dicts():
        dens = dens_by_id.get(row["stat_id"])
        value = row.get("player_value")
        if (
            dens is None
            or value is None
            or not row.get("qualified")
            or dens["n_sample"] < 2
        ):
            percentiles.append(None)
            continue
        percentiles.append(
            empirical_percentile(float(value), dens.get("value_counts", []), higher_is_better=higher[row["stat_id"]])
        )

    out = long.with_columns(pl.Series("percentile", percentiles, dtype=pl.Float64), pl.lit("qualified-ytd-midrank-v2").alias("percentile_method"))
    out_path = YTD_DIR / f"ytd_{position_group}_{season}_w{as_of_week}_pct.parquet"
    out.write_parquet(out_path)
    return PercentileResult(
        path=str(out_path),
        rows=out.height,
        seconds=time.perf_counter() - t0,
    )


def require_empirical_panel(panel: pl.DataFrame) -> None:
    if "percentile_method" not in panel.columns or (panel.height and set(panel["percentile_method"].to_list()) != {"qualified-ytd-midrank-v2"}):
        raise ValueError("Percentile panel predates observed-v2; rebuild before publishing")
