import os
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

def run_tests():
    file_path = "data/raw_boxscores.parquet"
    
    if not os.path.exists(file_path):
        log.error(f"❌ File not found: {file_path}")
        return

    log.info("Loading parquet file...")
    df = pd.read_parquet(file_path)
    
    log.info(f"\n{'='*40}")
    log.info("DATASET OVERVIEW")
    log.info(f"{'='*40}")
    log.info(f"Total Rows: {len(df)}")
    
    # 1. Check Unique Games
    unique_games = df['GAME_ID'].nunique()
    log.info(f"Unique Games Fetched: {unique_games}")
    if unique_games == 50:
        log.info("✅ Game count perfectly matches the expected 50.")
    else:
        log.warning(f"⚠️ Expected 50 games, but found {unique_games}.")

    # 2. Check Required Columns
    expected_cols = [
        "GAME_ID", "PLAYER_ID", "PLAYER_NAME", "TEAM_ABBREVIATION", "MIN", 
        "PTS", "AST", "REB", "TO", "STL", "BLK", "PLUS_MINUS", 
        "PACE", "USG_PCT", "TS_PCT", "DIST", "TCHS", "PASS", 
        "SEASON", "GAME_DATE"
    ]
    
    missing_cols = [col for col in expected_cols if col not in df.columns]
    if missing_cols:
        log.error(f"❌ Missing expected columns: {missing_cols}")
    else:
        log.info("✅ All required columns (Traditional, Advanced, Tracking, and Meta) are present.")

    # 3. Validate the MIN threshold parser
    min_check = df[df["MIN"] < 10.0]
    if len(min_check) > 0:
        log.error(f"❌ Found {len(min_check)} rows with less than 10.0 minutes. The filter failed.")
    else:
        log.info("✅ Minutes filter works perfectly. All players have >= 10.0 minutes.")

    # 4. Check for Nulls in Feature Columns
    feature_cols = ["PTS", "AST", "REB", "TO", "STL", "BLK", "PLUS_MINUS",
                    "TCHS", "PASS", "DIST", "PACE", "USG_PCT", "TS_PCT"]
    
    null_counts = df[feature_cols].isnull().sum()
    cols_with_nulls = null_counts[null_counts > 0]
    
    if not cols_with_nulls.empty:
        log.warning("\n⚠️ Found NULL values in the following feature columns:")
        for col, count in cols_with_nulls.items():
            log.warning(f"  - {col}: {count} missing values")
        log.info("  (Note: Minor missing tracking data is common for older games, Phase 3 handles this by filling with 0.0)")
    else:
        log.info("✅ No null values found in any of the feature columns.")

    # 5. Preview the first few rows of output features
    log.info(f"\n{'='*40}")
    log.info("DATA PREVIEW (First 3 Players)")
    log.info(f"{'='*40}")
    preview_cols = ["PLAYER_NAME", "GAME_DATE", "MIN", "PTS", "REB", "AST", "USG_PCT", "DIST"]
    available_preview = [c for c in preview_cols if c in df.columns]
    print(df[available_preview].head(3).to_string(index=False))

    # 6. Checking for a specific game
    # Does game 0022200227 exist?
    game_check = df[df["GAME_ID"] == "0022200227"]
    if len(game_check) > 0:
        log.info("✅ Game 0022200227 exists.")
    else:
        log.error("❌ Game 0022200227 does not exist.")

if __name__ == "__main__":
    run_tests()