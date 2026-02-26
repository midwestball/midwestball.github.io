"""
GATv2-GCN NBA Player Performance — Local Inference (MacBook / MPS)
==================================================================
Adapted from the Colab training notebook.
Loads pre-trained weights and cached data from the local `outputs/` folder.
"""

import copy, itertools, json, logging, os, pickle, sys, time, warnings
from pathlib import Path
warnings.filterwarnings('ignore')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import networkx as nx
from scipy import stats
from sklearn import preprocessing
from sklearn.metrics import (mean_squared_error, mean_absolute_error,
                             mean_absolute_percentage_error,
                             root_mean_squared_error)
from numpy.lib.stride_tricks import sliding_window_view

import torch, torch.nn as nn, torch.nn.functional as F

# ── Paths (local, relative to this script) ────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT  = SCRIPT_DIR / 'NBA-GNN-prediction'
REPRO_ROOT = SCRIPT_DIR / 'reproduction'
MODEL_DIR  = SCRIPT_DIR / 'outputs' / 'model'
FIG_DIR    = SCRIPT_DIR / 'outputs' / 'figures'
DATA_DIR   = SCRIPT_DIR / 'outputs' / 'data'

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPRO_ROOT))

# ── Device selection: prefer MPS on Apple Silicon ─────────────
if torch.backends.mps.is_available():
    DEVICE = torch.device('mps')
elif torch.cuda.is_available():
    DEVICE = torch.device('cuda')
else:
    DEVICE = torch.device('cpu')
print(f'Using device: {DEVICE}')

# ── Feature / prediction constants ───────────────────────────
FEATURE_COLS    = ['PTS','AST','REB','TO','STL','BLK','PLUS_MINUS',
                   'TCHS','PASS','DIST','PACE','USG_PCT','TS_PCT']
PREDICTION_COLS = ['PTS','AST','REB','TO','STL','BLK']
PRED_INDICES    = [FEATURE_COLS.index(c) for c in PREDICTION_COLS]
MIN_MINUTES     = 10.0
SEQ_LENGTH      = 10
OFFSET          = 1

# =====================================================================
# 1 · Load cached data
# =====================================================================
print('\n── Loading cached data ──')
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
print(f'X_seq shape: {X_seq.shape}   Players: {len(player_ids)}   Game-days: {len(game_dates)}')

# =====================================================================
# 2 · Rebuild edge tensors & temporal embeddings on DEVICE
# =====================================================================
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

print('Building edge tensors…')
G_edges = graphs_to_edges(G_seq, player_ids)
print(f'Built {len(G_edges)} edge tensors.')

# =====================================================================
# 3 · Rebuild season ranges & sliding windows (no retraining)
# =====================================================================
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

print('\nSeason boundaries:')
for s, (lo, hi) in season_ranges.items():
    print(f'  {s}: days [{lo}, {hi})  ({hi - lo} days)')

# ── Per-season Z-score normalization ──────────────────────────
# The cached X_seq.pkl contains raw forward-filled stats (pre-normalization).
# We must apply the same normalization the Colab notebook did in cell 12.
# Keep a copy of the raw data for un-normalization later.
X_seq_raw_copy = X_seq.copy()
X_seq = (X_seq - mu_per_day) / sd_per_day
print('Applied per-season Z-score normalization to X_seq.')

# ── Active-player mask ──
active_all = (X_raw_seq != 0).any(axis=-1)

# ── Season-isolated sliding windows ──
X_in_parts, X_out_parts = [], []
G_in_parts, G_out_parts = [], []
mask_parts = []
target_day_indices = []

for s in unique_seasons:
    lo, hi = season_ranges[s]
    n_days = hi - lo
    n_win = n_days - SEQ_LENGTH - OFFSET + 1
    if n_win <= 0:
        continue
    X_s = X_seq[lo:hi]
    Xi = sliding_window_view(X_s[:-OFFSET], SEQ_LENGTH, axis=0)
    Xo = X_s[SEQ_LENGTH + OFFSET - 1:]
    Gi = [G_edges[lo + t:lo + t + SEQ_LENGTH] for t in range(n_win)]
    Go = G_edges[lo + SEQ_LENGTH + OFFSET - 1:lo + SEQ_LENGTH + OFFSET - 1 + n_win]
    mask_s = active_all[lo + SEQ_LENGTH + OFFSET - 1:lo + SEQ_LENGTH + OFFSET - 1 + n_win]
    days_s = list(range(lo + SEQ_LENGTH + OFFSET - 1, lo + SEQ_LENGTH + OFFSET - 1 + n_win))
    X_in_parts.append(Xi)
    X_out_parts.append(Xo)
    G_in_parts.extend(Gi)
    G_out_parts.extend(Go)
    mask_parts.append(mask_s)
    target_day_indices.extend(days_s)

X_in  = torch.FloatTensor(np.concatenate(X_in_parts, axis=0))
X_out = torch.FloatTensor(np.concatenate(X_out_parts, axis=0))
G_in  = G_in_parts
mask_out_t = torch.BoolTensor(np.concatenate(mask_parts, axis=0))
target_day_indices = np.array(target_day_indices)

T = len(G_in)
total_possible_windows = T
t1 = int(total_possible_windows * 0.50)
t2 = int(total_possible_windows * 0.75)

X_tr, y_tr, G_tr = X_in[:t1], X_out[:t1], G_in[:t1]
X_va, y_va, G_va = X_in[t1:t2], X_out[t1:t2], G_in[t1:t2]
X_te, y_te, G_te = X_in[t2:],  X_out[t2:],  G_in[t2:]
mask_tr = mask_out_t[:t1]
mask_va = mask_out_t[t1:t2]
mask_te = mask_out_t[t2:]
target_days_te = target_day_indices[t2:]
target_days_tr = target_day_indices[:t1]
target_days_va = target_day_indices[t1:t2]

print(f'\nTotal windows: {T}  →  train:{t1}  val:{t2-t1}  test:{T-t2}')

# =====================================================================
# 4 · Load model
# =====================================================================
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

# Load trained weights (map to current device)
model.load_state_dict(torch.load(MODEL_DIR / 'model.pth', map_location=DEVICE))
team_emb.load_state_dict(torch.load(MODEL_DIR / 'team_emb.pth', map_location=DEVICE))
pos_emb.load_state_dict(torch.load(MODEL_DIR / 'pos_emb.pth', map_location=DEVICE))
model.eval(); team_emb.eval(); pos_emb.eval()

total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
print(f'\nModel loaded. Trainable parameters: {total_params:,}')
print(model)

# =====================================================================
# 5 · Test set evaluation
# =====================================================================
print('\n── Running test-set evaluation ──')
all_preds_raw, all_trues_raw = [], []
all_preds, all_trues = [], []

with torch.no_grad():
    for i in range(len(X_te)):
        day_i = target_days_te[i]
        input_days = list(range(day_i - SEQ_LENGTH, day_i))
        Xl = []
        for t_step, abs_day in enumerate(input_days):
            tv = team_emb(team_temporal_t[abs_day])
            pv = pos_emb(pos_temporal_t[abs_day])
            Xl.append(torch.cat([X_te[i, :, :, t_step].to(DEVICE), tv, pv], 1))
        x = torch.stack(Xl, -1)[None, ...]
        p_latent = model(x, G_te[i])[0].cpu().numpy()
        t_latent = y_te[i, :, PRED_INDICES].numpy()

        mu_d = mu_per_day[day_i, 0, PRED_INDICES]
        sd_d = sd_per_day[day_i, 0, PRED_INDICES]
        p_raw = (p_latent * sd_d) + mu_d
        t_raw = (t_latent * sd_d) + mu_d

        m = mask_te[i].numpy()
        all_preds_raw.append(p_raw[m])
        all_trues_raw.append(t_raw[m])
        all_preds.append(p_latent[m])
        all_trues.append(t_latent[m])

AP_raw = np.concatenate(all_preds_raw)
AT_raw = np.concatenate(all_trues_raw)
AP = np.concatenate(all_preds)
AT = np.concatenate(all_trues)

rmse_raw = root_mean_squared_error(AT_raw, AP_raw)
mae_raw  = mean_absolute_error(AT_raw, AP_raw)
mape_raw = mean_absolute_percentage_error(AT_raw, AP_raw)

corr_z = []
for mi in range(6):
    r = np.corrcoef(AP_raw[:, mi], AT_raw[:, mi])[0, 1]
    if not np.isnan(r) and abs(r) < 1 - 1e-7:
        corr_z.append(np.arctanh(r))
corr_raw = np.tanh(np.mean(corr_z)) if corr_z else float('nan')

repro_metrics_raw = {
    'RMSE': float(rmse_raw), 'MAE': float(mae_raw),
    'MAPE': float(mape_raw), 'CORR': float(corr_raw),
}

# Also compute normalized-space metrics for the comparison table
rmse_n = root_mean_squared_error(AT, AP)
mae_n  = mean_absolute_error(AT, AP)
mape_n = mean_absolute_percentage_error(AT, AP)
corr_z_n = []
for mi in range(6):
    r = np.corrcoef(AP[:, mi], AT[:, mi])[0, 1]
    if not np.isnan(r) and abs(r) < 1 - 1e-7:
        corr_z_n.append(np.arctanh(r))
corr_n = np.tanh(np.mean(corr_z_n)) if corr_z_n else float('nan')
repro_metrics = {'RMSE': round(rmse_n, 3), 'MAE': round(mae_n, 3),
                 'MAPE': round(mape_n, 3), 'CORR': round(corr_n, 3)}

print(f'── Test Metrics (RAW STATS — ACTIVE PLAYERS ONLY) ──')
print(f'  Evaluated on {len(AP_raw):,} active player-predictions')
for k, v in repro_metrics_raw.items():
    print(f'  {k}: {v:.4f}')

# =====================================================================
# 6 · Visualizations
# =====================================================================
os.makedirs(FIG_DIR, exist_ok=True)
train_hist = np.load(MODEL_DIR / 'train_hist.npy')
val_hist   = np.load(MODEL_DIR / 'val_hist.npy')
best_epoch = int(np.argmin(val_hist))

# 6a – Learning curves
fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(train_hist, label='Train Loss', color='#5b8fc7', lw=2)
ax.plot(val_hist,   label='Val Loss',   color='#e07b54', lw=2)
ax.axvline(best_epoch, color='gray', ls='--', lw=1.5, label=f'Best ({best_epoch})')
ax.set_xlabel('Epoch'); ax.set_ylabel('MSE Loss')
ax.set_title('GATv2-TCN Learning Curves', fontweight='bold')
ax.legend(); ax.grid(alpha=0.25)
plt.tight_layout()
plt.savefig(FIG_DIR / 'loss_curves.png', dpi=150)
print('Saved loss_curves.png')

# 6b – Model benchmark comparison
PAPER = {
    'N-BEATS':      {'RMSE': 5.112, 'MAE': 4.552, 'MAPE': 3.701, 'CORR': 0.366},
    'DeepVAR':      {'RMSE': 2.896, 'MAE': 2.151, 'MAPE': 1.754, 'CORR': 0.396},
    'TCN':          {'RMSE': 2.414, 'MAE': 1.780, 'MAPE': 0.551, 'CORR': 0.418},
    'ASTGCN':       {'RMSE': 2.293, 'MAE': 1.699, 'MAPE': 0.455, 'CORR': 0.453},
    'GATv2 (Paper)': {'RMSE': 2.222, 'MAE': 1.642, 'MAPE': 0.513, 'CORR': 0.508},
    'GATv2 (Repro)': repro_metrics,
}
COLORS = ['#e07b54', '#5b8fc7', '#70b472', '#c07ec9', '#f0c040', '#e84393']
mets = ['RMSE', 'MAE', 'CORR']
fig, axes = plt.subplots(1, 3, figsize=(16, 5))
for ax, met in zip(axes, mets):
    models = list(PAPER.keys())
    vals   = [PAPER[m][met] for m in models]
    bars   = ax.bar(range(len(models)), vals, color=COLORS, edgecolor='white', width=0.65)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.01 * max(vals),
                f'{v:.3f}', ha='center', fontsize=8.5, fontweight='bold')
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels(models, rotation=35, ha='right', fontsize=9)
    ax.set_title(met, fontweight='bold'); ax.grid(axis='y', alpha=0.2)
plt.suptitle('Model Benchmark Comparison', fontweight='bold')
plt.tight_layout()
plt.savefig(FIG_DIR / 'model_comparison.png', dpi=150, bbox_inches='tight')
print('Saved model_comparison.png')

# 6c – Predicted vs. Actual (per statistic)
colors = ['#5b8fc7', '#e07b54', '#70b472', '#c07ec9', '#f0c040', '#e84393']
fig, axes = plt.subplots(2, 3, figsize=(15, 9))
for i, (ax, stat) in enumerate(zip(axes.ravel(), PREDICTION_COLS)):
    p, t = AP[:, i], AT[:, i]
    ax.scatter(t, p, alpha=0.25, s=8, color=colors[i], rasterized=True)
    lo, hi = min(t.min(), p.min()), max(t.max(), p.max())
    ax.plot([lo, hi], [lo, hi], 'k--', lw=1.5, alpha=0.6, label='Perfect')
    m, b, r, *_ = stats.linregress(t, p)
    xs = np.array([lo, hi]); ax.plot(xs, m * xs + b, 'r-', lw=2, label=f'r={r:.3f}')
    ax.set_title(f'{stat} | MAE={mean_absolute_error(t, p):.2f}', fontweight='bold')
    ax.set_xlabel('Actual'); ax.set_ylabel('Predicted')
    ax.legend(fontsize=8); ax.grid(alpha=0.15)
plt.suptitle('GATv2-TCN: Predicted vs. Actual (Test Set)', fontweight='bold')
plt.tight_layout()
plt.savefig(FIG_DIR / 'pred_vs_actual.png', dpi=150, bbox_inches='tight')
print('Saved pred_vs_actual.png')

# 6d – Per-stat error bars
mae_s  = np.abs(AP - AT).mean(0)
rmse_s = np.sqrt(((AP - AT) ** 2).mean(0))
corr_s = [np.corrcoef(AP[:, i], AT[:, i])[0, 1] for i in range(6)]
x = np.arange(6); w = 0.28
fig, ax = plt.subplots(figsize=(12, 5))
for off, vals, lbl, col in [(-w, mae_s, 'MAE', '#5b8fc7'), (0, rmse_s, 'RMSE', '#e07b54'), (w, corr_s, 'CORR', '#70b472')]:
    bars = ax.bar(x + off, vals, w, label=lbl, color=col, edgecolor='white')
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                f'{bar.get_height():.2f}', ha='center', fontsize=8)
ax.set_xticks(x); ax.set_xticklabels(PREDICTION_COLS, fontsize=12)
ax.set_title('Per-Statistic Error Metrics (Test Set)', fontweight='bold')
ax.legend(); ax.grid(axis='y', alpha=0.2)
plt.tight_layout()
plt.savefig(FIG_DIR / 'per_stat_errors.png', dpi=150)
print('Saved per_stat_errors.png')

# 6e – Residual distributions
res = AP - AT
fig, axes = plt.subplots(2, 3, figsize=(15, 8))
for i, (ax, stat) in enumerate(zip(axes.ravel(), PREDICTION_COLS)):
    r = res[:, i]
    ax.hist(r, bins=60, color=colors[i], edgecolor='white', alpha=0.85, density=True)
    xs = np.linspace(r.min(), r.max(), 300)
    ax.plot(xs, stats.norm.pdf(xs, r.mean(), r.std()), 'k-', lw=2)
    ax.axvline(0,        color='red',    ls='--', lw=1.5)
    ax.axvline(r.mean(), color='orange', ls='-',  lw=1.5, label=f'μ={r.mean():.2f}')
    ax.set_title(stat, fontweight='bold')
    ax.legend(fontsize=8); ax.grid(axis='y', alpha=0.2)
plt.suptitle('Residual Error Distributions', fontweight='bold')
plt.tight_layout()
plt.savefig(FIG_DIR / 'residuals.png', dpi=150, bbox_inches='tight')
print('Saved residuals.png')

# 6f – Correlation heatmap
STAT_LBL = ['PTS', 'AST', 'REB', 'TO', 'STL', 'BLK', '±', 'TCHS', 'PASS', 'DIST', 'PACE', 'USG%', 'TS%']
n = X_seq.shape[-1]
flat = X_seq.reshape(-1, n)
flat = flat[(flat != 0).any(1)]
corr_mat = np.corrcoef(flat.T)
fig, ax = plt.subplots(figsize=(9, 7))
im = ax.imshow(corr_mat, cmap='RdBu_r', vmin=-1, vmax=1)
ax.set_xticks(range(n)); ax.set_xticklabels(STAT_LBL[:n], rotation=45, ha='right')
ax.set_yticks(range(n)); ax.set_yticklabels(STAT_LBL[:n])
for i in range(n):
    for j in range(n):
        ax.text(j, i, f'{corr_mat[i, j]:.2f}', ha='center', va='center', fontsize=7,
                color='white' if abs(corr_mat[i, j]) > 0.5 else 'black')
plt.colorbar(im, ax=ax, shrink=0.8, label='Pearson r')
ax.set_title('Feature Correlation Matrix', fontweight='bold')
plt.tight_layout()
plt.savefig(FIG_DIR / 'correlation_heatmap.png', dpi=150, bbox_inches='tight')
print('Saved correlation_heatmap.png')

# 6g – Graph topology sample
id2name = {k: v for k, v in zip(player_ids, [str(p) for p in player_ids])}
id2name_pkl = REPO_ROOT / 'player_id2name.pkl'
if id2name_pkl.exists():
    id2name = pickle.load(open(id2name_pkl, 'rb'))

G_sample = G_seq[len(G_seq) // 2]
active   = [n for n in G_sample.nodes() if G_sample.degree(n) > 0][:60]
subG     = G_sample.subgraph(active)
comps    = list(nx.connected_components(subG))
cmap_g   = plt.cm.get_cmap('tab20', len(comps))
nc = {}
for k, comp in enumerate(comps):
    for n in comp: nc[n] = cmap_g(k % 20)
fig, ax = plt.subplots(figsize=(13, 10))
pos = nx.kamada_kawai_layout(subG)
labels = {n: str(id2name.get(n, n))[:10] for n in subG.nodes()}
nx.draw_networkx_nodes(subG, pos, ax=ax,
                       node_color=[nc.get(n, '#ccc') for n in subG.nodes()],
                       node_size=250, alpha=0.93, linewidths=1.3, edgecolors='white')
nx.draw_networkx_edges(subG, pos, ax=ax, alpha=0.3, edge_color='#888', width=1.2)
nx.draw_networkx_labels(subG, pos, labels=labels, ax=ax, font_size=6.5)
ax.set_title('Game-Day Graph Topology (colours = game clusters)', fontweight='bold')
ax.axis('off'); plt.tight_layout()
plt.savefig(FIG_DIR / 'graph_topology.png', dpi=150, bbox_inches='tight')
print('Saved graph_topology.png')

# 6h – Performance radar
all_r = {**PAPER, 'GATv2 (Repro)': repro_metrics}
def to_radar(r):
    return {'1/RMSE': 1 / max(r['RMSE'], 1e-6), '1/MAE': 1 / max(r['MAE'], 1e-6),
            '1/MAPE': 1 / max(r['MAPE'], 1e-6), 'CORR': r['CORR']}
normed = {m: to_radar(v) for m, v in all_r.items()}
cats = list(next(iter(normed.values())).keys())
angles = np.linspace(0, 2 * np.pi, len(cats), endpoint=False).tolist() + [0]
RCOLS = ['#e07b54', '#5b8fc7', '#70b472', '#c07ec9', '#f0c040', '#e84393']
fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={'polar': True})
for (mtype, m), col in zip(normed.items(), RCOLS):
    vals = list(m.values()) + [list(m.values())[0]]
    ax.plot(angles, vals, lw=2.5, color=col, label=mtype)
    ax.fill(angles, vals, alpha=0.07, color=col)
ax.set_xticks(angles[:-1]); ax.set_xticklabels(cats, fontsize=12)
ax.set_yticklabels([])
ax.set_title('Performance Radar (higher=better on all axes)', fontweight='bold', pad=25)
ax.legend(loc='upper right', bbox_to_anchor=(1.45, 1.1), fontsize=9)
plt.tight_layout()
plt.savefig(FIG_DIR / 'radar.png', dpi=150, bbox_inches='tight')
print('Saved radar.png')

# 6i – PTS forecast trend
T_te = len(all_preds)
mean_p = [all_preds[i][:, 0].mean() for i in range(T_te)]
mean_t = [all_trues[i][:, 0].mean() for i in range(T_te)]
std_p  = [all_preds[i][:, 0].std()  for i in range(T_te)]
xr = np.arange(T_te)
fig, ax = plt.subplots(figsize=(14, 4.5))
ax.plot(xr, mean_t, color='#e07b54', lw=2.5, ls='--', label='Actual PTS')
ax.plot(xr, mean_p, color='#5b8fc7', lw=2.5, label='Predicted PTS')
ax.fill_between(xr, np.array(mean_p) - np.array(std_p),
                np.array(mean_p) + np.array(std_p), alpha=0.18, color='#5b8fc7', label='±1σ')
ax.set_xlabel('Test-Set Game-Day Index'); ax.set_ylabel('PTS (Z-Normalised)')
ax.set_title('Population-Average PTS Forecast vs. Actuals', fontweight='bold')
ax.legend(); ax.grid(axis='y', alpha=0.2)
plt.tight_layout()
plt.savefig(FIG_DIR / 'pts_trend.png', dpi=150)
print('Saved pts_trend.png')

# =====================================================================
# 7 · Case study — Out-of-Sample Prop Pick'em
# =====================================================================
import unicodedata

print('\n── Case Study ──')
test_game_dates = [game_dates[d] for d in target_days_te]
print(f'Test set spans: {test_game_dates[0]} → {test_game_dates[-1]}')

case_study_idx = len(target_days_te) // 2
case_study_abs_day = target_days_te[case_study_idx]
case_study_date = game_dates[case_study_abs_day]
print(f'Case study date: {case_study_date} (test window index {case_study_idx})')

# Build name lookups
name2pidx = {}
for pid in player_ids:
    rows = raw_df[raw_df['PLAYER_ID'] == pid]
    if len(rows):
        name = rows.iloc[0]['PLAYER_NAME']
        name2pidx[name] = player_ids.index(pid)

player_name_to_id = dict(zip(raw_df['PLAYER_NAME'], raw_df['PLAYER_ID']))

def normalize_string(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn').lower()

normalized_name_to_id = {normalize_string(name): pid for name, pid in player_name_to_id.items()}

def get_player_id(name):
    return normalized_name_to_id.get(normalize_string(name), None)

# Show top-15 predicted scorers
with torch.no_grad():
    input_days = list(range(case_study_abs_day - SEQ_LENGTH + 1, case_study_abs_day + 1))
    Xl = []
    for t_step, abs_day in enumerate(input_days[:SEQ_LENGTH]):
        tv = team_emb(team_temporal_t[abs_day])
        pv = pos_emb(pos_temporal_t[abs_day])
        Xl.append(torch.cat([torch.FloatTensor(X_seq[abs_day]).to(DEVICE), tv, pv], 1))
    x = torch.stack(Xl, -1)[None, ...]
    g_window = G_edges[case_study_abs_day - SEQ_LENGTH + 1:case_study_abs_day + 1]
    preds_cs = model(x, g_window)[0].cpu().numpy()

actuals_cs = X_seq_raw_copy[case_study_abs_day]  # raw stats (not normalized)
pts_pred_idx = PREDICTION_COLS.index('PTS')
pts_feat_idx = FEATURE_COLS.index('PTS')
mu_d = mu_per_day[case_study_abs_day, 0, pts_feat_idx]
sd_d = sd_per_day[case_study_abs_day, 0, pts_feat_idx]
active_mask = (X_raw_seq[case_study_abs_day] != 0).any(axis=-1)
pts_predicted = preds_cs[:, pts_pred_idx] * sd_d + mu_d  # un-normalize predictions
pts_actual    = actuals_cs[:, pts_feat_idx]               # already raw
topk = np.argsort(pts_predicted)[::-1][:15]
rev_name = {v: k for k, v in name2pidx.items()}
print(f'\nTop-15 predicted scorers for {case_study_date}:')
for rank, pidx in enumerate(topk):
    name = rev_name.get(pidx, f'PID={player_ids[pidx]}')
    act = 'active' if active_mask[pidx] else 'inactive'
    print(f'  {rank + 1:2d}. {name:25s}  pred={pts_predicted[pidx]:5.1f}  actual={pts_actual[pidx]:5.1f}  ({act})')

# =====================================================================
# 8 · Summary table
# =====================================================================
summary = pd.DataFrame(PAPER).T.rename_axis('Model')
summary.loc['GATv2 (Repro)'] = pd.Series(repro_metrics)
summary = summary.round(3)
print('\n── Summary ──')
print(summary.to_string())
summary.to_csv(MODEL_DIR / 'summary_table.csv')
print(f'\nSaved summary table to {MODEL_DIR / "summary_table.csv"}')

print('\n✅ All done! Figures saved to:', FIG_DIR)
