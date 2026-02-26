import pickle
import numpy as np
from pathlib import Path

DATA_DIR = Path('outputs/data')
with open(DATA_DIR / 'X_raw.pkl', 'rb') as f:
    X_raw = pickle.load(f)

# Rebuild forward-filled raw sequence
X_filled = X_raw.copy()
for d in range(1, len(X_filled)):
    mask = (X_filled[d] == 0).all(axis=-1)
    X_filled[d, mask] = X_filled[d-1, mask]

# Overwrite X_seq.pkl with the raw forward-filled stats!
with open(DATA_DIR / 'X_seq.pkl', 'wb') as f:
    pickle.dump(X_filled, f)

print(f"Recovered raw forward-filled X_seq.pkl! Shape: {X_filled.shape}")
