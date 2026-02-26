import requests

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"

r = requests.get(f'{KALSHI_BASE}/events', params={'series_ticker': 'KXNBAPTS', 'status': 'open', 'limit': 20})
events = r.json().get('events', [])

player_names = set()
for ev in events:
    mr = requests.get(f'{KALSHI_BASE}/markets', params={'event_ticker': ev['event_ticker'], 'limit': 20})
    markets = mr.json().get('markets', [])
    for m in markets:
        title = m.get('title', '')
        if ':' in title:
            player_name = title.split(':')[0].strip()
            player_names.add(player_name)

print(f"Sample Kalshi Names: {list(player_names)[:10]}")
