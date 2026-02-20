# GATv2-GCN NBA Reproduction — Google Drive Upload Guide

## What's in this folder

```
upload_to_drive/
├── GATv2_GCN_NBA_Reproduction.ipynb   ← open this in Colab
└── NBA-GNN-prediction/
    ├── gatv2tcn.py          ← model definition (GATv2Conv, GATv2TCN, ASTGCN)
    ├── tcn.py               ← TCN stub (satisfies the import)
    ├── player_id2name.pkl   ← player ID → display name
    ├── player_id2team.pkl   ← player ID → team
    ├── player_id2position.pkl ← player ID → position one-hot
    └── data/
        ├── X_seq.pkl        ← (92, 582, 13) feature tensor (2022-23 season)
        └── G_seq.pkl        ← list of 92 networkx graphs (one per game-day)
```

## Upload steps

1. Upload this entire `upload_to_drive/` folder to your Google Drive as:
   `MyDrive/knowball/`
   so the final structure is:
   ```
   MyDrive/knowball/NBA-GNN-prediction/...
   MyDrive/knowball/GATv2_GCN_NBA_Reproduction.ipynb
   ```

2. Open `GATv2_GCN_NBA_Reproduction.ipynb` in Colab:
   - **Runtime → Change runtime type → A100 GPU**
   - Run all cells top-to-bottom

3. Cell **Section 4** will scrape additional seasons (2023-24 through 2025-26) if you want
   the extended dataset. Set `SEASONS` to only `[('2022-23', ...)]` for a quick run using
   the pre-packaged data.

4. All outputs (model checkpoints, figures, metrics JSON) are automatically written back
   to `MyDrive/knowball/outputs/` so nothing is lost if the runtime disconnects.

## Runtime estimates on A100

| Phase                  | Estimated time |
|------------------------|---------------|
| Install deps           | ~1 min        |
| Mount Drive            | ~30 sec       |
| Data acquisition (4 seasons) | 3–5 hrs  |
| Preprocessing          | ~2 min        |
| Training (300 epochs)  | ~15–25 min    |
| Evaluation + figures   | ~2 min        |
| **Total (with scraping)**    | ~4–6 hrs |
| **Total (pre-packaged data only)** | ~30 min |

## Paper reference

Luo, K. & Krishnamurthy, A. (2023).
*Predicting NBA Player Performance via Graph Attention Networks with Temporal Convolutions.*
Reported metrics on 2022-23 test set:

| Model        | RMSE  | MAE   | MAPE  | CORR  |
|-------------|-------|-------|-------|-------|
| N-BEATS      | 5.112 | 4.552 | 3.701 | 0.366 |
| DeepVAR      | 2.896 | 2.151 | 1.754 | 0.396 |
| TCN          | 2.414 | 1.780 | 0.551 | 0.418 |
| ASTGCN       | 2.293 | 1.699 | 0.455 | 0.453 |
| **GATv2-TCN** | **2.222** | **1.642** | **0.513** | **0.508** |
