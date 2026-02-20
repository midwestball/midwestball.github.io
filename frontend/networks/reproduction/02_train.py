"""
Phase 4 & 5: GATv2-GCN Model Definition and Training
=====================================================
Faithful reproduction of the GATv2TCN architecture described in
Luo & Krishnamurthy (2023) "NBA Player Performance Prediction via
Graph Attention Networks with Temporal Convolutions".

Architecture:
  • Team embedding  : Linear(30→2)
  • Position embedding: Linear(3→2)
  • Input dim        : 13 (stats) + 2 (team) + 2 (pos) = 17
  • GATv2Conv        : in=17, out=32, heads=4  → 128-dim spatial rep
  • Conv2d (temporal): in=128, out=64, kernel(1,1)
  • Residual Conv2d  : in=17, out=64
  • LayerNorm + ReLU
  • Final Conv2d     : in=10 (seq_len), out=6 (predictions)

Training split: 50% train / 25% val / 25% test (chronological)
Optimiser     : Adam(lr=0.001, weight_decay=0.001)
Loss          : MSE
Epochs        : 300
Batch size    : 20 (random sample of training days per epoch)

Usage:
  uv run python 02_train.py
"""

import copy
import os
import pickle
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable
from sklearn import preprocessing
import networkx as nx
from tqdm import tqdm

# ── Local model import ────────────────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "NBA-GNN-prediction"))
from gatv2tcn import GATv2TCN   # noqa: E402

# ──────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

DATA_DIR  = "data"
MODEL_DIR = "model/gatv2tcn-repro"
os.makedirs(MODEL_DIR, exist_ok=True)

SEQ_LENGTH = 10
OFFSET     = 1
EPOCHS     = 300
BATCH_SIZE = 20
LR         = 0.001
WEIGHT_DECAY = 0.001

FEATURE_COLS = ["PTS", "AST", "REB", "TO", "STL", "BLK", "PLUS_MINUS",
                "TCHS", "PASS", "DIST", "PACE", "USG_PCT", "TS_PCT"]
PREDICTION_COLS = ["PTS", "AST", "REB", "TO", "STL", "BLK"]
PRED_INDICES = [FEATURE_COLS.index(c) for c in PREDICTION_COLS]


# ──────────────────────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────────────────────
def fill_zeros_with_last(seq: np.ndarray) -> np.ndarray:
    """Forward-fill zero entries along axis-0 for each column."""
    seq_ff = np.zeros_like(seq)
    for i in range(seq.shape[1]):
        arr = seq[:, i]
        prev = np.arange(len(arr))
        prev[arr == 0] = 0
        prev = np.maximum.accumulate(prev)
        seq_ff[:, i] = arr[prev]
    return seq_ff


def sliding_window(arr: np.ndarray, window: int, offset: int = 1):
    """Create (X, y) sliding-window pairs along axis-0."""
    from numpy.lib.stride_tricks import sliding_window_view
    if offset == 0:
        x = sliding_window_view(arr, window, axis=0)
    else:
        x = sliding_window_view(arr[:-offset], window, axis=0)
    y = arr[window + offset - 1:]
    return x, y


def graphs_to_edge_tensors(G_seq: list[nx.Graph], player_ids: list) -> list[torch.LongTensor]:
    """Convert networkx graph list to PyG edge_index tensors."""
    node_dict = {pid: i for i, pid in enumerate(player_ids)}
    tensors = []
    for G in G_seq:
        edges = list(G.edges())
        if not edges:
            # Empty graph – no edges; use self-loops as placeholder
            n = len(player_ids)
            ei = torch.stack([torch.arange(n), torch.arange(n)], dim=0).long()
        else:
            src, dst = zip(*edges)
            src = [node_dict.get(s, 0) for s in src]
            dst = [node_dict.get(d, 0) for d in dst]
            # Undirected: add both directions
            src_t = torch.LongTensor(src + dst)
            dst_t = torch.LongTensor(dst + src)
            ei = torch.stack([src_t, dst_t], dim=0)
        tensors.append(ei)
    return tensors


# ──────────────────────────────────────────────────────────────
# Dataset construction
# ──────────────────────────────────────────────────────────────
def create_dataset():
    log.info("Loading artefacts…")
    X_seq         = pickle.load(open(f"{DATA_DIR}/X_seq.pkl",         "rb"))
    G_seq_graphs  = pickle.load(open(f"{DATA_DIR}/G_seq.pkl",         "rb"))
    player_ids    = pickle.load(open(f"{DATA_DIR}/player_ids.pkl",    "rb"))
    player_id2team = pickle.load(open(f"{DATA_DIR}/player_id2team.pkl", "rb"))
    player_id2pos  = pickle.load(open(f"{DATA_DIR}/player_id2position.pkl", "rb"))

    N = len(player_ids)
    log.info(f"  Players: {N},  Days: {X_seq.shape[0]}")

    # ── Team embedding tensor ─────────────────────────────────
    # Encode team as integer then one-hot
    pid2team_int = {pid: player_id2team.get(pid, 0) for pid in player_ids}
    n_teams = max(pid2team_int.values()) + 1
    team_onehot = np.zeros((N, n_teams), dtype=np.float32)
    for idx, pid in enumerate(player_ids):
        t = pid2team_int[pid]
        team_onehot[idx, t] = 1.0
    team_tensor = Variable(torch.FloatTensor(team_onehot))

    # ── Position embedding tensor ─────────────────────────────
    pos_arrays = []
    for pid in player_ids:
        pos = player_id2pos.get(pid, np.array([0, 0, 0]))
        pos_arrays.append(np.array(pos, dtype=np.float32))
    position_tensor = Variable(torch.FloatTensor(np.stack(pos_arrays)))

    # ── Forward-fill zeros in X_seq ──────────────────────────
    Xs = np.zeros_like(X_seq)
    for i in range(X_seq.shape[1]):
        Xs[:, i, :] = fill_zeros_with_last(X_seq[:, i, :])

    # ── Build edge tensor list from graphs ───────────────────
    G_tensors = graphs_to_edge_tensors(G_seq_graphs, player_ids)

    # ── Sliding window ────────────────────────────────────────
    X_in, X_out = sliding_window(Xs,        SEQ_LENGTH, OFFSET)
    G_in, G_out = sliding_window(G_tensors, SEQ_LENGTH, OFFSET)
    X_in  = Variable(torch.FloatTensor(X_in))
    X_out = Variable(torch.FloatTensor(X_out))

    # ── Chronological 50/25/25 split ─────────────────────────
    T = X_in.shape[0]
    t1 = int(T * 0.50)
    t2 = int(T * 0.75)
    log.info(f"  Sequence length: {T}  →  train:{t1}  val:{t2-t1}  test:{T-t2}")

    splits = {
        "train": (X_in[:t1],     X_out[:t1],     G_in[:t1],     G_out[:t1]),
        "val":   (X_in[t1:t2],   X_out[t1:t2],   G_in[t1:t2],  G_out[t1:t2]),
        "test":  (X_in[t2:],     X_out[t2:],     G_in[t2:],    G_out[t2:]),
    }
    return splits, team_tensor, position_tensor, n_teams


# ──────────────────────────────────────────────────────────────
# Build model
# ──────────────────────────────────────────────────────────────
def build_model(n_teams: int, n_positions: int = 3):
    team_emb_in  = 2  # projected to 2-D
    pos_emb_in   = 2
    model_in     = len(FEATURE_COLS) + team_emb_in + pos_emb_in  # 17

    team_embedding     = nn.Linear(n_teams,     team_emb_in)
    position_embedding = nn.Linear(n_positions, pos_emb_in)

    model = GATv2TCN(
        in_channels     = model_in,
        out_channels    = 6,
        len_input       = SEQ_LENGTH,
        len_output      = 1,
        temporal_filter = 64,
        out_gatv2conv   = 32,
        dropout_tcn     = 0.25,
        dropout_gatv2conv = 0.5,
        head_gatv2conv  = 4,
    )
    return model, team_embedding, position_embedding


# ──────────────────────────────────────────────────────────────
# Training loop
# ──────────────────────────────────────────────────────────────
def train():
    splits, team_tensor, position_tensor, n_teams = create_dataset()

    X_train, y_train, G_train, h_train = splits["train"]
    X_val,   y_val,   G_val,   h_val   = splits["val"]
    X_test,  y_test,  G_test,  h_test  = splits["test"]

    n_positions = position_tensor.shape[-1]
    model, team_emb, pos_emb = build_model(n_teams, n_positions)

    parameters = (list(model.parameters()) +
                  list(team_emb.parameters()) +
                  list(pos_emb.parameters()))
    optimizer = torch.optim.Adam(parameters, lr=LR, weight_decay=WEIGHT_DECAY)

    train_loss_hist = []
    val_loss_hist   = []
    min_val_loss    = float("inf")
    min_val_epoch   = -1

    for epoch in tqdm(range(EPOCHS), desc="Training"):
        # ─── Training step ────────────────────────────────────
        model.train()
        team_emb.train()
        pos_emb.train()

        team_vec = team_emb(team_tensor)
        pos_vec  = pos_emb(position_tensor)

        train_loss = torch.tensor(0.0)
        batch_idx = np.random.choice(X_train.shape[0], size=BATCH_SIZE, replace=False)
        for i in batch_idx:
            mask = h_train[i].unique()
            X_list, G_list = [], []
            for t in range(SEQ_LENGTH):
                x_t = torch.cat([X_train[i, :, :, t], team_vec, pos_vec], dim=1)
                X_list.append(x_t)
                G_list.append(G_train[i][t])
            x = torch.stack(X_list, dim=-1)[None, ...]  # (1, N, F, T)
            pred = model(x, G_list)[0]                  # (N, 6)
            loss = F.mse_loss(pred[mask], y_train[i][mask][:, PRED_INDICES])
            train_loss = train_loss + loss

        train_loss.backward()
        optimizer.step()
        optimizer.zero_grad()

        # ─── Validation step ──────────────────────────────────
        model.eval()
        team_emb.eval()
        pos_emb.eval()
        with torch.no_grad():
            team_vec = team_emb(team_tensor)
            pos_vec  = pos_emb(position_tensor)

            val_loss = torch.tensor(0.0)
            for i in range(X_val.shape[0]):
                mask = h_val[i].unique()
                X_list, G_list = [], []
                for t in range(SEQ_LENGTH):
                    x_t = torch.cat([X_val[i, :, :, t], team_vec, pos_vec], dim=1)
                    X_list.append(x_t)
                    G_list.append(G_val[i][t])
                x = torch.stack(X_list, dim=-1)[None, ...]
                pred = model(x, G_list)[0]
                val_loss = val_loss + F.mse_loss(pred[mask], y_val[i][mask][:, PRED_INDICES])

        tl, vl = train_loss.item(), val_loss.item()
        train_loss_hist.append(tl)
        val_loss_hist.append(vl)

        if vl < min_val_loss:
            log.info(f"Epoch {epoch:03d} | val {vl:.4f} ↓ (was {min_val_loss:.4f}) – saving")
            min_val_loss  = vl
            min_val_epoch = epoch
            torch.save(model.state_dict(),    f"{MODEL_DIR}/model.pth")
            torch.save(team_emb.state_dict(), f"{MODEL_DIR}/team_emb.pth")
            torch.save(pos_emb.state_dict(),  f"{MODEL_DIR}/pos_emb.pth")

        if epoch % 20 == 0:
            log.info(f"Epoch {epoch:03d} | train {tl:.4f} | val {vl:.4f}")

    # Save loss history
    np.save(f"{MODEL_DIR}/train_loss.npy", np.array(train_loss_hist))
    np.save(f"{MODEL_DIR}/val_loss.npy",   np.array(val_loss_hist))
    log.info(f"\nBest val loss: {min_val_loss:.4f} at epoch {min_val_epoch}")
    log.info("Training complete ✓")

    return splits, team_tensor, position_tensor, n_teams


# ──────────────────────────────────────────────────────────────
# Test Evaluation
# ──────────────────────────────────────────────────────────────
def evaluate(splits, team_tensor, position_tensor, n_teams):
    from sklearn.metrics import (mean_squared_error, mean_absolute_error,
                                 mean_absolute_percentage_error)

    X_test, y_test, G_test, h_test = splits["test"]
    n_positions = position_tensor.shape[-1]
    model, team_emb, pos_emb = build_model(n_teams, n_positions)

    model.load_state_dict(torch.load(f"{MODEL_DIR}/model.pth",    map_location="cpu"))
    team_emb.load_state_dict(torch.load(f"{MODEL_DIR}/team_emb.pth", map_location="cpu"))
    pos_emb.load_state_dict(torch.load(f"{MODEL_DIR}/pos_emb.pth",  map_location="cpu"))
    model.eval()
    team_emb.eval()
    pos_emb.eval()

    with torch.no_grad():
        team_vec = team_emb(team_tensor)
        pos_vec  = pos_emb(position_tensor)

        all_preds, all_trues = [], []
        rmse_sum = mae_sum = mape_sum = corr_sum = 0.0

        for i in range(X_test.shape[0]):
            mask = h_test[i].unique()
            X_list, G_list = [], []
            for t in range(SEQ_LENGTH):
                x_t = torch.cat([X_test[i, :, :, t], team_vec, pos_vec], dim=1)
                X_list.append(x_t)
                G_list.append(G_test[i][t])
            x    = torch.stack(X_list, dim=-1)[None, ...]
            pred = model(x, G_list)[0]
            p_np = pred[mask].numpy()
            t_np = y_test[i][mask][:, PRED_INDICES].numpy()

            all_preds.append(p_np)
            all_trues.append(t_np)

            rmse_sum += mean_squared_error(t_np, p_np, squared=False)
            mae_sum  += mean_absolute_error(t_np, p_np)
            try:
                mape_sum += mean_absolute_percentage_error(t_np, p_np)
            except Exception:
                pass

            # Fisher-z correlation across metrics
            corr_vals = []
            for mi in range(len(PREDICTION_COLS)):
                try:
                    r = np.corrcoef(p_np[:, mi], t_np[:, mi])[0, 1]
                    if not np.isnan(r) and abs(r) < 1 - 1e-7:
                        corr_vals.append(np.arctanh(r))
                except Exception:
                    pass
            if corr_vals:
                corr_sum += np.tanh(np.mean(corr_vals))

        n = X_test.shape[0]
        results = {
            "RMSE": rmse_sum / n,
            "MAE":  mae_sum  / n,
            "MAPE": mape_sum / n,
            "CORR": corr_sum / n,
        }

    log.info("\n── Test Metrics ──────────────────────────────────")
    for k, v in results.items():
        log.info(f"  {k}: {v:.4f}")

    import json
    with open(f"{MODEL_DIR}/test_metrics.json", "w") as f:
        json.dump(results, f, indent=2)

    # Save raw preds/trues for analysis
    all_preds_np = np.concatenate(all_preds, axis=0)
    all_trues_np = np.concatenate(all_trues, axis=0)
    np.save(f"{MODEL_DIR}/test_preds.npy", all_preds_np)
    np.save(f"{MODEL_DIR}/test_trues.npy", all_trues_np)

    log.info("Evaluation complete ✓")
    return results


# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    splits, team_tensor, position_tensor, n_teams = train()
    evaluate(splits, team_tensor, position_tensor, n_teams)
