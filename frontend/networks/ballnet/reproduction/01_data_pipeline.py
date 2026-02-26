"""
Phase 1 & 2: Data Acquisition and Preprocessing Pipeline
=========================================================
Comprehensive NBA data scraper for the GATv2-GCN reproduction.
"""

import os
import sys
import time
import pickle
import logging
import itertools
import requests 
import random
from datetime import datetime, date

import numpy as np
import pandas as pd
import networkx as nx
from nba_api.stats.endpoints import (
    leaguegamelog,  
    boxscoretraditionalv3,
    boxscoreadvancedv3,
    boxscoreplayertrackv3,
)
from nba_api.library import http as nba_http

# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

OUTPUT_DIR = "data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

SEASONS = [
    ("2022-23", "2022-10-18", "2023-04-09"),
    ("2023-24", "2023-10-24", "2024-04-14"),
    ("2024-25", "2024-10-22", "2025-04-13"),
    ("2025-26", "2025-10-28", str(date.today())),
]

TRAD_COLS   = ["GAME_ID", "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_ABBREVIATION",
               "MIN", "PTS", "AST", "REB", "TO", "STL", "BLK", "PLUS_MINUS"]
ADV_COLS    = ["GAME_ID", "PLAYER_ID", "PACE", "USG_PCT", "TS_PCT"]
TRACK_COLS  = ["GAME_ID", "PLAYER_ID", "DIST", "TCHS", "PASS"]
FEATURE_COLS = ["PTS", "AST", "REB", "TO", "STL", "BLK", "PLUS_MINUS",
                "TCHS", "PASS", "DIST", "PACE", "USG_PCT", "TS_PCT"]
MIN_MINUTES = 10.0
API_DELAY = 2.5   

BASE_HEADERS = {
    'Host': 'stats.nba.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://www.nba.com/',
    'Connection': 'close',
    'Origin': 'https://www.nba.com',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
}

# ──────────────────────────────────────────────────────────────
# Session Management
# ──────────────────────────────────────────────────────────────
def reset_nba_session():
    """Creates a fresh session and actively prevents connection pooling."""
    session = requests.Session()
    session.headers.update(BASE_HEADERS)
    
    # Force urllib3 to destroy sockets immediately after use
    adapter = requests.adapters.HTTPAdapter(pool_connections=0, pool_maxsize=0, max_retries=0)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    nba_http.requests_session = session
    return session

# Initialize
current_session = reset_nba_session()

def call_api_with_retry(endpoint_class, *args, max_retries=6, **kwargs):
    global current_session
    kwargs.setdefault('timeout', (10, 15)) 
    
    for attempt in range(max_retries):
        try:
            return endpoint_class(*args, **kwargs).get_data_frames()[0]
        except (requests.exceptions.ReadTimeout, requests.exceptions.RequestException) as exc:
            if attempt == max_retries - 1:
                log.error(f"Max retries reached. Final error: {exc}")
                raise exc
            
            # Tarpit logic
            if "Read timed out" in str(exc) and attempt >= 4:
                log.warning("Tarpit detected. Resetting Session + 10m Deep Sleep...")
                current_session.close()
                current_session = reset_nba_session()
                time.sleep(600) 
            else:
                wait_time = (API_DELAY * (1.5 ** attempt)) + np.random.uniform(2, 8)
                log.warning(f"API call failed ({type(exc).__name__}), retrying in {wait_time:.2f}s...")
                time.sleep(wait_time)

# ──────────────────────────────────────────────────────────────
# Data Fetching Helpers (Restored your original logic)
# ──────────────────────────────────────────────────────────────
def get_game_ids(season: str, date_from: str, date_to: str) -> dict:
    try:
        time.sleep(API_DELAY + np.random.uniform(1, 5))
        df = call_api_with_retry(leaguegamelog.LeagueGameLog, season=season, league_id='00', season_type_all_star="Regular Season")
        df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
        mask = (df["GAME_DATE"] >= pd.to_datetime(date_from)) & (df["GAME_DATE"] <= pd.to_datetime(date_to))
        filtered = df.loc[mask]
        return filtered.set_index("GAME_ID")["GAME_DATE"].dt.strftime("%Y-%m-%d").to_dict()
    except Exception as exc:
        log.error(f"LeagueGameLog failed for {season}: {exc}")
        return {}

def fetch_game_stats(game_id: str) -> pd.DataFrame | None:
    try:
        time.sleep(np.random.uniform(2.0, 4.0)) 
        df_trad = call_api_with_retry(boxscoretraditionalv3.BoxScoreTraditionalV3, game_id=game_id)
        time.sleep(np.random.uniform(1.5, 2.5))
        df_adv = call_api_with_retry(boxscoreadvancedv3.BoxScoreAdvancedV3, game_id=game_id)
        time.sleep(np.random.uniform(1.5, 2.5))
        df_track = call_api_with_retry(boxscoreplayertrackv3.BoxScorePlayerTrackV3, game_id=game_id)
    except Exception as exc:
        log.warning(f"    Game {game_id} skipped – API error: {exc}")
        return None
    
    # 1. Traditional
    trad_map = {"gameId": "GAME_ID", "personId": "PLAYER_ID", "teamId": "TEAM_ID", "teamTricode": "TEAM_ABBREVIATION", "minutes": "MIN", "points": "PTS", "assists": "AST", "reboundsTotal": "REB", "turnovers": "TO", "steals": "STL", "blocks": "BLK", "plusMinusPoints": "PLUS_MINUS"}
    df_trad = df_trad.rename(columns=trad_map)
    if "firstName" in df_trad.columns and "familyName" in df_trad.columns:
        df_trad["PLAYER_NAME"] = (df_trad["firstName"].fillna("") + " " + df_trad["familyName"].fillna("")).str.strip()
    
    # 2. Advanced
    adv_map = {"gameId": "GAME_ID", "personId": "PLAYER_ID", "pace": "PACE", "usagePercentage": "USG_PCT", "trueShootingPercentage": "TS_PCT"}
    df_adv = df_adv.rename(columns=adv_map)

    # 3. Tracking (using your robust variant-loop)
    df_track.columns = df_track.columns.str.upper()
    df_track = df_track.rename(columns={"GAMEID": "GAME_ID", "PERSONID": "PLAYER_ID"})
    track_col_map = {}
    for wanted, variants in [("DIST", ["DIST", "DISTANCE"]), ("TCHS", ["TCHS", "TOUCHES"]), ("PASS", ["PASS", "PASSES"])]:
        for v in variants:
            if v in df_track.columns:
                track_col_map[v] = wanted
                break
    df_track = df_track.rename(columns=track_col_map)

    # Merge
    available_trad = [c for c in TRAD_COLS if c in df_trad.columns]
    available_adv  = [c for c in ADV_COLS  if c in df_adv.columns]
    available_track = ["GAME_ID", "PLAYER_ID"] + [c for c in ["DIST", "TCHS", "PASS"] if c in df_track.columns]

    df = (df_trad[available_trad]
          .merge(df_adv[available_adv],   on=["GAME_ID", "PLAYER_ID"], how="left")
          .merge(df_track[available_track], on=["GAME_ID", "PLAYER_ID"], how="left"))

    def parse_min(m):
        if pd.isna(m) or str(m).strip() == "": return 0.0
        if ":" in str(m):
            p = str(m).split(":")
            return float(p[0]) + (float(p[1]) / 60)
        return float(m)
    
    df["MIN"] = df["MIN"].apply(parse_min)
    return df[df["MIN"] >= MIN_MINUTES].copy()

# ──────────────────────────────────────────────────────────────
# Acquisition Loop
# ──────────────────────────────────────────────────────────────
def acquire_data() -> pd.DataFrame:
    global current_session
    raw_df_path = f"{OUTPUT_DIR}/raw_boxscores.parquet"
    
    if os.path.exists(raw_df_path):
        all_frames = [pd.read_parquet(raw_df_path)]
        processed_ids = set(all_frames[0]["GAME_ID"].unique())
        log.info(f"Resuming: Found {len(processed_ids)} games already in cache.")
    else:
        all_frames, processed_ids = [], set()

    games_processed_this_run = 0  # Initialize the kamikaze counter
    MAX_GAMES_PER_RUN = 199       # Threshold to trigger script reset

    for season, date_from, date_to in SEASONS:
        log.info(f"Season: {season} ({date_from} → {date_to})")
        game_map = get_game_ids(season, date_from, date_to)
        new_ids = [gid for gid in game_map.keys() if gid not in processed_ids]
        log.info(f"  {len(new_ids)} games to fetch.")

        for idx, gid in enumerate(new_ids):
            log.info(f"  [{idx+1}/{len(new_ids)}] Fetching game {gid}")
            df_game = fetch_game_stats(gid)
            if df_game is not None:
                df_game["SEASON"], df_game["GAME_DATE"] = season, game_map[gid]
                all_frames.append(df_game)
                processed_ids.add(gid)
            
            if (idx + 1) % 25 == 0:
                pd.concat(all_frames, ignore_index=True).to_parquet(raw_df_path, index=False)
                log.info("--- CHECKPOINT: Session Reset + 2 min pause ---")
                current_session.close()
                current_session = reset_nba_session()
                time.sleep(120)

            games_processed_this_run += 1
            
            if games_processed_this_run >= MAX_GAMES_PER_RUN:
                log.info(f"Reached {MAX_GAMES_PER_RUN} games. Committing Kamikaze protocol to clear TLS cache.")
                # Save the parquet file one last time before dying
                combined = pd.concat(all_frames, ignore_index=True)
                combined.to_parquet(raw_df_path, index=False)
                
                # Exit with a specific status code so the master script knows it was intentional
                sys.exit(42)

    combined = pd.concat(all_frames, ignore_index=True)
    combined.to_parquet(raw_df_path, index=False)
    return combined

def build_categorical_mappings(df: pd.DataFrame) -> tuple[dict, dict, dict]:
    player_id2name = dict(zip(df["PLAYER_ID"], df["PLAYER_NAME"]))
    teams = sorted(df["TEAM_ABBREVIATION"].dropna().unique())
    team2int = {t: i for i, t in enumerate(teams)}
    player_id2team = {pid: grp["TEAM_ABBREVIATION"].mode()[0] for pid, grp in df.groupby("PLAYER_ID") if "TEAM_ABBREVIATION" in grp.columns}
    player_id2team_int = {k: team2int.get(v, 0) for k, v in player_id2team.items()}
    from nba_api.stats.static import players as nba_players
    static = {p["id"]: p for p in nba_players.get_players()}
    pos_map = {"G": [0, 1, 0], "F": [1, 0, 0], "C": [0, 0, 1], "F-G": [1, 1, 0], "F-C": [1, 0, 1], "G-F": [1, 1, 0]}
    def encode_pos(pid):
        pos_str = static.get(pid, {}).get("position", "") or ""
        return pos_map.get(pos_str.replace(" ", "-")[:3], [0, 0, 0])
    player_id2position = {pid: np.array(encode_pos(pid)) for pid in player_id2name.keys()}
    return player_id2name, player_id2team_int, player_id2position

def preprocess(df: pd.DataFrame) -> tuple[np.ndarray, list, list, list]:
    for col in FEATURE_COLS:
        if col not in df.columns: df[col] = 0.0
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
    df = df.sort_values("GAME_DATE")
    player_ids = sorted(df["PLAYER_ID"].unique())
    player_index = {pid: i for i, pid in enumerate(player_ids)}
    game_dates = sorted(df["GAME_DATE"].dt.date.unique())
    X_raw = np.zeros((len(game_dates), len(player_ids), len(FEATURE_COLS)), dtype=np.float32)
    G_raw = []
    for d_idx, gdate in enumerate(game_dates):
        day_df = df[df["GAME_DATE"].dt.date == gdate]
        G = nx.Graph()
        G.add_nodes_from(player_ids)
        for game_id, game_grp in day_df.groupby("GAME_ID"):
            active = game_grp["PLAYER_ID"].tolist()
            for pid in active:
                if pid in player_index:
                    row = game_grp[game_grp["PLAYER_ID"] == pid].iloc[0]
                    X_raw[d_idx, player_index[pid], :] = [float(row.get(c, 0) or 0) for c in FEATURE_COLS]
            for pA, pB in itertools.combinations(active, 2):
                if pA in player_index and pB in player_index: G.add_edge(pA, pB)
        G_raw.append(G)
    return X_raw, G_raw, [str(d) for d in game_dates], player_ids

def save_artefacts(X_seq, G_seq, game_dates, player_ids, p2n, p2t, p2p):
    for name, obj in [("X_seq", X_seq), ("G_seq", G_seq), ("game_dates", game_dates), ("player_ids", player_ids), ("player_id2name", p2n), ("player_id2team", p2t), ("player_id2position", p2p)]:
        with open(f"{OUTPUT_DIR}/{name}.pkl", "wb") as f: pickle.dump(obj, f)
    log.info("All artefacts saved.")

if __name__ == "__main__":
    raw_df = acquire_data()
    X, G, dates, pids = preprocess(raw_df)
    mappings = build_categorical_mappings(raw_df)
    save_artefacts(X, G, dates, pids, *mappings)
    log.info("Data pipeline complete ✓")