import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from datetime import datetime
import time

def get_player_url(player_name):
    """Convert player name to Basketball Reference URL format."""
    # Format: First 5 letters of last name + first 2 of first name + 01.html
    # Example: Stephen Curry -> curryst01.html
    names = player_name.lower().split()
    last_name = names[-1][:5]
    first_name = names[0][:2]
    return f"{last_name}{first_name}01"

def get_player_data(player_name, season='2023-24'):
    # Convert season format (e.g., '2023-24' to '2024')
    season_year = season.split('-')[1]
    if len(season_year) == 2:
        season_year = '20' + season_year
    
    # Construct URL
    player_url = get_player_url(player_name)
    url = f"https://www.basketball-reference.com/players/{player_url[0]}/{player_url}/gamelog/{season_year}"
    print(f"Scraping URL: {url}")
    
    # Add headers to mimic browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # Make request
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find the game log table
    table = soup.find('table', id='pgl_basic')
    if not table:
        raise ValueError(f"Could not find game log for {player_name}")
    
    # Get column headers first
    headers = []
    header_row = table.find('thead').find('tr')
    for th in header_row.find_all('th'):
        headers.append(th.get('data-stat', th.text.strip()))
    
    # Extract rows
    rows = []
    for row in table.find('tbody').find_all('tr'):
        if 'thead' not in row.get('class', []):  # Skip header rows
            cols = row.find_all(['td', 'th'])
            if cols:  # Skip empty rows
                row_data = [col.text.strip() for col in cols]
                rows.append(row_data)
    
    # Convert to DataFrame
    df = pd.DataFrame(rows, columns=headers[:len(rows[0]) if rows else len(headers)])
    
    # Process into required features
    processed_df = pd.DataFrame()
    
    # Basic game info - use correct column names from Basketball Reference
    processed_df['game_date'] = pd.to_datetime(df['date_game'])
    processed_df['days_into_season'] = (processed_df['game_date'] - processed_df['game_date'].min()).dt.days
    processed_df['points'] = pd.to_numeric(df['pts'], errors='coerce')
    processed_df['minutes'] = pd.to_numeric(df['mp'].str.split(':').str[0], errors='coerce')
    processed_df['is_home'] = ~df['game_location'].str.contains('@', na=False)
    
    # Calculate rolling averages
    processed_df['points_ma'] = processed_df['points'].rolling(5, min_periods=1).mean()
    processed_df['minutes_played_ma'] = processed_df['minutes'].rolling(5, min_periods=1).mean()
    
    # Calculate rest days and back-to-backs
    processed_df['days_rest'] = processed_df['game_date'].diff().dt.days
    processed_df['back_to_back'] = processed_df['days_rest'] == 1
    
    # Season averages
    processed_df['season_avg_points'] = processed_df['points'].expanding().mean()
    
    # Last 5 games points
    processed_df['last_5_games_points'] = [
        processed_df['points'].iloc[i:min(i + 5, len(processed_df))].tolist()[::-1] 
        for i in range(len(processed_df))
    ]
    
    # Drop first 4 games
    processed_df = processed_df.iloc[:-4]
    
    # Add delay to be respectful to the website
    time.sleep(1)
    
    return processed_df

# Example usage:
# player_data = get_player_data('Stephen Curry')
# print("\nProcessed data:")
# print(player_data)