"""
Phase 1 & 2: Data Acquisition and Preprocessing Pipeline
=========================================================
Comprehensive NBA data scraper for the GATv2-GCN reproduction.
Fetches box score (traditional + advanced + tracking) data for multiple seasons.

Seasons covered:
  - 2022-23 (original paper training period: Oct 18, 2022 → Jan 20, 2023)
  - 2023-24
  - 2024-25
  - 2025-26 (available games so far)

Run:  uv run python 01_data_pipeline.py
"""

import os
import time
import pickle
import logging
import itertools
from datetime import datetime, date

import numpy as np
import pandas as pd
import networkx as nx
from nba_api.stats.endpoints import (
    leaguegamefinder,
    boxscoretraditionalv3,
    boxscoreadvancedv3,
    boxscoreplayertrackv3,
)

# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

OUTPUT_DIR = "data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Paper original date range (2022-23 season)
PAPER_START = "2022-10-18"
PAPER_END = "2023-01-20"

SEASONS = [
    ("2022-23", "2022-10-18", "2023-04-09"),
    ("2023-24", "2023-10-24", "2024-04-14"),
    ("2024-25", "2024-10-22", "2025-04-13"),
    ("2025-26", "2025-10-28", str(date.today())),
]

# Column specifications matching the paper
TRAD_COLS   = ["GAME_ID", "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_ABBREVIATION",
               "MIN", "PTS", "AST", "REB", "TO", "STL", "BLK", "PLUS_MINUS"]
ADV_COLS    = ["GAME_ID", "PLAYER_ID", "PACE", "USG_PCT", "TS_PCT"]
TRACK_COLS  = ["GAME_ID", "PLAYER_ID", "DIST", "TCHS", "PASS"]

# Final 13-feature vector (paper definition)
FEATURE_COLS = ["PTS", "AST", "REB", "TO", "STL", "BLK", "PLUS_MINUS",
                "TCHS", "PASS", "DIST", "PACE", "USG_PCT", "TS_PCT"]
MIN_MINUTES = 10.0
API_DELAY   = 1.0   # seconds between requests (conservative to avoid bans)

def call_api_with_retry(endpoint_class, *args, max_retries=5, **kwargs):
    kwargs.setdefault('timeout', 60)
    for attempt in range(max_retries):
        try:
            return endpoint_class(*args, **kwargs).get_data_frames()[0]
        except Exception as exc:
            if attempt == max_retries - 1:
                raise exc
            log.warning(f"API call failed ({exc}), retrying {attempt + 1}/{max_retries}...")
            time.sleep(API_DELAY * (2 ** attempt))


# ──────────────────────────────────────────────────────────────
# Helper: fetch game IDs for a season within a date window
# ──────────────────────────────────────────────────────────────
def get_game_ids(season: str, date_from: str, date_to: str) -> list[str]:
    """Return sorted list of unique GAME_IDs within the date window."""
    from nba_api.stats.static import teams
    nba_teams = teams.get_teams()
    
    all_game_ids = set()
    for team in nba_teams:
        time.sleep(API_DELAY)
        try:
            df = call_api_with_retry(
                leaguegamefinder.LeagueGameFinder,
                team_id_nullable=team['id'],
                season_nullable=season,
                season_type_nullable="Regular Season",
                league_id_nullable="00"
            )
            df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
            mask = (df["GAME_DATE"] >= pd.to_datetime(date_from)) & (df["GAME_DATE"] <= pd.to_datetime(date_to))
            filtered = df.loc[mask]
            if not filtered.empty:
                all_game_ids.update(filtered["GAME_ID"].tolist())
        except Exception as exc:
            log.error(f"LeagueGameFinder failed for team {team['abbreviation']} in {season}: {exc}")

    game_ids = list(all_game_ids)
    log.info(f"  Season {season}: {len(game_ids)} unique games between {date_from} and {date_to}")
    return sorted(game_ids)


# ──────────────────────────────────────────────────────────────
# Helper: fetch box score data for a single game
# ──────────────────────────────────────────────────────────────
def fetch_game_stats(game_id: str) -> pd.DataFrame | None:
    """
    Pulls traditional + advanced + player-tracking stats for one game.
    Returns a merged DataFrame (one row per qualifying player) or None on error.
    """
    try:
        time.sleep(API_DELAY)
        df_trad = call_api_with_retry(boxscoretraditionalv3.BoxScoreTraditionalV3, game_id=game_id)

        time.sleep(API_DELAY)
        df_adv = call_api_with_retry(boxscoreadvancedv3.BoxScoreAdvancedV3, game_id=game_id)

        time.sleep(API_DELAY)
        df_track = call_api_with_retry(boxscoreplayertrackv3.BoxScorePlayerTrackV3, game_id=game_id)

    except Exception as exc:
        log.warning(f"    Game {game_id} skipped – API error: {exc}")
        return None

    # Map V3 traditional columns
    trad_col_map = {
        "gameId": "GAME_ID", "personId": "PLAYER_ID", "teamId": "TEAM_ID",
        "teamTricode": "TEAM_ABBREVIATION", "minutes": "MIN", "points": "PTS",
        "assists": "AST", "reboundsTotal": "REB", "turnovers": "TO",
        "steals": "STL", "blocks": "BLK", "plusMinusPoints": "PLUS_MINUS"
    }
    df_trad = df_trad.rename(columns=trad_col_map)
    if "firstName" in df_trad.columns and "familyName" in df_trad.columns:
        df_trad["PLAYER_NAME"] = df_trad["firstName"].fillna("") + " " + df_trad["familyName"].fillna("")
        df_trad["PLAYER_NAME"] = df_trad["PLAYER_NAME"].str.strip()

    # Map V3 advanced columns
    adv_col_map = {
        "gameId": "GAME_ID", "personId": "PLAYER_ID",
        "pace": "PACE", "usagePercentage": "USG_PCT", "trueShootingPercentage": "TS_PCT"
    }
    df_adv = df_adv.rename(columns=adv_col_map)

    # Normalise column names (v3 may use different casing)
    df_track.columns = df_track.columns.str.upper()
    df_track = df_track.rename(columns={"GAMEID": "GAME_ID", "PERSONID": "PLAYER_ID"})

    # Select relevant columns
    available_trad = [c for c in TRAD_COLS if c in df_trad.columns]
    available_adv  = [c for c in ADV_COLS  if c in df_adv.columns]

    # DIST / TCHS / PASS column names vary slightly across endpoints
    track_col_map = {}
    for wanted, variants in [("DIST", ["DIST", "DISTANCE"]),
                               ("TCHS", ["TCHS", "TOUCHES"]),
                               ("PASS", ["PASS", "PASSES"])]:
        for v in variants:
            if v in df_track.columns:
                track_col_map[v] = wanted
                break

    df_track = df_track.rename(columns={v: k for v, k in track_col_map.items()})
    available_track = ["GAME_ID", "PLAYER_ID"] + [c for c in ["DIST", "TCHS", "PASS"] if c in df_track.columns]

    df = (df_trad[available_trad]
          .merge(df_adv[available_adv],   on=["GAME_ID", "PLAYER_ID"], how="left")
          .merge(df_track[available_track], on=["GAME_ID", "PLAYER_ID"], how="left"))

    # Parse minutes (can be "MM:SS" or a float)
    if df["MIN"].dtype == object:
        def parse_min(m):
            if pd.isna(m):
                return 0.0
            if isinstance(m, str) and ":" in m:
                parts = m.split(":")
                return float(parts[0]) + float(parts[1]) / 60
            return float(m)
        df["MIN"] = df["MIN"].apply(parse_min)

    # Apply 10-minute threshold
    df = df[df["MIN"] >= MIN_MINUTES].copy()

    return df if len(df) > 0 else None


# ──────────────────────────────────────────────────────────────
# Phase 2: Main data acquisition loop
# ──────────────────────────────────────────────────────────────
def acquire_data() -> pd.DataFrame:
    """Fetch all seasons and return a single long-form DataFrame."""
    all_frames: list[pd.DataFrame] = []

    for season, date_from, date_to in SEASONS:
        log.info(f"\n{'='*60}")
        log.info(f"Season: {season}  ({date_from} → {date_to})")
        game_ids = get_game_ids(season, date_from, date_to)
        if not game_ids:
            continue

        for idx, gid in enumerate(game_ids):
            log.info(f"  [{idx+1}/{len(game_ids)}] Fetching game {gid}")
            df_game = fetch_game_stats(gid)
            if df_game is not None and len(df_game) > 0:
                df_game["SEASON"] = season
                all_frames.append(df_game)

    if not all_frames:
        raise RuntimeError("No data fetched – check API connectivity.")

    combined = pd.concat(all_frames, ignore_index=True)
    log.info(f"\nTotal rows fetched: {len(combined):,}")
    return combined


# ──────────────────────────────────────────────────────────────
# Phase 3: Preprocessing & Matrix Construction
# ──────────────────────────────────────────────────────────────
def build_categorical_mappings(df: pd.DataFrame) -> tuple[dict, dict, dict]:
    """
    Build player_id → name / team / position dicts.
    Replicate the pickle structures from the original repository.
    """
    player_id2name = dict(zip(df["PLAYER_ID"], df["PLAYER_NAME"]))

    # Team abbreviation → integer (LabelEncoder style)
    teams = sorted(df["TEAM_ABBREVIATION"].dropna().unique())
    team2int = {t: i for i, t in enumerate(teams)}
    player_id2team = {
        pid: grp["TEAM_ABBREVIATION"].mode()[0]
        for pid, grp in df.groupby("PLAYER_ID")
        if "TEAM_ABBREVIATION" in grp.columns
    }
    player_id2team_int = {k: team2int.get(v, 0) for k, v in player_id2team.items()}

    # Position (not available in box score – we'll map using nba_api static data)
    try:
        from nba_api.stats.static import players as nba_players
        static = {p["id"]: p for p in nba_players.get_players()}
        # Positions available: 'Guard', 'Forward', 'Center', 'Forward-Guard', etc.
        pos_map = {"G": [0, 1, 0], "F": [1, 0, 0], "C": [0, 0, 1],
                   "F-G": [1, 1, 0], "F-C": [1, 0, 1], "G-F": [1, 1, 0]}
        def encode_pos(pid):
            info = static.get(pid, {})
            pos_str = info.get("position", "") or ""
            key = pos_str.replace(" ", "-")[:3]
            return pos_map.get(key, [0, 0, 0])
    except Exception:
        def encode_pos(_pid):
            return [0, 0, 0]

    player_ids = list(player_id2name.keys())
    player_id2position = {pid: np.array(encode_pos(pid)) for pid in player_ids}

    return player_id2name, player_id2team_int, player_id2position


def preprocess(df: pd.DataFrame) -> tuple[np.ndarray, list, list]:
    """
    Build:
      X_seq – (days, players, 13)  feature tensor (forward-filled, z-score normalised)
      G_seq – list of networkx graphs (one per game-day)
      game_dates – sorted list of date strings
    """
    # Ensure we have all feature columns; fill missing with 0
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = 0.0

    # Need a proper game date column
    # The GAME_ID encodes the date: first 3 chars = season code (e.g. "002"), next 8 = YYYYMMDD
    if "GAME_DATE" not in df.columns:
        df["GAME_DATE"] = pd.to_datetime(
            df["GAME_ID"].astype(str).str[3:11], format="%Y%m%d", errors="coerce"
        )

    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
    df = df.sort_values("GAME_DATE")

    # Build universe of players (sorted by player_id for reproducibility)
    player_ids = sorted(df["PLAYER_ID"].unique())
    player_index = {pid: i for i, pid in enumerate(player_ids)}
    N = len(player_ids)
    log.info(f"Player universe size: {N}")

    # Build chronological day sequence
    game_dates = sorted(df["GAME_DATE"].dt.date.unique())
    D = len(game_dates)
    log.info(f"Game days: {D}")

    # Raw feature tensor: (D, N, 13)  – 0 where player didn't play
    X_raw = np.zeros((D, N, len(FEATURE_COLS)), dtype=np.float32)
    G_raw: list[nx.Graph] = []

    for d_idx, gdate in enumerate(game_dates):
        day_df = df[df["GAME_DATE"].dt.date == gdate]
        G = nx.Graph()
        G.add_nodes_from(player_ids)  # all players always present in graph

        # Populate feature rows and edges
        for game_id, game_grp in day_df.groupby("GAME_ID"):
            active_players = game_grp["PLAYER_ID"].tolist()
            for pid in active_players:
                if pid in player_index:
                    row = game_grp[game_grp["PLAYER_ID"] == pid].iloc[0]
                    feat = [float(row.get(c, 0) or 0) for c in FEATURE_COLS]
                    X_raw[d_idx, player_index[pid], :] = feat

            # Complete bipartite graph for players in same game
            for pA, pB in itertools.combinations(active_players, 2):
                if pA in player_index and pB in player_index:
                    G.add_edge(pA, pB)

        G_raw.append(G)

    # ── Forward-fill (impute temporal sparsity) ──────────────────
    X_ffill = np.zeros_like(X_raw)
    for p in range(N):
        for f in range(len(FEATURE_COLS)):
            arr = X_raw[:, p, f]
            prev = np.arange(len(arr))
            prev[arr == 0] = 0
            prev = np.maximum.accumulate(prev)
            X_ffill[:, p, f] = arr[prev]

    # ── Z-score normalisation per feature ───────────────────────
    means = X_ffill.mean(axis=(0, 1), keepdims=True)
    stds  = X_ffill.std(axis=(0, 1), keepdims=True) + 1e-8
    X_norm = (X_ffill - means) / stds

    log.info(f"X_seq shape: {X_norm.shape}")
    return X_norm, G_raw, [str(d) for d in game_dates], player_ids


# ──────────────────────────────────────────────────────────────
# Save artefacts
# ──────────────────────────────────────────────────────────────
def save_artefacts(X_seq, G_seq, game_dates, player_ids,
                   player_id2name, player_id2team, player_id2position):
    with open(f"{OUTPUT_DIR}/X_seq.pkl", "wb") as f:
        pickle.dump(X_seq, f)
    with open(f"{OUTPUT_DIR}/G_seq.pkl", "wb") as f:
        pickle.dump(G_seq, f)
    with open(f"{OUTPUT_DIR}/game_dates.pkl", "wb") as f:
        pickle.dump(game_dates, f)
    with open(f"{OUTPUT_DIR}/player_ids.pkl", "wb") as f:
        pickle.dump(player_ids, f)
    with open(f"{OUTPUT_DIR}/player_id2name.pkl", "wb") as f:
        pickle.dump(player_id2name, f)
    with open(f"{OUTPUT_DIR}/player_id2team.pkl", "wb") as f:
        pickle.dump(player_id2team, f)
    with open(f"{OUTPUT_DIR}/player_id2position.pkl", "wb") as f:
        pickle.dump(player_id2position, f)
    log.info("All artefacts saved to ./data/")


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    raw_df_path = f"{OUTPUT_DIR}/raw_boxscores.parquet"

    if os.path.exists(raw_df_path):
        log.info(f"Loading cached raw data from {raw_df_path}")
        raw_df = pd.read_parquet(raw_df_path)
    else:
        log.info("Starting data acquisition (this may take several hours)…")
        raw_df = acquire_data()
        raw_df.to_parquet(raw_df_path, index=False)
        log.info(f"Raw data saved to {raw_df_path}")

    log.info("Preprocessing…")
    X_seq, G_seq, game_dates, player_ids = preprocess(raw_df)

    log.info("Building categorical mappings…")
    player_id2name, player_id2team, player_id2position = build_categorical_mappings(raw_df)

    log.info("Saving artefacts…")
    save_artefacts(X_seq, G_seq, game_dates, player_ids,
                   player_id2name, player_id2team, player_id2position)

    log.info("Data pipeline complete ✓")
