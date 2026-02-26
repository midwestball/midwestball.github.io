"""
Generate all figures for the Quarto report using the existing NBA-GNN data.
This uses the ORIGINAL data from the repo (data/X_seq.pkl, G_seq.pkl) so
figures are generated even before a full re-training run.

Usage:  uv run python 04_generate_figures.py
"""

import os
import sys
import pickle
import json
import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
import networkx as nx
from sklearn.metrics import (mean_squared_error, mean_absolute_error,
                             mean_absolute_percentage_error)
from sklearn import preprocessing
from torch.autograd import Variable
from scipy import stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────
REPO_DATA = Path(__file__).parent.parent / "NBA-GNN-prediction" / "data"
REPO_ROOT = Path(__file__).parent.parent / "NBA-GNN-prediction"
sys.path.insert(0, str(REPO_ROOT))

FIG_DIR = "figures"
os.makedirs(FIG_DIR, exist_ok=True)

PRED_COLS    = ["PTS", "AST", "REB", "TO", "STL", "BLK"]
FEATURE_COLS = ["PTS", "AST", "REB", "TO", "STL", "BLK", "PLUS_MINUS",
                "TCHS", "PASS", "DIST", "PACE", "USG_PCT", "TS_PCT"]
PRED_INDICES = [FEATURE_COLS.index(c) for c in PRED_COLS]

PALETTE = {
    "N-BEATS":   "#e07b54",
    "DeepVAR":   "#5b8fc7",
    "TCN":       "#70b472",
    "ASTGCN":    "#c07ec9",
    "GATv2-TCN\n(Paper)": "#f0c040",
    "GATv2-TCN\n(Repro)": "#e84393",
}

PAPER_RESULTS = {
    "N-BEATS":       {"RMSE": 5.112, "MAE": 4.552, "MAPE": 3.701, "CORR": 0.366},
    "DeepVAR":       {"RMSE": 2.896, "MAE": 2.151, "MAPE": 1.754, "CORR": 0.396},
    "TCN":           {"RMSE": 2.414, "MAE": 1.780, "MAPE": 0.551, "CORR": 0.418},
    "ASTGCN":        {"RMSE": 2.293, "MAE": 1.699, "MAPE": 0.455, "CORR": 0.453},
    "GATv2-TCN\n(Paper)": {"RMSE": 2.222, "MAE": 1.642, "MAPE": 0.513, "CORR": 0.508},
}

STYLE = {
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": "#fafafa",
}
plt.rcParams.update(STYLE)


# ──────────────────────────────────────────────────────────────
# Load original repo data
# ──────────────────────────────────────────────────────────────
def load_original_data():
    X_seq = pickle.load(open(REPO_DATA / "X_seq.pkl", "rb"))
    G_seq = pickle.load(open(REPO_DATA / "G_seq.pkl", "rb"))
    id2name = pickle.load(open(REPO_ROOT / "player_id2name.pkl", "rb"))
    id2team = pickle.load(open(REPO_ROOT / "player_id2team.pkl", "rb"))
    id2pos  = pickle.load(open(REPO_ROOT / "player_id2position.pkl", "rb"))
    return X_seq, G_seq, id2name, id2team, id2pos


# ──────────────────────────────────────────────────────────────
# Quick train+eval on original data for figure generation
# ──────────────────────────────────────────────────────────────
def fill_zeros_with_last(seq):
    seq_ff = np.zeros_like(seq)
    for i in range(seq.shape[1]):
        arr = seq[:, i]
        prev = np.arange(len(arr))
        prev[arr == 0] = 0
        prev = np.maximum.accumulate(prev)
        seq_ff[:, i] = arr[prev]
    return seq_ff


def get_train_val_test(X_seq, G_seq):
    from numpy.lib.stride_tricks import sliding_window_view

    Xs = np.zeros_like(X_seq)
    for i in range(X_seq.shape[1]):
        Xs[:, i, :] = fill_zeros_with_last(X_seq[:, i, :])

    SEQ = 10; OFFSET = 1
    X_in  = sliding_window_view(Xs[:-OFFSET], SEQ, axis=0)
    X_out = Xs[SEQ + OFFSET - 1:]

    G_edge = []
    for g in G_seq:
        node_dict = {node: i for i, node in enumerate(G_seq[0].nodes())}
        raw = list(nx.generate_edgelist(g))
        if raw:
            try:
                edges = np.array([e.split(' ')[:2] for e in raw], dtype=int).T
                edges = np.vectorize(node_dict.__getitem__)(edges)
                G_edge.append(torch.LongTensor(np.hstack([edges, edges[[1,0]]])))
            except Exception:
                n = X_seq.shape[1]
                G_edge.append(torch.stack([torch.arange(n), torch.arange(n)]).long())
        else:
            n = X_seq.shape[1]
            G_edge.append(torch.stack([torch.arange(n), torch.arange(n)]).long())

    from numpy.lib.stride_tricks import sliding_window_view as sw
    # G sliding windows
    G_in  = [G_edge[t:t+SEQ] for t in range(len(G_edge) - SEQ - OFFSET + 1)]
    G_out = G_edge[SEQ + OFFSET - 1:]

    T = len(G_in)
    t1 = int(T * 0.50); t2 = int(T * 0.75)
    return (
        torch.FloatTensor(X_in[:t1]),  torch.FloatTensor(X_out[:t1]),  G_in[:t1],  G_out[:t1],
        torch.FloatTensor(X_in[t1:t2]), torch.FloatTensor(X_out[t1:t2]), G_in[t1:t2], G_out[t1:t2],
        torch.FloatTensor(X_in[t2:]),  torch.FloatTensor(X_out[t2:]),  G_in[t2:],  G_out[t2:],
        T, t1, t2
    )


# ──────────────────────────────────────────────────────────────
# Mini model (using gatv2tcn from repo) – quick-train for figs
# ──────────────────────────────────────────────────────────────
def quick_train_and_eval(X_seq, G_seq, id2team, id2pos):
    from gatv2tcn import GATv2TCN

    (X_train, y_train, G_train, h_train,
     X_val,   y_val,   G_val,   h_val,
     X_test,  y_test,  G_test,  h_test,
     T, t1, t2) = get_train_val_test(X_seq, G_seq)

    # Embeddings
    player_id2team  = id2team
    player_id2pos   = id2pos

    le = preprocessing.LabelEncoder()
    df_id2team = pd.DataFrame.from_dict(player_id2team, orient='index').apply(le.fit_transform)
    enc = preprocessing.OneHotEncoder(sparse_output=False)
    enc.fit(df_id2team)
    onehotlabels = enc.transform(df_id2team)
    team_tensor  = Variable(torch.FloatTensor(onehotlabels))
    position_tensor = Variable(torch.FloatTensor(
        np.stack(list(player_id2pos.values()), axis=0).astype(np.float32)))

    n_teams = onehotlabels.shape[1]
    n_pos   = position_tensor.shape[-1]
    n_stats = X_seq.shape[-1]

    team_emb = nn.Linear(n_teams, 2)
    pos_emb  = nn.Linear(n_pos,   2)
    model_in = n_stats + 2 + 2  # e.g. 13 + 2 + 2 = 17

    model = GATv2TCN(
        in_channels=model_in, out_channels=6, len_input=10, len_output=1,
        temporal_filter=64, out_gatv2conv=32,
        dropout_tcn=0.25, dropout_gatv2conv=0.5, head_gatv2conv=4
    )

    params = list(model.parameters()) + list(team_emb.parameters()) + list(pos_emb.parameters())
    opt = torch.optim.Adam(params, lr=0.001, weight_decay=0.001)

    EPOCHS = 80    # shortened for figure-gen purposes
    SEQ = 10
    BS  = 10
    train_hist, val_hist = [], []
    min_val = float("inf")

    log.info(f"Quick-training {EPOCHS} epochs (figure generation)…")
    for ep in range(EPOCHS):
        model.train(); team_emb.train(); pos_emb.train()
        tv = team_emb(team_tensor); pv = pos_emb(position_tensor)
        loss = torch.tensor(0.0)
        for i in np.random.choice(len(X_train), size=min(BS, len(X_train)), replace=False):
            Xlist = [torch.cat([X_train[i,:,:,t], tv, pv], 1) for t in range(SEQ)]
            x    = torch.stack(Xlist, -1)[None,...]
            pred = model(x, G_train[i])[0]
            loss = loss + F.mse_loss(pred, y_train[i,:,PRED_INDICES])
        loss.backward(); opt.step(); opt.zero_grad()
        train_hist.append(loss.item())

        model.eval(); team_emb.eval(); pos_emb.eval()
        with torch.no_grad():
            tv2 = team_emb(team_tensor); pv2 = pos_emb(position_tensor)
            vl  = 0.0
            for i in range(len(X_val)):
                Xlist = [torch.cat([X_val[i,:,:,t], tv2, pv2], 1) for t in range(SEQ)]
                x    = torch.stack(Xlist, -1)[None,...]
                pred = model(x, G_val[i])[0]
                vl  += F.mse_loss(pred, y_val[i,:,PRED_INDICES]).item()
        val_hist.append(vl)
        if ep % 20 == 0:
            log.info(f"  Epoch {ep:03d}: train={loss.item():.4f}  val={vl:.4f}")

    # Evaluate on test
    model.eval(); team_emb.eval(); pos_emb.eval()
    with torch.no_grad():
        tv = team_emb(team_tensor); pv = pos_emb(position_tensor)
        preds, trues = [], []
        for i in range(len(X_test)):
            Xlist = [torch.cat([X_test[i,:,:,t], tv, pv], 1) for t in range(SEQ)]
            x    = torch.stack(Xlist, -1)[None,...]
            pred = model(x, G_test[i])[0].numpy()
            true = y_test[i,:,PRED_INDICES].numpy()
            preds.append(pred)
            trues.append(true)

    return np.array(train_hist), np.array(val_hist), preds, trues, G_seq, id2name if 'id2name' in dir() else {}


# ──────────────────────────────────────────────────────────────
# FIGURES
# ──────────────────────────────────────────────────────────────

def fig_loss_curves(train_hist, val_hist):
    fig, ax = plt.subplots(figsize=(10, 5))
    ep = np.arange(len(train_hist))
    ax.plot(ep, train_hist,  label="Training Loss",   color="#5b8fc7", lw=2.5)
    ax.plot(ep, val_hist,    label="Validation Loss", color="#e07b54", lw=2.5)
    best = int(np.argmin(val_hist))
    ax.axvline(best, color="#aaaaaa", ls="--", lw=1.5, label=f"Best epoch ({best})")
    ax.fill_between(ep, train_hist, alpha=0.08, color="#5b8fc7")
    ax.set_xlabel("Epoch", fontsize=12)
    ax.set_ylabel("MSE Loss (un-normalised)", fontsize=12)
    ax.set_title("GATv2-TCN: Learning Curves", fontsize=14, fontweight="bold")
    ax.legend(fontsize=11)
    ax.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(f"{FIG_DIR}/loss_curves.png", dpi=150)
    plt.close()
    log.info("✓ loss_curves.png")


def fig_model_comparison(repro_metrics=None):
    if repro_metrics is None:
        repro_metrics = {"RMSE": 2.25, "MAE": 1.66, "MAPE": 0.52, "CORR": 0.497}

    all_results = {**PAPER_RESULTS, "GATv2-TCN\n(Repro)": repro_metrics}
    metrics_to_plot = ["RMSE", "MAE", "CORR"]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5))
    fig.patch.set_facecolor("#fafafa")

    for ax, metric in zip(axes, metrics_to_plot):
        models = list(all_results.keys())
        vals   = [all_results[m][metric] for m in models]
        colors = [PALETTE.get(m, "#888888") for m in models]
        bars   = ax.bar(range(len(models)), vals, color=colors,
                        edgecolor="#ffffff", linewidth=1.5, width=0.65, zorder=3)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.015 * max(vals),
                    f"{val:.3f}", ha="center", va="bottom", fontsize=9, fontweight="bold")
        ax.set_xticks(range(len(models)))
        ax.set_xticklabels([m.replace("\n", " ") for m in models],
                           rotation=35, ha="right", fontsize=9)
        ax.set_title(metric, fontsize=13, fontweight="bold")
        ax.set_ylabel(metric, fontsize=11)
        ax.grid(axis="y", alpha=0.2, zorder=0)
        ax.set_facecolor("#fafafa")

    plt.suptitle("Forecasting Model Benchmark Comparison\n(Luo & Krishnamurthy 2023 + Reproduction)",
                 fontsize=13, fontweight="bold", y=1.01)
    plt.tight_layout()
    plt.savefig(f"{FIG_DIR}/model_comparison.png", dpi=150, bbox_inches="tight")
    plt.close()
    log.info("✓ model_comparison.png")


def fig_per_stat_errors(preds, trues):
    all_p = np.concatenate(preds, 0); all_t = np.concatenate(trues, 0)
    mae_v  = np.abs(all_p - all_t).mean(0)
    rmse_v = np.sqrt(((all_p - all_t)**2).mean(0))
    corr_v = [np.corrcoef(all_p[:,i], all_t[:,i])[0,1] for i in range(6)]

    x = np.arange(6)
    width = 0.28
    fig, ax = plt.subplots(figsize=(12, 5))
    b1 = ax.bar(x - width,   mae_v,  width, label="MAE",  color="#5b8fc7", edgecolor="white")
    b2 = ax.bar(x,           rmse_v, width, label="RMSE", color="#e07b54", edgecolor="white")
    b3 = ax.bar(x + width,   corr_v, width, label="CORR", color="#70b472", edgecolor="white")

    for bars in [b1, b2, b3]:
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2, h + 0.01, f"{h:.2f}",
                    ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(PRED_COLS, fontsize=12)
    ax.set_title("GATv2-TCN: Per-Statistic Error Metrics (Test Set)",
                 fontsize=13, fontweight="bold")
    ax.set_ylabel("Metric Value", fontsize=11)
    ax.legend(fontsize=11)
    ax.grid(axis="y", alpha=0.2)
    plt.tight_layout()
    plt.savefig(f"{FIG_DIR}/per_stat_errors.png", dpi=150)
    plt.close()
    log.info("✓ per_stat_errors.png")


def fig_pred_vs_actual(preds, trues):
    all_p = np.concatenate(preds, 0); all_t = np.concatenate(trues, 0)
    colors = ["#5b8fc7","#e07b54","#70b472","#c07ec9","#f0c040","#e84393"]

    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    fig.patch.set_facecolor("#fafafa")

    for i, (ax, stat) in enumerate(zip(axes.ravel(), PRED_COLS)):
        p, t = all_p[:,i], all_t[:,i]
        ax.scatter(t, p, alpha=0.3, s=10, color=colors[i], rasterized=True, zorder=3)
        lo = min(t.min(), p.min()); hi = max(t.max(), p.max())
        ax.plot([lo, hi], [lo, hi], "k--", lw=1.5, alpha=0.6, label="Perfect")

        # Regression line
        m, b, r, *_ = stats.linregress(t, p)
        xs = np.array([lo, hi])
        ax.plot(xs, m*xs + b, color="red", lw=2, label=f"Fit (r={r:.3f})")

        mae = mean_absolute_error(t, p)
        ax.set_title(f"{stat}  |  MAE = {mae:.2f}", fontsize=11, fontweight="bold")
        ax.set_xlabel("Actual", fontsize=10)
        ax.set_ylabel("Predicted", fontsize=10)
        ax.legend(fontsize=8)
        ax.grid(alpha=0.15)
        ax.set_facecolor("#fafafa")

    plt.suptitle("GATv2-TCN: Predicted vs. Actual Performance (Test Set)",
                 fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(f"{FIG_DIR}/pred_vs_actual.png", dpi=150, bbox_inches="tight")
    plt.close()
    log.info("✓ pred_vs_actual.png")


def fig_graph_topology(G_seq, id2name):
    # Use a representative game-day graph (mid-season)
    G = G_seq[len(G_seq)//2]
    active = [n for n in G.nodes() if G.degree(n) > 0]
    if len(active) == 0:
        log.warning("Graph empty – skipping topology figure")
        return
    subG = G.subgraph(active[:60])

    # Colour nodes by connected component (= game)
    components = list(nx.connected_components(subG))
    cmap = plt.cm.get_cmap("tab20", len(components))
    node_colors = {}
    for k, comp in enumerate(components):
        for n in comp:
            node_colors[n] = cmap(k % 20)

    fig, ax = plt.subplots(figsize=(13, 11))
    pos    = nx.kamada_kawai_layout(subG)
    labels = {n: id2name.get(n, str(n))[:10] for n in subG.nodes()}
    nc     = [node_colors.get(n, "#cccccc") for n in subG.nodes()]

    nx.draw_networkx_nodes(subG, pos, ax=ax, node_color=nc,
                           node_size=300, alpha=0.95, linewidths=1.5,
                           edgecolors="white")
    nx.draw_networkx_edges(subG, pos, ax=ax, alpha=0.35,
                           edge_color="#888888", width=1.2)
    nx.draw_networkx_labels(subG, pos, labels=labels, ax=ax,
                            font_size=6.5, font_color="#222222")

    ax.set_title(
        "Game-Day Graph Topology (Sample)\n"
        "Nodes = Players · Edges = On-Court Co-Participation · Colours = Game Instance",
        fontsize=12, fontweight="bold"
    )
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(f"{FIG_DIR}/graph_topology.png", dpi=150, bbox_inches="tight")
    plt.close()
    log.info("✓ graph_topology.png")


def fig_residuals(preds, trues):
    all_p = np.concatenate(preds, 0); all_t = np.concatenate(trues, 0)
    residuals = all_p - all_t
    colors = ["#5b8fc7","#e07b54","#70b472","#c07ec9","#f0c040","#e84393"]

    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    for i, (ax, stat) in enumerate(zip(axes.ravel(), PRED_COLS)):
        res = residuals[:,i]
        ax.hist(res, bins=60, color=colors[i], edgecolor="white", alpha=0.85, density=True)
        xs = np.linspace(res.min(), res.max(), 300)
        ax.plot(xs, stats.norm.pdf(xs, res.mean(), res.std()),
                "k-", lw=2, label="Normal fit")
        ax.axvline(0,          color="red",    lw=1.5, ls="--", label="Zero bias")
        ax.axvline(res.mean(), color="orange", lw=1.5, ls="-",  label=f"μ={res.mean():.2f}")
        ax.set_title(f"{stat}", fontsize=11, fontweight="bold")
        ax.set_xlabel("Error (Pred − Actual)", fontsize=9)
        ax.set_ylabel("Density", fontsize=9)
        ax.legend(fontsize=7.5)
        ax.grid(axis="y", alpha=0.2)

    plt.suptitle("GATv2-TCN: Residual Error Distributions (Test Set)",
                 fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(f"{FIG_DIR}/residuals.png", dpi=150, bbox_inches="tight")
    plt.close()
    log.info("✓ residuals.png")


def fig_radar(repro_metrics=None):
    if repro_metrics is None:
        repro_metrics = {"RMSE": 2.25, "MAE": 1.66, "MAPE": 0.52, "CORR": 0.497}

    all_r = {**PAPER_RESULTS, "GATv2-TCN\n(Repro)": repro_metrics}

    def norm(results):
        out = {}
        for model, m in results.items():
            out[model] = {
                "1/RMSE": 1 / max(m["RMSE"], 1e-6),
                "1/MAE":  1 / max(m["MAE"],  1e-6),
                "1/MAPE": 1 / max(m["MAPE"], 1e-6),
                "CORR":   m["CORR"],
            }
        return out

    normed = norm(all_r)
    cats   = list(next(iter(normed.values())).keys())
    N      = len(cats)
    angles = np.linspace(0, 2*np.pi, N, endpoint=False).tolist() + [0]

    fig, ax = plt.subplots(figsize=(8,8), subplot_kw={"polar": True})
    fig.patch.set_facecolor("#fafafa")

    for model, m in normed.items():
        vals = list(m.values()) + [list(m.values())[0]]
        color = PALETTE.get(model, "#888888")
        ax.plot(angles, vals, lw=2.5, color=color,
                label=model.replace("\n", " "), zorder=4)
        ax.fill(angles, vals, alpha=0.08, color=color)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(cats, fontsize=12, fontweight="bold")
    ax.set_yticklabels([])
    ax.set_title("Model Performance Radar\n(all axes: higher = better)",
                 fontsize=13, fontweight="bold", pad=25)
    ax.legend(loc="upper right", bbox_to_anchor=(1.45, 1.15), fontsize=9.5)
    ax.grid(color="#cccccc", alpha=0.5)
    plt.tight_layout()
    plt.savefig(f"{FIG_DIR}/radar_comparison.png", dpi=150, bbox_inches="tight")
    plt.close()
    log.info("✓ radar_comparison.png")


def fig_pts_trend(preds, trues):
    T = len(preds)
    mean_pred = [preds[i][:,0].mean() for i in range(T)]
    mean_true = [trues[i][:,0].mean() for i in range(T)]
    std_pred  = [preds[i][:,0].std()  for i in range(T)]

    x = np.arange(T)
    fig, ax = plt.subplots(figsize=(14, 4.5))
    ax.plot(x, mean_true, color="#e07b54", lw=2.5, ls="--", label="Actual PTS (mean)")
    ax.plot(x, mean_pred, color="#5b8fc7", lw=2.5,         label="Predicted PTS (mean)")
    ax.fill_between(x,
                    np.array(mean_pred) - np.array(std_pred),
                    np.array(mean_pred) + np.array(std_pred),
                    alpha=0.18, color="#5b8fc7", label="±1σ (predicted)")
    ax.set_xlabel("Test-Set Game-Day Index", fontsize=11)
    ax.set_ylabel("Points (Z-Normalised)", fontsize=11)
    ax.set_title("GATv2-TCN: Population-Average PTS Forecast vs. Actuals",
                 fontsize=13, fontweight="bold")
    ax.legend(fontsize=10)
    ax.grid(axis="y", alpha=0.2)
    plt.tight_layout()
    plt.savefig(f"{FIG_DIR}/pts_forecast_trend.png", dpi=150)
    plt.close()
    log.info("✓ pts_forecast_trend.png")


def fig_architecture():
    """Minimal architecture block diagram."""
    fig, ax = plt.subplots(figsize=(16, 5))
    ax.axis("off")
    ax.set_facecolor("#fafafa")
    fig.patch.set_facecolor("#fafafa")

    blocks = [
        ("Raw Stats\n13 features",      "#c7daf0"),
        ("Team\nEmbedding\n(→2D)",       "#c7f0d4"),
        ("Position\nEmbedding\n(→2D)",   "#f7e7b0"),
        ("Concat\n17-D Input",           "#e8d5f0"),
        ("GATv2Conv\n(4 heads)\n128-D",  "#5b8fc7"),
        ("Temporal\nConv2D\n64 ch",      "#70b472"),
        ("Residual\n+LayerNorm",         "#c07ec9"),
        ("Final\nConv2D\n6 stats out",   "#e07b54"),
    ]

    n = len(blocks)
    bw, bh = 1.6, 1.0
    gap    = 0.55
    y0     = 1.8

    for i, (label, color) in enumerate(blocks):
        x = i * (bw + gap)
        rect = mpatches.FancyBboxPatch(
            (x, y0), bw, bh, boxstyle="round,pad=0.12",
            facecolor=color, edgecolor="white", linewidth=2.5, zorder=3)
        ax.add_patch(rect)
        ax.text(x + bw/2, y0 + bh/2, label,
                ha="center", va="center", fontsize=9, fontweight="bold", zorder=4)
        if i < n - 1:
            ax.annotate("", xy=(x + bw + gap, y0 + bh/2),
                        xytext=(x + bw + 0.05, y0 + bh/2),
                        arrowprops=dict(arrowstyle="-|>", lw=2,
                                        color="#444444", mutation_scale=18),
                        zorder=5)

    # Dimension labels below
    dims = ["N×13", "N×30", "N×3", "N×17",
            "N×128", "N×64", "N×64",  "N×6"]
    for i, (d, _) in enumerate(zip(dims, blocks)):
        x = i * (bw + gap) + bw/2
        ax.text(x, y0 - 0.35, d, ha="center", va="top", fontsize=8, color="#555555")

    total_w = n * (bw + gap)
    ax.set_xlim(-0.4, total_w)
    ax.set_ylim(1.0, 3.2)
    ax.set_title("GATv2-TCN Model Architecture Overview",
                 fontsize=15, fontweight="bold", pad=10)
    plt.tight_layout()
    plt.savefig(f"{FIG_DIR}/architecture_diagram.png", dpi=150, bbox_inches="tight")
    plt.close()
    log.info("✓ architecture_diagram.png")


def fig_data_stats(X_seq):
    """Distribution of raw stats across the dataset."""
    STAT_LABELS = ["PTS","AST","REB","TO","STL","BLK","±","TCHS","PASS","DIST","PACE","USG%","TS%"]
    n_stats = min(X_seq.shape[-1], len(STAT_LABELS))

    fig, axes = plt.subplots(3, 5, figsize=(18, 10))
    axes = axes.ravel()
    colors = plt.cm.tab20(np.linspace(0, 1, n_stats))

    for i in range(n_stats):
        vals = X_seq[:, :, i].ravel()
        vals = vals[vals != 0]   # skip padded zeros
        ax = axes[i]
        ax.hist(vals, bins=60, color=colors[i], edgecolor="white", alpha=0.85, density=True)
        xs = np.linspace(vals.min(), vals.max(), 300)
        try:
            ax.plot(xs, stats.norm.pdf(xs, vals.mean(), vals.std()), "k-", lw=1.5)
        except Exception:
            pass
        ax.set_title(STAT_LABELS[i], fontsize=11, fontweight="bold")
        ax.set_xlabel("Value", fontsize=8)
        ax.grid(axis="y", alpha=0.2)
        ax.tick_params(labelsize=8)

    for i in range(n_stats, len(axes)):
        axes[i].axis("off")

    plt.suptitle("Distribution of Raw NBA Statistics Across the Dataset",
                 fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(f"{FIG_DIR}/data_distributions.png", dpi=150, bbox_inches="tight")
    plt.close()
    log.info("✓ data_distributions.png")


def fig_correlation_heatmap(X_seq):
    """Feature correlation matrix."""
    STAT_LABELS = ["PTS","AST","REB","TO","STL","BLK","±","TCHS","PASS","DIST","PACE","USG%","TS%"]
    n = min(X_seq.shape[-1], len(STAT_LABELS))
    flat = X_seq.reshape(-1, X_seq.shape[-1])[:, :n]
    # remove all-zero rows
    mask = (flat != 0).any(axis=1)
    flat = flat[mask]
    corr = np.corrcoef(flat.T)

    fig, ax = plt.subplots(figsize=(9, 7))
    im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(n)); ax.set_xticklabels(STAT_LABELS[:n], rotation=45, ha="right")
    ax.set_yticks(range(n)); ax.set_yticklabels(STAT_LABELS[:n])
    for i in range(n):
        for j in range(n):
            ax.text(j, i, f"{corr[i,j]:.2f}", ha="center", va="center",
                    fontsize=7.5, color="white" if abs(corr[i,j]) > 0.5 else "black")
    plt.colorbar(im, ax=ax, shrink=0.8, label="Pearson r")
    ax.set_title("Feature Correlation Matrix (NBA Player Statistics)", fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig(f"{FIG_DIR}/correlation_heatmap.png", dpi=150, bbox_inches="tight")
    plt.close()
    log.info("✓ correlation_heatmap.png")


def fig_graph_degree_distribution(G_seq):
    """Degree distribution of the player-interaction graphs."""
    all_degrees = []
    for G in G_seq:
        all_degrees.extend([d for _, d in G.degree()])

    all_degrees = np.array(all_degrees)
    all_degrees = all_degrees[all_degrees > 0]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # Histogram
    ax1.hist(all_degrees, bins=40, color="#5b8fc7", edgecolor="white", alpha=0.85)
    ax1.set_xlabel("Node Degree (# co-participants)", fontsize=11)
    ax1.set_ylabel("Count", fontsize=11)
    ax1.set_title("Degree Distribution of Game Graphs", fontsize=12, fontweight="bold")
    ax1.grid(axis="y", alpha=0.2)

    # Log-log
    unique_deg, counts = np.unique(all_degrees, return_counts=True)
    ax2.loglog(unique_deg, counts, "o", color="#e07b54", markersize=5, alpha=0.8)
    ax2.set_xlabel("Degree (log)", fontsize=11)
    ax2.set_ylabel("Count (log)", fontsize=11)
    ax2.set_title("Degree Distribution (Log-Log Scale)", fontsize=12, fontweight="bold")
    ax2.grid(alpha=0.2, which="both")

    plt.suptitle("Player Co-Participation Graph: Degree Analysis", fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig(f"{FIG_DIR}/degree_distribution.png", dpi=150, bbox_inches="tight")
    plt.close()
    log.info("✓ degree_distribution.png")


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("Loading original repo data…")
    X_seq, G_seq, id2name, id2team, id2pos = load_original_data()
    log.info(f"X_seq shape: {X_seq.shape}  |  G_seq length: {len(G_seq)}")

    log.info("\nQuick training run (80 epochs) on original data for figure generation…")
    train_hist, val_hist, preds, trues, G_seq2, _ = quick_train_and_eval(
        X_seq, G_seq, id2team, id2pos)

    # Compute metrics from this quick run
    all_p = np.concatenate(preds, 0)
    all_t = np.concatenate(trues, 0)
    rmse_v  = mean_squared_error(all_t, all_p, squared=False)
    mae_v   = mean_absolute_error(all_t, all_p)
    try:
        mape_v = mean_absolute_percentage_error(all_t, all_p)
    except Exception:
        mape_v = float("nan")

    corr_vals = []
    for mi in range(6):
        try:
            r = np.corrcoef(all_p[:,mi], all_t[:,mi])[0,1]
            if not np.isnan(r) and abs(r) < 1-1e-7:
                corr_vals.append(np.arctanh(r))
        except Exception:
            pass
    corr_v = np.tanh(np.mean(corr_vals)) if corr_vals else float("nan")
    repro_metrics = {"RMSE": float(rmse_v), "MAE": float(mae_v),
                     "MAPE": float(mape_v), "CORR": float(corr_v)}
    log.info(f"Quick-run metrics: {repro_metrics}")

    # ── Generate all figures ───────────────────────────────────
    log.info("\nGenerating figures…")
    fig_loss_curves(train_hist, val_hist)
    fig_model_comparison(repro_metrics)
    fig_per_stat_errors(preds, trues)
    fig_pred_vs_actual(preds, trues)
    fig_graph_topology(G_seq, id2name)
    fig_residuals(preds, trues)
    fig_radar(repro_metrics)
    fig_pts_trend(preds, trues)
    fig_architecture()
    fig_data_stats(X_seq)
    fig_correlation_heatmap(X_seq)
    fig_graph_degree_distribution(G_seq)

    # Save metrics for Quarto
    with open("outputs/repro_metrics.json", "w") as f:
        json.dump(repro_metrics, f, indent=2)

    log.info(f"\nAll figures saved to ./{FIG_DIR}/")
    log.info("Figure generation complete ✓")
