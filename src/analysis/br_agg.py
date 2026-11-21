"""Expand BR pair-series market rows into per-model rows for mixed-market summaries."""

from __future__ import annotations

import re

import pandas as pd

# Series folder join used by paths.get_exp_series_name for BR.
_PAIR_SEP = " & "
# Optional BAS prefix on a series folder: a01_ / s20_ / b_
_BAS_PREFIX = re.compile(r"^(?:[as]\d{2}|b)_")


def models_from_br_series(series: str) -> list[str]:
    """Split a BR series name into model folder segments (strip optional BAS prefix)."""
    raw = str(series or "").strip()
    if not raw:
        return []
    raw = _BAS_PREFIX.sub("", raw)
    parts = [p.strip() for p in raw.split(_PAIR_SEP) if p.strip()]
    # De-dupe while preserving order (same model twice would be unusual).
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def rows_for_mode(df: pd.DataFrame, mode: str) -> pd.DataFrame:
    """Filter rows to ``mode`` (``sgl`` / ``br``); empty if none or column missing."""
    if df is None or df.empty:
        return pd.DataFrame()
    if "mode" not in df.columns:
        return pd.DataFrame()
    wanted = str(mode).strip().lower()
    col = df["mode"].astype(str).str.strip().str.lower()
    return df.loc[col == wanted].copy()


def br_market_rows(market_df: pd.DataFrame) -> pd.DataFrame:
    """Rows with ``mode == "br"`` (mixed groups like TEST); empty if none."""
    return rows_for_mode(market_df, "br")


def expand_market_by_model(market_df: pd.DataFrame) -> pd.DataFrame:
    """
    Duplicate each session row once per model in its pair series.

    ``series`` becomes the single model name; mse / amplitude / pv_variance /
    session / rounds / group / mode / bas are unchanged (same session-level
    metrics as SGL).
    """
    if market_df is None or market_df.empty:
        return market_df.copy() if market_df is not None else pd.DataFrame()

    rows: list[dict] = []
    for rec in market_df.to_dict(orient="records"):
        models = models_from_br_series(str(rec.get("series", "")))
        if not models:
            rows.append(dict(rec))
            continue
        for model in models:
            row = dict(rec)
            row["series"] = model
            rows.append(row)
    return pd.DataFrame(rows)


def frame_for_robust(df: pd.DataFrame, mode: str) -> pd.DataFrame:
    """
    Session rows for one mode-split robust file (market or rational).

    ``sgl``: filter only. ``br``: filter then explode pair series → one row per model.
    """
    part = rows_for_mode(df, mode)
    if part.empty:
        return part
    if str(mode).strip().lower() == "br":
        return expand_market_by_model(part)
    return part


# Backward-compatible alias.
market_frame_for_robust = frame_for_robust
