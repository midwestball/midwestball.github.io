"""Streamlit-cached data loaders (Phase 2)."""

from __future__ import annotations

import polars as pl
import streamlit as st

from knowball.loaders import (
    fetch_player_stats,
    load_league_distributions,
    load_player_game_logs,
    load_players,
)


@st.cache_data
def get_player_game_logs() -> pl.DataFrame:
    return load_player_game_logs()


@st.cache_data
def get_league_distributions() -> pl.DataFrame:
    return load_league_distributions()


@st.cache_data
def get_players(*, position: str | None = None) -> pl.DataFrame:
    return load_players(position=position)


@st.cache_data
def get_player_stats(player_id: str) -> pl.DataFrame:
    return fetch_player_stats(player_id)


def filter_player_logs(player_id: str) -> pl.DataFrame:
    """Filter cached Parquet logs for one player (in-memory, no re-read)."""
    return get_player_game_logs().filter(pl.col("player_id") == player_id)
