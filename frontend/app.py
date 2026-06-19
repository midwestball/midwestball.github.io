"""Knowball Streamlit app — Savant percentile UI + data layer."""

from __future__ import annotations

import polars as pl
import streamlit as st

from knowball.cache import (
    filter_player_logs,
    get_league_distributions,
    get_player_game_logs,
    get_players,
)
from knowball.config import DB_PATH, PLAYER_GAME_LOGS_PATH, supabase_is_configured
from knowball.db import pandas_to_polars
from knowball.ui.components import render_savant_tab

st.set_page_config(page_title="Knowball", page_icon="🏈", layout="wide")

st.title("Knowball")
st.caption("NFL analytics — percentile profiles and empirical distributions")

using_remote_db = supabase_is_configured()
if not using_remote_db and (
    not DB_PATH.exists() or not PLAYER_GAME_LOGS_PATH.exists()
):
    st.error(
        "Local data not found. Run `uv run python scripts/ingest_data.py` first."
    )
    st.stop()
elif using_remote_db and not PLAYER_GAME_LOGS_PATH.exists():
    st.error(
        "Parquet cache not found. Run `uv run python scripts/ingest_data.py` first."
    )
    st.stop()

players = get_players()

tab_savant, tab_data = st.tabs(["Savant", "Data layer"])

with tab_savant:
    render_savant_tab(players)

with tab_data:
    st.subheader("Phase 2 — connection & cache diagnostics")
    conn = st.connection("knowball_db", type="sql")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        players_count = conn.query("SELECT COUNT(*) AS n FROM players").iloc[0, 0]
        st.metric("Players", f"{players_count:,}")
    with col2:
        games_count = conn.query("SELECT COUNT(*) AS n FROM games").iloc[0, 0]
        st.metric("Games", f"{games_count:,}")
    with col3:
        stats_count = conn.query("SELECT COUNT(*) AS n FROM stats").iloc[0, 0]
        st.metric("Stat rows", f"{stats_count:,}")
    with col4:
        bins_count = conn.query(
            "SELECT COUNT(*) AS n FROM league_distributions"
        ).iloc[0, 0]
        st.metric("Distribution bins", f"{bins_count:,}")

    logs = get_player_game_logs()
    distributions = get_league_distributions()
    st.write(
        f"Parquet cache: **{logs.height:,}** game logs · "
        f"League bins: **{distributions.height:,}** rows"
    )

    qbs = get_players(position="QB")
    if qbs.is_empty():
        st.warning("No quarterbacks found in the player directory.")
    else:
        options = qbs.sort("display_name").select("gsis_id", "display_name").to_dicts()
        labels = {row["gsis_id"]: row["display_name"] for row in options}
        player_id = st.selectbox(
            "Sample QB lookup",
            options=list(labels.keys()),
            format_func=lambda pid: labels[pid],
            key="data_tab_player",
        )

        stats_df = pandas_to_polars(
            conn.query(
                """
                SELECT season, week, team, opponent_team, passing_epa, rushing_epa
                FROM stats
                WHERE player_id = :player_id
                ORDER BY season, week
                """,
                params={"player_id": player_id},
            ),
            schema="stats",
        )

        parquet_df = filter_player_logs(player_id)
        st.write(f"**{labels[player_id]}** — {stats_df.height} games via SQL")
        st.dataframe(
            stats_df.select(
                "season", "week", "team", "opponent_team", "passing_epa", "rushing_epa"
            ),
            width="stretch",
            hide_index=True,
        )

        if stats_df.height != parquet_df.height:
            st.warning("SQL and Parquet row counts differ for this player.")
        else:
            st.success("SQL connection and Parquet cache agree on row count.")

    with st.expander("Sample league distribution (passing_epa, Current Season)"):
        sample = distributions.filter(
            (pl.col("metric") == "passing_epa")
            & (pl.col("timeframe_context") == "Current Season")
        ).sort("bin_start")
        st.dataframe(sample, width="stretch", hide_index=True)
