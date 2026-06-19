"""Checkpoint 2.2 — @st.cache_data performance."""

from __future__ import annotations

import time

import pytest
import streamlit as st

from knowball.cache import get_league_distributions, get_player_game_logs
from knowball.config import DB_PATH, PLAYER_GAME_LOGS_PATH


@pytest.fixture(autouse=True)
def clear_streamlit_cache() -> None:
    st.cache_data.clear()
    yield
    st.cache_data.clear()


@pytest.mark.skipif(
    not DB_PATH.exists() or not PLAYER_GAME_LOGS_PATH.exists(),
    reason="Local data not ingested",
)
def test_cached_loads_are_fast_on_second_call() -> None:
    get_player_game_logs()
    t0 = time.perf_counter()
    get_player_game_logs()
    parquet_elapsed = time.perf_counter() - t0

    get_league_distributions()
    t0 = time.perf_counter()
    get_league_distributions()
    distributions_elapsed = time.perf_counter() - t0

    assert parquet_elapsed < 0.5, f"Parquet cache reload took {parquet_elapsed:.3f}s"
    assert distributions_elapsed < 0.1, (
        f"Distributions cache reload took {distributions_elapsed:.3f}s"
    )
