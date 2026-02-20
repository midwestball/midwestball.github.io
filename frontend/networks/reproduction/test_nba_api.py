import time
from nba_api.stats.endpoints import leaguegamefinder
from nba_api.stats.endpoints import boxscoretraditionalv3

custom_headers = {
    'Host': 'stats.nba.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

try:
    print("Testing LeagueGameFinder...")
    gf = leaguegamefinder.LeagueGameFinder(
        season_nullable="2022-23",
        season_type_nullable="Regular Season",
        league_id_nullable="00",
        timeout=60
    )
    df = gf.get_data_frames()[0]
    print(df.head())
    print("LeagueGameFinder success")
except Exception as e:
    print(f"LeagueGameFinder error: {e}")

try:
    print("Testing BoxScoreTraditionalV3...")
    trad = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id="0022500009", timeout=10)
    df_trad = trad.get_data_frames()[0]
    print(list(df_trad.keys()) if isinstance(df_trad, dict) else df_trad.columns)
    print("BoxScoreTraditionalV3 success")
except Exception as e:
    print(f"BoxScoreTraditionalV3 error: {e}")
