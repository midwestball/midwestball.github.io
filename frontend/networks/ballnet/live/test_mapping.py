import sys
import pickle
import pandas as pd
from pathlib import Path

def clean_name(name: str) -> str:
    return ''.join(c.lower() for c in name if c.isalpha())

base_dir = Path("networks/ballnet/outputs/data")
with open(base_dir / 'player_ids.pkl', 'rb') as f:
    player_ids = pickle.load(f)

df = pd.read_parquet(base_dir / 'raw_boxscores.parquet')
p2n = df.drop_duplicates('PLAYER_ID', keep='last').set_index('PLAYER_ID')['PLAYER_NAME'].to_dict()

name2idx = {}
for pid, name in p2n.items():
    if pid in player_ids:
        idx = player_ids.index(pid)
        name2idx[clean_name(name)] = idx

print(f"Total model player IDs: {len(player_ids)}")
print(f"Total mapped Clean Names: {len(name2idx)}")
print(f"Sample mapped names: {list(name2idx.keys())[:10]}")
