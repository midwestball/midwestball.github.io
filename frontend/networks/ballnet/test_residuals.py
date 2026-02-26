import pickle
import numpy as np
import torch
import pandas as pd
from pathlib import Path
from numpy.lib.stride_tricks import sliding_window_view
import sys
import os

NOTEBOOK_DIR = Path('.').resolve()
REPO_ROOT  = NOTEBOOK_DIR / 'NBA-GNN-prediction'
REPRO_ROOT = NOTEBOOK_DIR / 'reproduction'

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPRO_ROOT))

from gatv2tcn import GATv2TCN

if torch.backends.mps.is_available(): DEVICE = torch.device('mps')
elif torch.cuda.is_available(): DEVICE = torch.device('cuda')
else: DEVICE = torch.device('cpu')

DATA_DIR = Path('outputs/data')
MODEL_DIR = Path('outputs/model')

# Load cached data
X_seq      = pickle.load(open(DATA_DIR / 'X_seq.pkl', 'rb'))  # Should now be raw stats!
X_raw_seq  = pickle.load(open(DATA_DIR / 'X_raw.pkl', 'rb'))
G_seq      = pickle.load(open(DATA_DIR / 'G_seq.pkl', 'rb'))
player_ids = pickle.load(open(DATA_DIR / 'player_ids.pkl', 'rb'))
game_dates = pickle.load(open(DATA_DIR / 'game_dates.pkl', 'rb'))
day_seasons = pickle.load(open(DATA_DIR / 'day_seasons.pkl', 'rb'))
team_temporal = pickle.load(open(DATA_DIR / 'team_temporal.pkl', 'rb'))
pos_temporal  = pickle.load(open(DATA_DIR / 'pos_temporal.pkl', 'rb'))
n_teams       = pickle.load(open(DATA_DIR / 'n_teams.pkl', 'rb'))
mu_per_day = np.load(DATA_DIR / 'mu_per_day.npy')
sd_per_day = np.load(DATA_DIR / 'sd_per_day.npy')

FEATURE_COLS    = ['PTS','AST','REB','TO','STL','BLK','PLUS_MINUS','TCHS','PASS','DIST','PACE','USG_PCT','TS_PCT']
PREDICTION_COLS = ['PTS','AST','REB','TO','STL','BLK']
PRED_INDICES    = [FEATURE_COLS.index(c) for c in PREDICTION_COLS]
SEQ_LENGTH      = 10
OFFSET          = 1

# Normalize (the single time it should happen!)
X_seq_raw_copy = X_seq.copy()
X_seq = (X_seq - mu_per_day) / sd_per_day

team_temporal_t = torch.FloatTensor(team_temporal).to(DEVICE)
pos_temporal_t  = torch.FloatTensor(pos_temporal).to(DEVICE)

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
            out.append(torch.stack([torch.LongTensor(s + d), torch.LongTensor(d + s)]).to(DEVICE))
    return out

G_edges = graphs_to_edges(G_seq, player_ids)

unique_seasons = []
season_ranges = {}
prev_season = None
for d, s in enumerate(day_seasons):
    if s != prev_season:
        if prev_season is not None: season_ranges[prev_season] = (season_ranges[prev_season][0], d)
        season_ranges[s] = (d, None)
        unique_seasons.append(s)
        prev_season = s
season_ranges[prev_season] = (season_ranges[prev_season][0], len(day_seasons))

active_all = (X_raw_seq != 0).any(axis=-1)
X_in_parts, X_out_parts, G_in_parts, mask_parts, target_day_indices = [], [], [], [], []

for s in unique_seasons:
    lo, hi = season_ranges[s]
    n_days = hi - lo
    n_win = n_days - SEQ_LENGTH - OFFSET + 1
    if n_win <= 0: continue
    X_s = X_seq[lo:hi]
    Xi = sliding_window_view(X_s[:-OFFSET], SEQ_LENGTH, axis=0)
    Xo = X_s[SEQ_LENGTH + OFFSET - 1:]
    Gi = [G_edges[lo + t:lo + t + SEQ_LENGTH] for t in range(n_win)]
    mask_s = active_all[lo + SEQ_LENGTH + OFFSET - 1:lo + SEQ_LENGTH + OFFSET - 1 + n_win]
    days_s = list(range(lo + SEQ_LENGTH + OFFSET - 1, lo + SEQ_LENGTH + OFFSET - 1 + n_win))
    X_in_parts.append(Xi); X_out_parts.append(Xo); G_in_parts.extend(Gi)
    mask_parts.append(mask_s); target_day_indices.extend(days_s)

X_in  = torch.FloatTensor(np.concatenate(X_in_parts, axis=0))
X_out = torch.FloatTensor(np.concatenate(X_out_parts, axis=0))
G_in  = G_in_parts
mask_out_t = torch.BoolTensor(np.concatenate(mask_parts, axis=0))
target_day_indices = np.array(target_day_indices)

T = len(G_in)
t1 = int(T * 0.50)
t2 = int(T * 0.75)
X_va, y_va, G_va = X_in[t1:t2], X_out[t1:t2], G_in[t1:t2]

model_in = len(FEATURE_COLS) + 2 + 2 
model = GATv2TCN(in_channels=model_in, out_channels=6, len_input=10, len_output=1, temporal_filter=64, out_gatv2conv=32, dropout_tcn=0.25, dropout_gatv2conv=0.5, head_gatv2conv=4).to(DEVICE)
model.load_state_dict(torch.load(MODEL_DIR / 'model.pth', map_location=DEVICE))

team_emb = torch.nn.Linear(n_teams, 2).to(DEVICE)
pos_emb  = torch.nn.Linear(3, 2).to(DEVICE)

team_emb.load_state_dict(torch.load(MODEL_DIR / 'team_emb.pth', map_location=DEVICE))
pos_emb.load_state_dict(torch.load(MODEL_DIR / 'pos_emb.pth', map_location=DEVICE))
model.eval(); team_emb.eval(); pos_emb.eval()

val_residuals = {stat: [] for stat in PREDICTION_COLS}
with torch.no_grad():
    for i in range(len(X_va)):
        day_i = target_day_indices[t1 + i] 
        input_days = list(range(day_i - SEQ_LENGTH, day_i))
        Xl = []
        for t_step, abs_day in enumerate(input_days):
            tv = team_emb(team_temporal_t[abs_day])
            pv = pos_emb(pos_temporal_t[abs_day])
            Xl.append(torch.cat([X_va[i, :, :, t_step].to(DEVICE), tv, pv], 1))
        x = torch.stack(Xl, -1)[None, ...]
        p_latent = model(x, G_va[i])[0].cpu().numpy()
        t_latent = y_va[i, :, PRED_INDICES].numpy()

        mu_d = mu_per_day[day_i, 0, PRED_INDICES]
        sd_d = sd_per_day[day_i, 0, PRED_INDICES]
        p_raw = (p_latent * sd_d) + mu_d
        t_raw = (t_latent * sd_d) + mu_d
        m = mask_out_t[t1 + i].numpy() # Active players
        
        res_raw = t_raw[m] - p_raw[m] 
        for s_idx, stat in enumerate(PREDICTION_COLS):
            val_residuals[stat].extend(res_raw[:, s_idx].tolist())

for stat in PREDICTION_COLS:
    val_residuals[stat] = np.array(val_residuals[stat])

print("Stat   | 5th %ile  | Median    | 95th %ile")
for stat in PREDICTION_COLS:
    res = val_residuals[stat]
    print(f"{stat:<6} | {np.percentile(res, 5):>9.2f} | {np.median(res):>9.2f} | {np.percentile(res, 95):>9.2f}")
