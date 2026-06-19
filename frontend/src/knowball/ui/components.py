"""Reusable Streamlit widgets for player comparison (Phase 3)."""

from __future__ import annotations

import polars as pl
import streamlit as st

from knowball.analytics import (
    filter_logs_by_player_context,
    format_player_context_label,
    league_current_season,
    player_metric_average,
    player_summary,
    player_timeframe_options,
)
from knowball.cache import filter_player_logs, get_player_game_logs
from knowball.chart_cache import (
    get_cached_player_percentiles,
    get_league_kde_for_player_context,
)
from knowball.charts import context_comparison_chart, head_to_head_chart
from knowball.config import DISTRIBUTION_METRICS, METRIC_LABELS


def active_player_options(players: pl.DataFrame, logs: pl.DataFrame) -> dict[str, str]:
    """Map gsis_id → display_name for players with ingested game logs."""
    active_ids = logs.select("player_id").unique().to_series().to_list()
    subset = players.filter(pl.col("gsis_id").is_in(active_ids)).sort("display_name")
    return {
        row["gsis_id"]: row["display_name"]
        for row in subset.select("gsis_id", "display_name").iter_rows(named=True)
    }


def render_player_selectors(labels: dict[str, str]) -> tuple[str | None, str | None]:
    """Two side-by-side selectors; second is optional for head-to-head."""
    ids = list(labels.keys())
    if not ids:
        st.warning("No players with game logs found. Run ingest first.")
        return None, None

    col_a, col_b = st.columns(2)
    with col_a:
        player_a = st.selectbox(
            "Player A",
            options=ids,
            format_func=lambda pid: labels[pid],
            key="player_a",
        )
    with col_b:
        compare_h2h = st.checkbox("Compare head-to-head", value=False)
        player_b = None
        if compare_h2h:
            other_ids = [pid for pid in ids if pid != player_a]
            if other_ids:
                player_b = st.selectbox(
                    "Player B",
                    options=other_ids,
                    format_func=lambda pid: labels[pid],
                    key="player_b",
                )
            else:
                st.info("Select a different Player A to enable head-to-head.")

    return player_a, player_b


def render_player_context_selector(
    player_id: str,
    player_logs: pl.DataFrame,
    *,
    league_current_season: int | None,
    label: str,
    key: str,
) -> str:
    """Per-player timeframe selector with All-Time as the default."""
    options = player_timeframe_options(
        player_logs,
        league_current_season=league_current_season,
    )
    values = [value for value, _ in options]
    labels = {value: option_label for value, option_label in options}
    return st.selectbox(
        label,
        options=values,
        format_func=lambda value: labels[value],
        key=key,
    )


def render_player_card(
    logs: pl.DataFrame,
    *,
    title_suffix: str = "",
    context_label: str | None = None,
) -> None:
    summary = player_summary(logs)
    name = summary["display_name"] or "Unknown"
    position = summary["position"] or "—"
    teams = ", ".join(summary["teams"]) if summary["teams"] else "—"
    context_suffix = f" · {context_label}" if context_label else ""

    st.markdown(
        f"""
        <div class="player-card">
            <h3>{name}{title_suffix}</h3>
            <div class="meta">{position} · {summary["games"]} games · {teams}{context_suffix}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    metric_cols = st.columns(len(DISTRIBUTION_METRICS))
    for col, metric in zip(metric_cols, DISTRIBUTION_METRICS, strict=True):
        avg = player_metric_average(logs, metric)
        label = METRIC_LABELS[metric]
        with col:
            st.metric(label, f"{avg:.2f}" if avg is not None else "—")


def render_percentile_sliders(
    percentiles: dict[str, float | None],
    *,
    key_prefix: str = "pct",
) -> None:
    st.markdown('<div class="percentile-slider">', unsafe_allow_html=True)
    for metric in DISTRIBUTION_METRICS:
        pct = percentiles.get(metric)
        label = METRIC_LABELS[metric]
        if pct is None:
            st.caption(f"{label} — no data in this timeframe")
            continue
        st.slider(
            label,
            min_value=0,
            max_value=100,
            value=int(round(pct)),
            disabled=True,
            key=f"{key_prefix}_{metric}",
            help=f"{pct:.0f}th percentile vs league",
        )
    st.markdown("</div>", unsafe_allow_html=True)


def render_distribution_charts(
    *,
    metric: str,
    context_a: str,
    context_label_a: str,
    player_a_id: str,
    player_a_name: str,
    player_b_id: str | None,
    player_b_name: str | None,
    context_b: str | None = None,
    context_label_b: str | None = None,
    league_current_season: int | None,
) -> None:
    logs_a = filter_logs_by_player_context(
        filter_player_logs(player_a_id),
        context_a,
        league_current_season=league_current_season,
    )

    if player_b_id is None:
        avg = player_metric_average(logs_a, metric)
        fig = context_comparison_chart(
            metric=metric,
            league_kde=get_league_kde_for_player_context(
                metric,
                context_a,
                player_a_id,
                league_current_season,
            ),
            player_logs=logs_a,
            player_name=player_a_name,
            player_average=avg,
            timeframe=context_label_a,
        )
        st.plotly_chart(fig, use_container_width=True)
        return

    logs_b = filter_logs_by_player_context(
        filter_player_logs(player_b_id),
        context_b or context_a,
        league_current_season=league_current_season,
    )
    fig = head_to_head_chart(
        metric=metric,
        logs_a=logs_a,
        logs_b=logs_b,
        name_a=player_a_name,
        name_b=player_b_name or "Player B",
        context_label_a=context_label_a,
        context_label_b=context_label_b or context_label_a,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_savant_tab(players: pl.DataFrame) -> None:
    """Main Savant percentile UI."""
    from knowball.ui.styles import inject_savant_styles

    inject_savant_styles()

    logs = get_player_game_logs()
    labels = active_player_options(players, logs)
    current_season = league_current_season(logs)

    st.subheader("Search & compare")
    player_a, player_b = render_player_selectors(labels)
    if player_a is None:
        return

    logs_a_full = filter_player_logs(player_a)
    logs_b_full = filter_player_logs(player_b) if player_b else None

    context_cols = st.columns(2 if player_b else 1)
    with context_cols[0]:
        context_a = render_player_context_selector(
            player_a,
            logs_a_full,
            league_current_season=current_season,
            label="Player A timeframe",
            key=f"context_{player_a}",
        )
    context_b = None
    if player_b and logs_b_full is not None:
        with context_cols[1]:
            context_b = render_player_context_selector(
                player_b,
                logs_b_full,
                league_current_season=current_season,
                label="Player B timeframe",
                key=f"context_{player_b}",
            )

    context_label_a = format_player_context_label(context_a, logs_a_full)
    context_label_b = (
        format_player_context_label(context_b, logs_b_full)
        if player_b and logs_b_full is not None and context_b is not None
        else None
    )

    name_a = labels[player_a]
    name_b = labels[player_b] if player_b else None

    st.subheader("Player profile")
    card_cols = st.columns(2 if player_b else 1)
    logs_a = filter_logs_by_player_context(
        logs_a_full,
        context_a,
        league_current_season=current_season,
    )
    with card_cols[0]:
        render_player_card(logs_a, context_label=context_label_a)
    if player_b and logs_b_full is not None and context_b is not None:
        logs_b = filter_logs_by_player_context(
            logs_b_full,
            context_b,
            league_current_season=current_season,
        )
        with card_cols[1]:
            render_player_card(logs_b, title_suffix=" (B)", context_label=context_label_b)

    st.subheader("Percentile ranks")
    if player_b is None:
        percentiles = get_cached_player_percentiles(
            player_a,
            context_a,
            current_season,
        )
        render_percentile_sliders(percentiles, key_prefix=f"pct_{player_a}")
    else:
        pct_cols = st.columns(2)
        with pct_cols[0]:
            st.markdown(f"**{name_a}** · {context_label_a}")
            pct_a = get_cached_player_percentiles(player_a, context_a, current_season)
            render_percentile_sliders(pct_a, key_prefix=f"pct_{player_a}")
        with pct_cols[1]:
            st.markdown(f"**{name_b}** · {context_label_b}")
            pct_b = get_cached_player_percentiles(
                player_b,
                context_b or context_a,
                current_season,
            )
            render_percentile_sliders(pct_b, key_prefix=f"pct_{player_b}")

    st.subheader("Empirical distributions")
    metric = st.selectbox(
        "Metric",
        options=list(DISTRIBUTION_METRICS),
        format_func=lambda m: METRIC_LABELS[m],
        key="chart_metric",
    )
    render_distribution_charts(
        metric=metric,
        context_a=context_a,
        context_label_a=context_label_a,
        player_a_id=player_a,
        player_a_name=name_a,
        player_b_id=player_b,
        player_b_name=name_b,
        context_b=context_b,
        context_label_b=context_label_b,
        league_current_season=current_season,
    )
