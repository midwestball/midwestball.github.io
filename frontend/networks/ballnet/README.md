# ballnet Inference & GATv2-TCN Pipeline README

> **Note for AI Agents**: This file contains critical knowledge regarding module imports, common gotchas, and specific bugs uncovered in the `ballnet` execution pipeline (`inference_v2.qmd` / data pipeline). Please review this before editing scripts dealing with the `GATv2TCN` model or the `X_seq` data.

## 1. Custom Model Imports (`gatv2tcn`)
The model architecture (`GATv2TCN`) is located in custom local modules, meaning that standard Python absolute or relative imports will fail unless the environment paths are configured properly. 
- **Gotcha**: You will encounter a `ModuleNotFoundError: No module named 'gatv2tcn'` if you attempt to import it dynamically in scripts or notebooks without modifying `sys.path`.
- **Solution**: You must explicitly append the repo root and the `reproduction` subdirectory to `sys.path` before running the import:

```python
import sys
from pathlib import Path

# Fix paths to resolve custom custom GNN architectures
NOTEBOOK_DIR = Path('.').resolve()
sys.path.insert(0, str(NOTEBOOK_DIR / 'NBA-GNN-prediction'))
sys.path.insert(0, str(NOTEBOOK_DIR / 'reproduction'))

from gatv2tcn import GATv2TCN
```

## 2. The `X_seq` Double-Normalization Bug
There was previously a severe silent bug where validation error residuals were systematically heavily negative (e.g., predicted points uniformly 20+ points too high). 
- **The Cause**: The daily data pipeline `01_data_pipeline.py` originally dumped pre-normalized (Z-scored) data into `outputs/data/X_seq.pkl`. `inference_v2.qmd` then independently ran Z-score normalization (`X_seq = (X_seq - mu_per_day) / sd_per_day`) on load. If incremental updates saved the normalized array *back* to disk, subsequent executions would apply Z-scoring *again*, exponentially shrinking the stats and massively skewing the predictions.
- **The Solution**: 
  - `X_seq.pkl` must ONLY store **RAW, un-normalized, forward-filled statistics**. 
  - If you edit the notebook's update logic (Phase 2), **do not** write the Z-scored `X_seq` array back to disk. Only write `X_seq_raw_copy` (or equivalent raw stats) to `X_seq.pkl`.
  - Normalization should only happen exactly *once* in memory right before inference.

## 3. String Literals inside Quarto (`.qmd`) Code Blocks
Python cells inside Quarto files (`.qmd`) act exactly like Jupyter Notebook cells, but writing raw multi-line string text (using actual line breaks instead of `\n`) inside `.write()` or `print()` statements can cause weird string literal parsing bugs.
- **Gotcha**: `SyntaxError: unterminated string literal`
- **Solution**: Always use explicit escaped newlines (`\n`) for string concatenation and f-strings inside these blocks. 

## 4. Pandas KeyErrors on Cumulative Log Updates
The tracking logs (e.g., `results_log.jsonl` or `ev_analysis.json`) accumulate data over many days. When adding new features (such as `naive_bet_made` or `bet_edge`), legacy JSON records will not contain these keys.
- **Gotcha**: `KeyError` when creating Pandas Dataframes from logs and trying to filter. (e.g. `df_results[df_results['naive_bet_made'] == True]`)
- **Solution**: Always implement defensive defaults or column existence checks when reading JSON log files back into DataFrames for the dashboards.

```python
# Defensive column checks for backward compatibility
if 'naive_bet_made' not in df_results.columns:
    df_results['naive_bet_made'] = False
```

## 5. URL Syntax in Python Assignments
When copying URLs from documentation or markdown outputs, take care to assign them correctly.
- **Gotcha**: Assigning `URL = '[https://...](https://...)'` instead of a raw string will break standard library `requests`. 
- **Solution**: Ensure API base strings like `KALSHI_BASE` and endpoints are unformatted raw URLs. 

## 6. EV Strategy "Bet" Sheet Volume Discrepancy
When running `inference_v2.qmd`, you may notice that **Phase 10: Conformal Probability Bet Sheet** outputs dozens of "bets" (e.g. 100+ over edges), whereas **Phase 11: ROI Comparison Dashboard** or the `backtest.py` script report significantly fewer bets (e.g. 2-5 per day).
- **The Cause**: The Bet Sheet is NOT a record of graded behaviors. The Bet Sheet evaluates the model's EV against *every single open, pending Kalshi prop line available before the games start*. The backtesting and `results_log.jsonl` dashboard, on the other hand, strictly filter out propositions where the player Did Not Play, or the odds changed / were suspended. Phase 10 provides *hypothetical suggestions*, whereas the logging dashboards reflect actual executed outcomes.
