"""Shared leading column order for integ tables."""

from __future__ import annotations

import pandas as pd

# First columns for rx / mkt / output (exact spelling).
LEADING_COLS = [
    "group",
    "series",
    "session",
    "market_type",
    "bas",
    "round",
    "llm",
    "llm_type",
]


def order_leading_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        # Keep declared leading cols present even on empty frames when possible.
        cols = list(LEADING_COLS) + [c for c in df.columns if c not in LEADING_COLS]
        return pd.DataFrame(columns=cols)
    lead = [c for c in LEADING_COLS if c in df.columns]
    rest = [c for c in df.columns if c not in LEADING_COLS]
    return df.loc[:, lead + rest]
