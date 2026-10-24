"""Shared train-fitted design matrix for the ROS tabular models.

Same idea as ``projections.validation.tabular._design`` but with the ROS
categorical set (position, team).  Categorical levels are fixed from the
training fold, so unseen holdout levels become missing rather than new columns.
"""

from __future__ import annotations

import numpy as np
import polars as pl


def design_matrix(
    train: pl.DataFrame,
    test: pl.DataFrame,
    columns: tuple[str, ...],
    *,
    categorical: tuple[str, ...] = ("position", "team"),
):
    import pandas as pd

    present = [c for c in columns if c in train.columns and c in test.columns]
    train_pdf = train.select(present).to_pandas()
    test_pdf = test.select(present).to_pandas()
    keep: list[str] = []
    cat_cols: list[str] = []
    for col in present:
        if col in categorical:
            train_s = train_pdf[col].astype("string")
            test_s = test_pdf[col].astype("string")
            if train_s.notna().sum() == 0:
                continue
            categories = pd.Index(train_s.dropna().unique())
            train_pdf[col] = pd.Categorical(train_s, categories=categories)
            test_pdf[col] = pd.Categorical(test_s, categories=categories)
            cat_cols.append(col)
            keep.append(col)
            continue
        series = pd.to_numeric(train_pdf[col], errors="coerce")
        if series.notna().sum() == 0:
            continue
        train_pdf[col] = series
        test_pdf[col] = pd.to_numeric(test_pdf[col], errors="coerce")
        keep.append(col)
    if not keep:
        raise ValueError("no usable features")
    return train_pdf[keep], test_pdf[keep], tuple(cat_cols)


def dense_design(
    train: pl.DataFrame,
    test: pl.DataFrame,
    columns: tuple[str, ...],
    *,
    categorical: tuple[str, ...] = ("position", "team"),
) -> tuple[np.ndarray, np.ndarray]:
    """Dense float design for scikit-learn forests (train-fitted one-hot + medians)."""
    import pandas as pd

    train_pdf, test_pdf, cat_cols = design_matrix(train, test, columns, categorical=categorical)
    train_enc = pd.get_dummies(train_pdf, columns=list(cat_cols), dummy_na=True, dtype=np.float32)
    test_enc = pd.get_dummies(
        test_pdf, columns=list(cat_cols), dummy_na=True, dtype=np.float32
    ).reindex(columns=train_enc.columns, fill_value=0.0)
    train_enc = train_enc.replace([np.inf, -np.inf], np.nan)
    test_enc = test_enc.replace([np.inf, -np.inf], np.nan)
    medians = train_enc.median(axis=0, numeric_only=True)
    train_enc = train_enc.fillna(medians).fillna(0.0)
    test_enc = test_enc.fillna(medians).fillna(0.0)
    return (
        train_enc.to_numpy(dtype=np.float32, copy=False),
        test_enc.to_numpy(dtype=np.float32, copy=False),
    )
