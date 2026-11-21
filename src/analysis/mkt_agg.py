"""Per-round mean price/volume + 95% CI by group × mode × bas × series."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

_ID_COLS = ("group", "mode", "bas", "series")
_OUT_COLS = [
    "group",
    "mode",
    "bas",
    "series",
    "round",
    "mean_price",
    "ci_low",
    "ci_up",
    "mean_volume",
    "fundamental_value",
    "n",
]


def _mean_and_ci(values: pd.Series) -> tuple[float, float, float, int]:
    """Return mean, 95% t CI low/up, n (same rules as summarize_by_series)."""
    vals = pd.to_numeric(values, errors="coerce").dropna()
    n = int(len(vals))
    if n == 0:
        return float("nan"), float("nan"), float("nan"), 0
    mean = float(vals.mean())
    std = float(vals.std(ddof=1)) if n > 1 else 0.0
    if n <= 1 or not np.isfinite(std) or std == 0.0:
        return mean, mean, mean, n
    try:
        sem = float(stats.sem(vals))
        if not np.isfinite(sem) or sem == 0.0:
            return mean, mean, mean, n
        lo, hi = stats.t.interval(
            confidence=0.95, df=n - 1, loc=mean, scale=sem
        )
        return mean, float(lo), float(hi), n
    except Exception:
        return mean, float("nan"), float("nan"), n


def session_round_market_panel(mkt_df: pd.DataFrame) -> pd.DataFrame:
    """
    Collapse agent-duplicated _mkt rows to one row per
    (group, mode, bas, series, session, round).
    """
    need = {"session", "round", "mkt_prc", "mkt_vol"}
    missing = need - set(mkt_df.columns)
    if missing:
        raise ValueError(f"_mkt.csv missing columns: {sorted(missing)}")
    id_missing = [c for c in ("mode", "bas", "series") if c not in mkt_df.columns]
    if id_missing:
        raise ValueError(
            f"_mkt.csv missing identity columns: {id_missing}; re-run integ"
        )

    panel = mkt_df.copy()
    panel["round"] = pd.to_numeric(panel["round"], errors="coerce")
    panel["mkt_prc"] = pd.to_numeric(panel["mkt_prc"], errors="coerce")
    panel["mkt_vol"] = pd.to_numeric(panel["mkt_vol"], errors="coerce")
    panel = panel.dropna(subset=["session", "round", "mkt_prc"])
    panel["round"] = panel["round"].astype(int)
    panel["mkt_vol"] = panel["mkt_vol"].fillna(0.0)

    id_cols = [c for c in _ID_COLS if c in panel.columns]
    subset = id_cols + ["session", "round"]
    keep = id_cols + ["session", "round", "mkt_prc", "mkt_vol"]
    return (
        panel.sort_values(subset)
        .drop_duplicates(subset=subset, keep="first")
        .loc[:, keep]
    )


def build_mkt_agg_table(
    mkt_df: pd.DataFrame,
    *,
    group: str,
    fundamental_value: float,
    total_rounds: int,
) -> pd.DataFrame:
    """
    Per formal round mean price, 95% CI, mean volume within each
    ``group × mode × bas × series`` (no BR pair explode).
    """
    panel = session_round_market_panel(mkt_df)
    if "group" not in panel.columns:
        panel["group"] = group
    else:
        panel["group"] = panel["group"].fillna(group)

    formal = set(range(1, int(total_rounds) + 1))
    panel = panel[panel["round"].isin(formal)]
    if panel.empty:
        return pd.DataFrame(columns=_OUT_COLS)

    rows: list[dict] = []
    strata = panel.groupby(list(_ID_COLS), dropna=False, sort=True)
    for key_vals, stratum in strata:
        if not isinstance(key_vals, tuple):
            key_vals = (key_vals,)
        id_map = dict(zip(_ID_COLS, key_vals))
        for rnd in range(1, int(total_rounds) + 1):
            part = stratum[stratum["round"] == rnd]
            mean_p, ci_lo, ci_hi, n = _mean_and_ci(part["mkt_prc"])
            mean_v = (
                float(pd.to_numeric(part["mkt_vol"], errors="coerce").dropna().mean())
                if n > 0
                else float("nan")
            )
            rows.append(
                {
                    **id_map,
                    "round": rnd,
                    "mean_price": round(mean_p, 4) if np.isfinite(mean_p) else np.nan,
                    "ci_low": round(ci_lo, 4) if np.isfinite(ci_lo) else np.nan,
                    "ci_up": round(ci_hi, 4) if np.isfinite(ci_hi) else np.nan,
                    "mean_volume": round(mean_v, 4) if np.isfinite(mean_v) else np.nan,
                    "fundamental_value": float(fundamental_value),
                    "n": n,
                }
            )
    return pd.DataFrame(rows).loc[:, _OUT_COLS]


def load_group_mkt_csv(path: Path) -> pd.DataFrame:
    from src.integ.paths import read_table_csv

    return read_table_csv(path)
