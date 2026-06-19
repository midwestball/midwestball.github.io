"""Tests for cached league KDE."""

from __future__ import annotations

import time

import pytest
import streamlit as st

from knowball.chart_cache import get_league_kde
from knowball.config import DB_PATH, PLAYER_GAME_LOGS_PATH, TIMEFRAME_ALL_TIME


@pytest.fixture(autouse=True)
def clear_streamlit_cache() -> None:
    st.cache_data.clear()
    yield
    st.cache_data.clear()


@pytest.mark.skipif(
    not DB_PATH.exists() or not PLAYER_GAME_LOGS_PATH.exists(),
    reason="Local data not ingested",
)
def test_league_kde_cache_is_fast_on_second_call() -> None:
    get_league_kde("receiving_epa", TIMEFRAME_ALL_TIME)
    t0 = time.perf_counter()
    get_league_kde("receiving_epa", TIMEFRAME_ALL_TIME)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.05, f"Cached league KDE reload took {elapsed:.3f}s"
