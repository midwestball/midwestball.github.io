"""
Phase 1 & 2: Data Acquisition Pipeline (Maximized Data Extraction)
==================================================================
Extracts COMPLETE boxscore metrics, PASSING NETWORKS, and PLAY-BY-PLAY with on-court players.
"""

import os
import sys
import time
import logging
import requests 
import numpy as np
import pandas as pd
from datetime import date

import nba_on_court as noc  # NEW: Parser for the 10 players on the floor

from nba_api.stats.endpoints import (
    leaguegamelog,  
    boxscoretraditionalv3,
    boxscoreadvancedv3,
    boxscoreplayertrackv3,
    teamdashptpass,
    playbyplayv2  # NEW: Play-by-play endpoint
)
from nba_api.library import http as nba_http

# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

OUTPUT_DIR = "pass_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

SEASONS = [
    ("2022-23", "2022-10-18", "2023-04-09"),
    ("2023-24", "2023-10-24", "2024-04-14"),
    ("2024-25", "2024-10-22", "2025-04-13"),
]

API_DELAY = 2.5   

BASE_HEADERS = {
    'Host': 'stats.nba.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://www.nba.com/',
    'Origin': 'https://www.nba.com',
}

# ──────────────────────────────────────────────────────────────
# Session Management
# ──────────────────────────────────────────────────────────────
def reset_nba_session():
    session = requests.Session()
    session.headers.update(BASE_HEADERS)
    nba_http.requests_session = session
    return session

current_session = reset_nba_session()

def call_api_with_retry(endpoint_class, *args, max_retries=6, **kwargs):
    global current_session
    kwargs.setdefault('timeout', 15)
    
    for attempt in range(max_retries):
        try:
            return endpoint_class(*args, **kwargs).get_data_frames()[0]
        except (requests.exceptions.ReadTimeout, requests.exceptions.RequestException) as exc:
            if attempt == max_retries - 1:
                log.error(f"Max retries reached. Final error: {exc}")
                raise exc
            
            if "Read timed out" in str(exc) and attempt >= 4:
                log.warning("Tarpit detected. Resetting Session + 10m Deep Sleep...")
                current_session.close()
                current_session = reset_nba_session()
                time.sleep(600) 
            else:
                wait_time = (API_DELAY * (1.5 ** attempt)) + np.random.uniform(2, 8)
                log.warning(f"API call failed, retrying in {wait_time:.2f}s...")
                time.sleep(wait_time)

# ──────────────────────────────────────────────────────────────
# Data Fetching Logic
# ──────────────────────────────────────────────────────────────
def get_game_schedule(season: str, date_from: str, date_to: str) -> dict:
    try:
        time.sleep(API_DELAY + np.random.uniform(1, 5))
        df = call_api_with_retry(leaguegamelog.LeagueGameLog, season=season, league_id='00', season_type_all_star="Regular Season")
        df["GAME_DATE_DT"] = pd.to_datetime(df["GAME_DATE"])
        mask = (df["GAME_DATE_DT"] >= pd.to_datetime(date_from)) & (df["GAME_DATE_DT"] <= pd.to_datetime(date_to))
        df = df.loc[mask]
        
        schedule = {}
        for gid, grp in df.groupby("GAME_ID"):
            date_dt = grp["GAME_DATE_DT"].iloc[0]
            schedule[gid] = {
                "DATE_MDY": date_dt.strftime("%m/%d/%Y"),
                "SEASON": season,
                "TEAM_IDS": grp["TEAM_ID"].unique().tolist()
            }
        return schedule
    except Exception as exc:
        log.error(f"LeagueGameLog failed: {exc}")
        return {}

def fetch_full_boxscore(game_id: str) -> pd.DataFrame | None:
    try:
        time.sleep(np.random.uniform(2.0, 4.0)) 
        df_trad = call_api_with_retry(boxscoretraditionalv3.BoxScoreTraditionalV3, game_id=game_id)
        time.sleep(np.random.uniform(1.5, 2.5))
        df_adv = call_api_with_retry(boxscoreadvancedv3.BoxScoreAdvancedV3, game_id=game_id)
        time.sleep(np.random.uniform(1.5, 2.5))
        df_track = call_api_with_retry(boxscoreplayertrackv3.BoxScorePlayerTrackV3, game_id=game_id)
    except Exception as exc:
        log.warning(f"  Game {game_id} boxscore skipped: {exc}")
        return None
    
    for df in [df_trad, df_adv, df_track]:
        df.columns = df.columns.str.upper()
        
    rename_map = {"GAMEID": "GAME_ID", "PERSONID": "PLAYER_ID", "TEAMID": "TEAM_ID"}
    df_trad = df_trad.rename(columns=rename_map)
    df_adv = df_adv.rename(columns=rename_map)
    df_track = df_track.rename(columns=rename_map)

    df_merged = df_trad.merge(df_adv, on=["GAME_ID", "PLAYER_ID", "TEAM_ID"], how="outer", suffixes=("", "_ADV"))
    df_merged = df_merged.merge(df_track, on=["GAME_ID", "PLAYER_ID", "TEAM_ID"], how="outer", suffixes=("", "_TRACK"))
    
    return df_merged

def fetch_pass_network(team_id: str, season: str, game_date_mdy: str, game_id: str) -> pd.DataFrame | None:
    try:
        time.sleep(np.random.uniform(2.0, 4.0))
        df_passes = call_api_with_retry(
            teamdashptpass.TeamDashPtPass,
            team_id=team_id,
            season=season,
            date_from_nullable=game_date_mdy,
            date_to_nullable=game_date_mdy
        )
        if df_passes is not None and not df_passes.empty:
            df_passes["GAME_ID"] = game_id 
            df_passes["GAME_DATE"] = game_date_mdy
            return df_passes
    except Exception as exc:
        log.warning(f"  Pass Network failed for Team {team_id}: {exc}")
    return None

def fetch_play_by_play(game_id: str) -> pd.DataFrame | None:
    """Fetches chronological play-by-play and calculates the 10 players on the court."""
    try:
        time.sleep(np.random.uniform(2.0, 4.0))
        # Use PlayByPlayV2 to ensure compatibility with nba_on_court
        df_pbp = call_api_with_retry(playbyplayv2.PlayByPlayV2, game_id=game_id)
        
        if df_pbp is not None and not df_pbp.empty:
            # nba_on_court automatically calculates substitutions and appends 10 new columns
            df_pbp_with_players = noc.players_on_court(df_pbp)
            df_pbp_with_players["GAME_ID"] = game_id  
            return df_pbp_with_players
    except Exception as exc:
        log.warning(f"  Play-by-play parsing failed for Game {game_id}: {exc}")
        return None

# ──────────────────────────────────────────────────────────────
# Acquisition Loop
# ──────────────────────────────────────────────────────────────
def save_checkpoint(new_boxes, new_passes, new_pbp, box_path, pass_path, pbp_path):
    if new_boxes:
        df_new_box = pd.concat(new_boxes, ignore_index=True)
        if os.path.exists(box_path):
            df_new_box = pd.concat([pd.read_parquet(box_path), df_new_box], ignore_index=True)
        df_new_box.to_parquet(box_path, index=False)
        new_boxes.clear() 

    if new_passes:
        df_new_pass = pd.concat(new_passes, ignore_index=True)
        if os.path.exists(pass_path):
            df_new_pass = pd.concat([pd.read_parquet(pass_path), df_new_pass], ignore_index=True)
        df_new_pass.to_parquet(pass_path, index=False)
        new_passes.clear()

    if new_pbp:
        df_new_pbp = pd.concat(new_pbp, ignore_index=True)
        if os.path.exists(pbp_path):
            df_new_pbp = pd.concat([pd.read_parquet(pbp_path), df_new_pbp], ignore_index=True)
        df_new_pbp.to_parquet(pbp_path, index=False)
        new_pbp.clear()


def acquire_data():
    global current_session
    boxscores_path = f"{OUTPUT_DIR}/full_boxscores.parquet"
    pass_nets_path = f"{OUTPUT_DIR}/pass_networks.parquet"
    pbp_path = f"{OUTPUT_DIR}/play_by_play.parquet"
    
    processed_gids = set()
    if os.path.exists(boxscores_path):
        df_existing = pd.read_parquet(boxscores_path)
        processed_gids = set(df_existing["GAME_ID"].unique())
        log.info(f"Resuming: {len(processed_gids)} games already in cache.")
        
    all_boxscores = []
    all_pass_nets = []
    all_play_by_play = []

    for season, date_from, date_to in SEASONS:
        log.info(f"Season: {season}")
        schedule = get_game_schedule(season, date_from, date_to)
        new_gids = [gid for gid in schedule.keys() if gid not in processed_gids]

        for idx, gid in enumerate(new_gids):
            log.info(f"  [{idx+1}/{len(new_gids)}] Fetching Game {gid}")
            
            # 1. Fetch Node Data
            df_game = fetch_full_boxscore(gid)
            if df_game is not None:
                df_game["SEASON"] = season
                df_game["GAME_DATE"] = schedule[gid]["DATE_MDY"]
                all_boxscores.append(df_game)
                
            # 2. Fetch Edge Data
            date_mdy = schedule[gid]["DATE_MDY"]
            for team_id in schedule[gid]["TEAM_IDS"]:
                df_edges = fetch_pass_network(team_id, season, date_mdy, gid)
                if df_edges is not None:
                    all_pass_nets.append(df_edges)

            # 3. Fetch Chronological Data (Play-by-Play + On Court Parser)
            df_pbp = fetch_play_by_play(gid)
            if df_pbp is not None:
                df_pbp["SEASON"] = season
                df_pbp["GAME_DATE"] = date_mdy
                all_play_by_play.append(df_pbp)
            
            # Tarpit Checkpoint
            if (idx + 1) % 25 == 0:
                log.info("--- CHECKPOINT: Session Reset + 2 min pause ---")
                save_checkpoint(all_boxscores, all_pass_nets, all_play_by_play, boxscores_path, pass_nets_path, pbp_path)
                current_session.close()
                current_session = reset_nba_session()
                time.sleep(120)

            # Kamikaze Protocol
            if (idx + 1) % 119 == 0:
                log.info(f"Reached 119 games. Committing Kamikaze protocol to clear TLS cache.")
                save_checkpoint(all_boxscores, all_pass_nets, all_play_by_play, boxscores_path, pass_nets_path, pbp_path)
                sys.exit(42)

    # Final Save 
    save_checkpoint(all_boxscores, all_pass_nets, all_play_by_play, boxscores_path, pass_nets_path, pbp_path)
    log.info("Data pipeline complete ✓")

if __name__ == "__main__":
    acquire_data()