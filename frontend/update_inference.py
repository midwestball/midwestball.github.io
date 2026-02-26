import re

with open('networks/ballnet/inference_v2.qmd', 'r') as f:
    content = f.read()

# 1. Update Phase 3 to get started games
s3_find = """todays_games = sb[0]
todays_teams = sb[1]
print(f'Games today ({today_str}): {len(todays_games)}')

teams_playing_today = set(todays_teams['TEAM_ABBREVIATION'].tolist())
print(f'Teams playing: {sorted(teams_playing_today)}')"""

s3_repl = """todays_games = sb[0]
todays_teams = sb[1]
print(f'Games today ({today_str}): {len(todays_games)}')

teams_playing_today = set(todays_teams['TEAM_ABBREVIATION'].tolist())
print(f'Teams playing: {sorted(teams_playing_today)}')

# Filter out live/finished games to prevent fetching live lines
started_gids = todays_games[todays_games['GAME_STATUS_ID'] > 1]['GAME_ID'].tolist()
started_team_abbrs = set(todays_teams[todays_teams['GAME_ID'].isin(started_gids)]['TEAM_ABBREVIATION'].tolist())
if started_team_abbrs:
    print(f'Already started games for: {sorted(started_team_abbrs)}')

name2pidx = {}
player_to_team = {}
for pid in player_ids:
    rows = (raw_df if not new_frames else raw_df_updated)[
        (raw_df if not new_frames else raw_df_updated)['PLAYER_ID'] == pid
    ]
    if len(rows):
        pname_norm = norm(rows.iloc[-1]['PLAYER_NAME'])
        name2pidx[pname_norm] = player_ids.index(pid)
        player_to_team[pname_norm] = rows.iloc[-1]['TEAM_ABBREVIATION']
"""

content = content.replace(s3_find, s3_repl)

# 2. Update Phase 4
s4_find = """name2pidx = {}
for pid in player_ids:
    rows = (raw_df if not new_frames else raw_df_updated)[
        (raw_df if not new_frames else raw_df_updated)['PLAYER_ID'] == pid
    ]
    if len(rows):
        name2pidx[norm(rows.iloc[0]['PLAYER_NAME'])] = player_ids.index(pid)

pregame_path = TRACKING_DIR / f'pregame_{today_str}.json'

# Lookahead Bias Fix: Load previously saved props for today to lock them.
# If Kalshi updates the line post-tipoff, we IGNORE it and keep our pregame snapshot.
locked_kalshi_data = {}
if pregame_path.exists():
    with open(pregame_path, 'r') as f:
        for p in json.load(f):
            locked_kalshi_data[p['kalshi_ticker']] = {
                'ticker': p['kalshi_ticker'],
                'event_ticker': p['event_ticker'],
                'player_name': p['player'],
                'stat': p['stat'],
                'line': p['line'],
                'threshold': p['threshold'],
                'yes_ask': p['yes_ask'],
                'no_ask': p['no_ask'],
                'yes_bid': p.get('yes_bid'),
                'no_bid': p.get('no_bid'),
                'last_price': p.get('last_price'),
                'close_time': p.get('close_time', ''),
                'game_title': p.get('game', ''),
            }
print(f'Loaded {len(locked_kalshi_data)} locked pre-game props from earlier today.')

kalshi_props = []
for series_ticker, stat_col in KALSHI_SERIES.items():
    try:
        r = requests.get(f'{KALSHI_BASE}/events',
                         params={'series_ticker': series_ticker, 'status': 'open', 'limit': 50})
        for ev in r.json().get('events', []):
            mr = requests.get(f'{KALSHI_BASE}/markets',
                              params={'event_ticker': ev['event_ticker'], 'limit': 200})
            for m in mr.json().get('markets', []):
                ticker = m['ticker']
                
                # --- LOOKAHEAD BIAS LOCK ---
                # If we already have this line locked from before tip-off, keep it.
                if ticker in locked_kalshi_data:
                    kalshi_props.append(locked_kalshi_data[ticker])
                    continue
                
                title = m.get('title', '')
                if ':' not in title:
                    continue
                
                player_name = title.split(':')[0].strip()"""

s4_repl = """pregame_path = TRACKING_DIR / f'pregame_{today_str}.json'

# Lookahead Bias Fix: Load previously saved props for today to lock them.
# If Kalshi updates the line post-tipoff, we IGNORE it and keep our pregame snapshot.
locked_kalshi_data = {}
if pregame_path.exists():
    with open(pregame_path, 'r') as f:
        for p in json.load(f):
            locked_kalshi_data[p['kalshi_ticker']] = {
                'ticker': p['kalshi_ticker'],
                'event_ticker': p['event_ticker'],
                'player_name': p['player'],
                'stat': p['stat'],
                'line': p['line'],
                'threshold': p['threshold'],
                'yes_ask': p['yes_ask'],
                'no_ask': p['no_ask'],
                'yes_bid': p.get('yes_bid'),
                'no_bid': p.get('no_bid'),
                'last_price': p.get('last_price'),
                'close_time': p.get('close_time', ''),
                'game_title': p.get('game', ''),
            }
print(f'Loaded {len(locked_kalshi_data)} locked pre-game props from earlier today.')

kalshi_props = []
for series_ticker, stat_col in KALSHI_SERIES.items():
    try:
        r = requests.get(f'{KALSHI_BASE}/events',
                         params={'series_ticker': series_ticker, 'status': 'open', 'limit': 50})
        for ev in r.json().get('events', []):
            mr = requests.get(f'{KALSHI_BASE}/markets',
                              params={'event_ticker': ev['event_ticker'], 'limit': 200})
            
            for m in mr.json().get('markets', []):
                ticker = m['ticker']
                
                # If we already have this line locked from before tip-off, keep it.
                if ticker in locked_kalshi_data:
                    kalshi_props.append(locked_kalshi_data[ticker])
                    continue
                
                title = m.get('title', '')
                if ':' not in title:
                    continue
                
                player_name = title.split(':')[0].strip()
                pname_norm = norm(player_name)
                
                # Check if the player's game has started
                player_tm = player_to_team.get(pname_norm)
                if player_tm in started_team_abbrs:
                    continue
"""
content = content.replace(s4_find, s4_repl)

# 3. Phase 13 changes to EV analysis to include ticker
s13_find = """            ev_rows.append({
                'player': pred['player'],
                'stat': stat,
                'game': pred.get('game', ''),"""

s13_repl = """            ev_rows.append({
                'date': today_str,
                'player': pred['player'],
                'kalshi_ticker': pred['kalshi_ticker'],
                'event_ticker': pred['event_ticker'],
                'stat': stat,
                'game': pred.get('game', ''),"""
content = content.replace(s13_find, s13_repl)

with open('networks/ballnet/inference_v2.qmd', 'w') as f:
    f.write(content)
