import requests
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from tqdm import tqdm

KALSHI_BASE = 'https://api.elections.kalshi.com/trade-api/v2'
DATA_DIR = Path('networks/ballnet/outputs/tracking/kalshi_data')
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Important: Kalshi NBA player props might be under different tickers throughout the season.
# We will pull all events for 'KXNBAP' (NBA Player Props) and 'KXNBA' (NBA Games)
# and try to extract player props.

def fetch_events(series_ticker, max_pages=10):
    events = []
    cursor = None
    for _ in range(max_pages):
        params = {'series_ticker': series_ticker, 'limit': 200}
        if cursor:
            params['cursor'] = cursor
            
        r = requests.get(f'{KALSHI_BASE}/events', params=params)
        if r.status_code != 200:
            print(f"Error fetching {series_ticker}: {r.status_code}")
            break
            
        data = r.json()
        evs = data.get('events', [])
        events.extend(evs)
        
        cursor = data.get('cursor')
        if not cursor or len(evs) < 200:
            break
        time.sleep(0.5)
    return events

# Stat series tickers
stat_series = ['KXNBAPTS', 'KXNBAAST', 'KXNBAREB', 'KXNBASTL', 'KXNBABLK', 'KXNBATO']

print("Fetching all NBA events for player props...")
events = []
for series in stat_series:
    print(f"Fetching {series}...")
    events.extend(fetch_events(series, max_pages=50))
    
print(f"Found {len(events)} events.")

# Filter to 2026 onwards
target_events = []
for ev in events:
    target_events.append(ev['event_ticker'])

target_events = list(set(target_events))
print(f"Unique event tickers: {len(target_events)}")

all_markets = []
for event_ticker in tqdm(target_events, desc="Fetching markets"):
    mr = requests.get(f'{KALSHI_BASE}/markets', params={'event_ticker': event_ticker, 'limit': 200})
    if mr.status_code == 200:
        markets = mr.json().get('markets', [])
        
        for m in markets:
            if m.get('status') == 'finalized': # Only get settled markets
                # Check if it's 2026
                close_time = m.get('close_time', '')
                if close_time.startswith('2026-01') or close_time.startswith('2026-02'):
                    title = m.get('title', '')
                    if ':' in title: # Player prop format usually has a colon
                        exp_time_str = m.get('expected_expiration_time')
                        if not exp_time_str: continue
                        
                        exp_time = datetime.strptime(exp_time_str[:19], "%Y-%m-%dT%H:%M:%S")
                        end_ts = int(exp_time.timestamp()) - 3 * 3600 # 3 hrs prior is approx tip-off
                        start_ts = end_ts - 2 * 24 * 3600 # 48 hours prior
                        
                        series_ticker = m['ticker'].split('-')[0]
                        cr = requests.get(f'{KALSHI_BASE}/series/{series_ticker}/markets/{m["ticker"]}/candlesticks', 
                                          params={'start_ts': start_ts, 'end_ts': end_ts, 'period_interval': 1})
                        if cr.status_code == 200:
                            candlesticks = cr.json().get('candlesticks', [])
                            if candlesticks:
                                last_c = candlesticks[-1]
                                ya = last_c.get('yes_ask', {}).get('close')
                                yb = last_c.get('yes_bid', {}).get('close')
                                if ya is not None and yb is not None:
                                    m['yes_ask'] = ya
                                    m['no_ask'] = 100 - yb
                                    all_markets.append(m)
                        time.sleep(0.1) # Prevent rate limiting
    time.sleep(0.2)

print(f"Found {len(all_markets)} settled player prop markets in Jan/Feb 2026 with pre-game odds.")

# Split by day for backtesting
markets_by_day = {}
for m in all_markets:
    day = m['close_time'][:10]
    if day not in markets_by_day:
        markets_by_day[day] = []
    markets_by_day[day].append(m)

for day, markets in markets_by_day.items():
    out_path = DATA_DIR / f'historical_{day}.json'
    with open(out_path, 'w') as f:
        json.dump(markets, f, indent=2)
    print(f"Saved {len(markets)} markets for {day}")
