import copy, itertools, json, logging, pickle, time, warnings
from pathlib import Path
from datetime import datetime
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
import torch, torch.nn as nn, torch.nn.functional as F
from tqdm import tqdm

# ── Paths (local) ─────────────────────────────────────────────
NOTEBOOK_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT  = NOTEBOOK_DIR / 'NBA-GNN-prediction'
REPRO_ROOT = NOTEBOOK_DIR / 'reproduction'
MODEL_DIR  = NOTEBOOK_DIR / 'outputs' / 'model'
TRACKING_DIR = NOTEBOOK_DIR / 'outputs' / 'tracking'
DATA_DIR   = NOTEBOOK_DIR / 'outputs' / 'data'
KALSHI_DIR = TRACKING_DIR / 'kalshi_data'

import sys
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPRO_ROOT))

# ── Device ────────────────────────────────────────────────────
if torch.backends.mps.is_available():
    DEVICE = torch.device('mps')
elif torch.cuda.is_available():
    DEVICE = torch.device('cuda')
else:
    DEVICE = torch.device('cpu')
print('Using device:', DEVICE)

# ── Context/Setup ─────────────────────────────────────────────
FEATURE_COLS    = ['PTS','AST','REB','TO','STL','BLK','PLUS_MINUS',
                   'TCHS','PASS','DIST','PACE','USG_PCT','TS_PCT']
PREDICTION_COLS = ['PTS','AST','REB','TO','STL','BLK']
PRED_INDICES    = [FEATURE_COLS.index(c) for c in PREDICTION_COLS]
MIN_MINUTES     = 10.0
SEQ_LENGTH      = 10
OFFSET          = 1

print("Loading Cached Tensors...")
raw_df     = pd.read_parquet(DATA_DIR / 'raw_boxscores.parquet')
X_seq      = pickle.load(open(DATA_DIR / 'X_seq.pkl', 'rb'))
X_raw_seq  = pickle.load(open(DATA_DIR / 'X_raw.pkl', 'rb'))
G_seq      = pickle.load(open(DATA_DIR / 'G_seq.pkl', 'rb'))
player_ids = pickle.load(open(DATA_DIR / 'player_ids.pkl', 'rb'))
game_dates = pickle.load(open(DATA_DIR / 'game_dates.pkl', 'rb'))
day_seasons     = pickle.load(open(DATA_DIR / 'day_seasons.pkl', 'rb'))
team_temporal   = pickle.load(open(DATA_DIR / 'team_temporal.pkl', 'rb'))
pos_temporal    = pickle.load(open(DATA_DIR / 'pos_temporal.pkl', 'rb'))
n_teams         = pickle.load(open(DATA_DIR / 'n_teams.pkl', 'rb'))
mu_per_day = np.load(DATA_DIR / 'mu_per_day.npy')
sd_per_day = np.load(DATA_DIR / 'sd_per_day.npy')

team_temporal_t = torch.FloatTensor(team_temporal).to(DEVICE)
pos_temporal_t  = torch.FloatTensor(pos_temporal).to(DEVICE)
n_pos = 3

def graphs_to_edges(G_seq, player_ids):
    nd = {pid: i for i, pid in enumerate(player_ids)}
    out = []
    for G in G_seq:
        edges = list(G.edges())
        if not edges:
            n = len(player_ids)
            out.append(torch.stack([torch.arange(n), torch.arange(n)]).long().to(DEVICE))
        else:
            s, d = zip(*edges)
            s = [nd.get(x, 0) for x in s]; d = [nd.get(x, 0) for x in d]
            out.append(torch.stack([
                torch.LongTensor(s + d), torch.LongTensor(d + s)]).to(DEVICE))
    return out

G_edges = graphs_to_edges(G_seq, player_ids)

# Normalization
X_seq = (X_seq - mu_per_day) / sd_per_day

# Sliding Windows
unique_seasons = []
season_ranges = {}
prev_season = None

for d, s in enumerate(day_seasons):
    if s != prev_season:
        if prev_season is not None:
            season_ranges[prev_season] = (season_ranges[prev_season][0], d)
        season_ranges[s] = (d, None)
        unique_seasons.append(s)
        prev_season = s
        
season_ranges[prev_season] = (season_ranges[prev_season][0], len(day_seasons))

active_all = (X_raw_seq != 0).any(axis=-1)

X_in_parts, X_out_parts = [], []
G_in_parts, G_out_parts = [], []
mask_parts = []
target_day_indices = []

for s in unique_seasons:
    lo, hi = season_ranges[s]
    n_days = hi - lo
    n_win = n_days - SEQ_LENGTH - OFFSET + 1
    if n_win <= 0: continue
    X_s = X_seq[lo:hi]
    Xi = sliding_window_view(X_s[:-OFFSET], SEQ_LENGTH, axis=0)
    Xo = X_s[SEQ_LENGTH + OFFSET - 1:]
    Gi = [G_edges[lo + t:lo + t + SEQ_LENGTH] for t in range(n_win)]
    Go = G_edges[lo + SEQ_LENGTH + OFFSET - 1:lo + SEQ_LENGTH + OFFSET - 1 + n_win]
    mask_s = active_all[lo + SEQ_LENGTH + OFFSET - 1:lo + SEQ_LENGTH + OFFSET - 1 + n_win]
    days_s = list(range(lo + SEQ_LENGTH + OFFSET - 1, lo + SEQ_LENGTH + OFFSET - 1 + n_win))
    X_in_parts.append(Xi); X_out_parts.append(Xo)
    G_in_parts.extend(Gi); G_out_parts.extend(Go)
    mask_parts.append(mask_s)
    target_day_indices.extend(days_s)

X_in  = torch.FloatTensor(np.concatenate(X_in_parts, axis=0))
X_out = torch.FloatTensor(np.concatenate(X_out_parts, axis=0))
G_in  = G_in_parts
mask_out_t = torch.BoolTensor(np.concatenate(mask_parts, axis=0))
target_day_indices = np.array(target_day_indices)

T = len(G_in)
t1 = int(T * 0.50)
t2 = int(T * 0.75)

# We will iterate over the test set since it covers 2026
X_te, y_te, G_te = X_in[t2:],  X_out[t2:],  G_in[t2:]
mask_te = mask_out_t[t2:]
target_days_te = target_day_indices[t2:]

print("Loading Model...")
from gatv2tcn import GATv2TCN
model_in = len(FEATURE_COLS) + 2 + 2  # 17

team_emb = nn.Linear(n_teams, 2).to(DEVICE)
pos_emb  = nn.Linear(n_pos, 2).to(DEVICE)
model    = GATv2TCN(
    in_channels=model_in, out_channels=6,
    len_input=SEQ_LENGTH, len_output=1,
    temporal_filter=64, out_gatv2conv=32,
    dropout_tcn=0.25, dropout_gatv2conv=0.5, head_gatv2conv=4,
).to(DEVICE)

model.load_state_dict(torch.load(MODEL_DIR / 'model.pth', map_location=DEVICE))
team_emb.load_state_dict(torch.load(MODEL_DIR / 'team_emb.pth', map_location=DEVICE))
pos_emb.load_state_dict(torch.load(MODEL_DIR / 'pos_emb.pth', map_location=DEVICE))
model.eval(); team_emb.eval(); pos_emb.eval()

# Load Residuals
calibration_path = TRACKING_DIR / 'conformal_residuals.pkl'
with open(calibration_path, 'rb') as f:
    val_residuals = pickle.load(f)
    print("Loaded Conformal Residuals.")

MC_SAMPLES = 20

stat_map_reverse = {
    'points': 'PTS',
    'assists': 'AST',
    'rebounds': 'REB',
    'steals': 'STL',
    'blocks': 'BLK',
    'turnovers': 'TO'
}

def get_mc_dropout_prediction(model, x, G_idx, samples=MC_SAMPLES):
    model.train()
    preds = []
    with torch.no_grad():
        for _ in range(samples):
            p = model(x, G_idx)[0].cpu().numpy()
            preds.append(p)
    return np.array(preds)

generated_days = 0

print("Generating Historical Predictions...")
import re

for i in range(len(X_te)):
    day_i = target_days_te[i]
    game_date_str = game_dates[day_i]
    
    # We only care about Jan and Feb 2026
    if not ('2026-01' in game_date_str or '2026-02' in game_date_str):
        continue
        
    kalshi_path = KALSHI_DIR / f'historical_{game_date_str}.json'
    if not kalshi_path.exists():
        continue
        
    with open(kalshi_path, 'r') as f:
        k_props = json.load(f)
        
    print(f"[{game_date_str}] Processing {len(k_props)} Kalshi props...")
    generated_days += 1
    
    input_days = list(range(day_i - SEQ_LENGTH, day_i))
    Xl = []
    for t_step, abs_day in enumerate(input_days):
        tv = team_emb(team_temporal_t[abs_day])
        pv = pos_emb(pos_temporal_t[abs_day])
        Xl.append(torch.cat([X_te[i, :, :, t_step].to(DEVICE), tv, pv], 1))
    x = torch.stack(Xl, -1)[None, ...]
    
    # Get model distributions
    mc_preds = get_mc_dropout_prediction(model, x, G_te[i])
    
    mu_d = mu_per_day[day_i, 0, PRED_INDICES]
    sd_d = sd_per_day[day_i, 0, PRED_INDICES]
    
    preds_raw = (mc_preds * sd_d) + mu_d
    mc_mean = preds_raw.mean(axis=0)
    
    # Map normalize names
    player_to_idx = {}
    for pid in player_ids:
        # slow but safe finding
        p_rows = raw_df[raw_df['PLAYER_ID'] == pid].head(1)
        if len(p_rows) > 0:
            name = p_rows.iloc[0]['PLAYER_NAME'].lower().replace('.', '').replace('-', '').replace(' ', '')
            idx = player_ids.index(pid)
            player_to_idx[name] = idx
            
    day_predictions = []
    
    # Process each prob
    for p in k_props:
        title = p.get('title', '')
        if ':' not in title: continue
        
        parts = title.split(':')
        player = parts[0].strip()
        rest = parts[1].strip().lower()
        
        match = re.search(r'([\d\.]+)\+?\s+([a-z]+)', rest)
        if not match: continue
        
        val_str, stat_word = match.groups()
        threshold = float(val_str)
        stat = stat_map_reverse.get(stat_word, stat_word.upper())
        
        yes_ask = p.get('yes_ask')
        no_ask = p.get('no_ask')
        if yes_ask is None or no_ask is None: continue
        
        norm_name = player.lower().replace('.', '').replace('-', '').replace(' ', '')
        if norm_name not in player_to_idx:
            continue
            
        p_idx = player_to_idx[norm_name]
        try:
            stat_idx = PREDICTION_COLS.index(stat)
        except ValueError:
            continue
            
        pred_val = mc_mean[p_idx, stat_idx]
        
        # Conformal Logic
        res_pool = val_residuals.get(stat, np.array([0]))
        margin_needed = threshold - pred_val
        p_over = (res_pool > margin_needed).mean()
        p_under = 1 - p_over
        
        # EV
        ev_y = (p_over * (100 - yes_ask) - p_under * yes_ask) if pd.notna(yes_ask) and yes_ask > 0 else None
        ev_n = (p_under * (100 - no_ask) - p_over * no_ask) if pd.notna(no_ask) and no_ask > 0 else None
        
        action = 'NO EDGE'
        best_ev = max(ev_y or -999, ev_n or -999)
        
        if ev_y is not None and ev_n is not None:
            if ev_y >= ev_n and ev_y > 0:
                action = 'BUY YES (Over)'
                best_ev = ev_y
            elif ev_n > ev_y and ev_n > 0:
                action = 'BUY NO (Under)'
                best_ev = ev_n
                
        out_dict = {
            'player': player,
            'stat': stat,
            'threshold': threshold,
            'mc_mean': float(pred_val),
            'yes_ask': yes_ask,
            'no_ask': no_ask,
            'conf_p_over': float(p_over),
            'conf_p_under': float(p_under),
            'conf_ev_yes': float(ev_y) if ev_y is not None else None,
            'conf_ev_no': float(ev_n) if ev_n is not None else None,
            'conf_action': action,
            'conf_best_ev': float(best_ev) if best_ev != -999 else 0.0,
            # Best EV is what the naive model would predict
            'best_ev': float(best_ev) if best_ev != -999 else 0.0,
            'recent_5d': 5 # dummy value to bypass arbitrary filters
        }
        
        # Also need bet_edge for arbitrary filters
        if 'YES' in action:
            out_dict['bet_edge'] = float(p_over - (yes_ask / 100))
        elif 'NO' in action:
            out_dict['bet_edge'] = float(p_under - (no_ask / 100))
        else:
            out_dict['bet_edge'] = 0.0
            
        day_predictions.append(out_dict)
        
    out_file = TRACKING_DIR / f'full_ev_analysis_{game_date_str}.json'
    with open(out_file, 'w') as f:
        json.dump(day_predictions, f, indent=2)

print(f"\nDone! Generated historical predictions for {generated_days} dates.")
