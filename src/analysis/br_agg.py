"""Expand BR pair-series market rows into per-model rows (Table 1 Mixed)."""

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


def expand_market_by_model(market_df: pd.DataFrame) -> pd.DataFrame:
    """
    Duplicate each session row once per model in its pair series.

    ``series`` becomes the single model name; mse / amplitude / pv_variance /
    session / rounds / group are unchanged (same session-level metrics as SGL).
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


def is_br_group(group_name: str) -> bool:
    """True for Battle-Royale analysis folders (e.g. BR, 3_BR)."""
    name = str(group_name or "").strip().upper()
    return name == "BR" or name.endswith("_BR") or name.startswith("BR_")
