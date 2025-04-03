import os
import json
from player_cache import get_current_players

# Set environment variable to indicate we're in build
os.environ['VERCEL_BUILD'] = 'true'

# Create static data directory
os.makedirs('static/data', exist_ok = True)

# Generate and save players data
players = get_current_players()
with open('static/data/players.json', 'w') as f:
    json.dump(players, f)

print("Build script completed: Players data generated")