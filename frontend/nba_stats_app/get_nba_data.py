from nba_api.stats.endpoints import PlayerGameLogs
from nba_api.stats.static import players
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

def get_player_data(player_name, season='2023-24'):
    # Get player ID
    player_dict = players.find_players_by_full_name(player_name)[0]
    player_id = player_dict['id']
    print(f"Player ID: {player_id}")
    
    # Get game logs
    game_logs = PlayerGameLogs(player_id_nullable=player_id, season_nullable=season).get_data_frames()[0]
    
    # Process into required features
    df = pd.DataFrame()
    
    # Basic game info
    df['game_date'] = pd.to_datetime(game_logs['GAME_DATE'])
    # turn 'game_date' into 'days_into_season'
    df['days_into_season'] = (df['game_date'] - df['game_date'].min()).dt.days
    df['points'] = game_logs['PTS']
    df['minutes'] = game_logs['MIN']
    df['is_home'] = game_logs['MATCHUP'].str.contains('vs.')
    
    # Calculate rolling averages
    df['points_ma'] = df['points'].rolling(5, min_periods=1).mean()
    df['minutes_played_ma'] = df['minutes'].rolling(5, min_periods=1).mean()
    
    # Calculate rest days and back-to-backs
    df['days_rest'] = df['game_date'].diff().dt.days
    df['back_to_back'] = df['days_rest'] == 1
    
    # Season averages
    df['season_avg_points'] = df['points'].expanding().mean()
    
    # Last 5 games points (as a list) the last row is the first game, and the first row is the last game
    df['last_5_games_points'] = [
        df['points'].iloc[i:min(i + 5, len(df))].tolist()[::-1] for i in range(len(df))
    ]

    # drop first 4 games
    df = df.iloc[:-4]

    return df

# Example usage
# player_data = get_player_data('Stephen Curry')
# print(player_data)