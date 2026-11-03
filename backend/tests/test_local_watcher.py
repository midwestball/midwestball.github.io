import importlib.util
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl
import pytest

spec = importlib.util.spec_from_file_location(
    "local_watcher", Path(__file__).parents[1] / "local_ops/watcher.py"
)
watcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watcher)

CFG = {"season": 2026, "game_duration_hours": 3.5,
       "after_end_buffer_minutes": 5, "morning_after_hour": 9,
       "evening_after_hour": 18, "tuesday_hour": 10, "tuesday_minute": 0}
SCHEDULE = pl.DataFrame({"game_id": ["2026_08_CHI_SEA"], "week": [8],
    "gameday": ["2026-11-02"], "gametime": ["20:15"],
    "home_score": [20], "away_score": [17]})


@pytest.mark.parametrize("hour,expected", [(9, 10), (10, None), (11, None)])
def test_dst_shifted_tuesday_waits_for_configured_window(hour, expected):
    now = datetime(2026, 11, 3, hour, tzinfo=ZoneInfo("America/New_York"))
    target = watcher._early_tuesday_target(SCHEDULE, CFG, now, {"completed": {}})
    assert (target.hour if target else None) == expected


def test_early_tuesday_does_not_wait_or_retrain_completed_week():
    now = datetime(2026, 11, 3, 9, tzinfo=ZoneInfo("America/New_York"))
    state = {"completed": {"2026:week8:tuesday": "verified"}}
    assert watcher._early_tuesday_target(SCHEDULE, CFG, now, state) is None


def test_wait_refreshes_state_and_avoids_duplicate_run(monkeypatch):
    early = datetime(2026, 11, 3, 9, tzinfo=ZoneInfo("America/New_York"))
    ready = early.replace(hour=10)
    times = iter([early, ready])
    states = iter([{"completed": {}}, {"completed": {"2026:week8:tuesday": "manual"}}])
    monkeypatch.setattr(watcher, "_now", lambda tz: next(times))
    monkeypatch.setattr(watcher, "_load_config", lambda: CFG)
    monkeypatch.setattr(watcher, "_load_state", lambda: next(states))
    monkeypatch.setattr(watcher, "_load_schedules", lambda season: SCHEDULE)
    monkeypatch.setattr(watcher.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(watcher, "_log_event", lambda event: None)
    monkeypatch.setattr(watcher, "_run_pipeline", lambda *a, **kw: pytest.fail("already completed"))
    monkeypatch.setattr("sys.argv", ["watcher", "--mode", "tuesday"])
    assert watcher.main() == 0


def test_early_tuesday_runs_full_pipeline_at_ten_and_records_completion(monkeypatch):
    early = datetime(2026, 11, 3, 9, tzinfo=ZoneInfo("America/New_York"))
    times = iter([early, early.replace(hour=10)])
    calls, saved = [], []
    monkeypatch.setattr(watcher, "_now", lambda tz: next(times))
    monkeypatch.setattr(watcher, "_load_config", lambda: CFG)
    monkeypatch.setattr(watcher, "_load_state", lambda: {"completed": {}})
    monkeypatch.setattr(watcher, "_load_schedules", lambda season: SCHEDULE)
    monkeypatch.setattr(watcher.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(watcher, "_log_event", lambda event: None)
    monkeypatch.setattr(watcher, "_save_state", saved.append)
    monkeypatch.setattr(watcher, "_run_pipeline", lambda cfg, week, **kw: calls.append((week, kw["projections"])) or 0)
    monkeypatch.setattr("sys.argv", ["watcher", "--mode", "tuesday"])
    assert watcher.main() == 0
    assert calls == [(8, True)]
    assert "2026:week8:tuesday" in saved[0]["completed"]
