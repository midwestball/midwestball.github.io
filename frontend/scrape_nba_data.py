import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

def get_player_data(player_name, season='2023-24'):
    """
    Scrapes player data from Basketball Reference for a given player and season.
    """
    # Format player name for URL
    player_name = player_name.lower().replace(" ", "")
    
    # Build the URL for the player's page
    # get the player's code
    code = player_name[0].lower() + "/" + player_name[:5].lower() + player_name[-2:].lower() + "01"
    url = f"https://www.basketball-reference.com/players/{code}/gamelog/{season}"
    print(f"Fetching data for: {url}")
    
    # Request the page
    response = requests.get(url)
    
    if response.status_code != 200:
        raise Exception(f"Failed to fetch data for {player_name} from Basketball Reference")
    
    # Parse the page with BeautifulSoup
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find the player's game log table
    game_log_table = soup.find('table', {'id': 'pgl_basic'})
    if not game_log_table:
        raise Exception(f"Game log table not found for player {player_name}")
    
    # Parse the game log data into a pandas DataFrame
    rows = game_log_table.find_all('tr')[1:]  # Skip the header row
    data = []
    for row in rows:
        cols = row.find_all('td')
        if len(cols) > 0:
            game_data = {
                'game_date': datetime.strptime(cols[0].text, '%Y-%m-%d'),
                'points': int(cols[2].text),
                'minutes': int(cols[3].text),
                'is_home': 'vs.' in cols[1].text,
                'opponent': cols[1].text.strip(),
            }
            data.append(game_data)
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Calculate additional stats
    df['days_into_season'] = (df['game_date'] - df['game_date'].min()).dt.days
    df['points_ma'] = df['points'].rolling(5, min_periods=1).mean()
    df['minutes_played_ma'] = df['minutes'].rolling(5, min_periods=1).mean()
    
    # Calculate rest days
    df['days_rest'] = df['game_date'].diff().dt.days
    df['back_to_back'] = df['days_rest'] == 1
    
    # Calculate season averages
    df['season_avg_points'] = df['points'].expanding().mean()
    
    # Remove the first few games for better analysis (optional)
    df = df.iloc[:-4]
    
    return df

# Example usage
player_data = get_player_data('Stephen Curry')
print(player_data)