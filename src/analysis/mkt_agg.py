"""Group-level per-round mean price/volume + 95% CI (Figure 2 data)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


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
    """Collapse agent-duplicated _mkt rows to one row per (session, round)."""
    need = {"session", "round", "mkt_prc", "mkt_vol"}
    missing = need - set(mkt_df.columns)
    if missing:
        raise ValueError(f"_mkt.csv missing columns: {sorted(missing)}")

    panel = mkt_df.copy()
    panel["round"] = pd.to_numeric(panel["round"], errors="coerce")
    panel["mkt_prc"] = pd.to_numeric(panel["mkt_prc"], errors="coerce")
    panel["mkt_vol"] = pd.to_numeric(panel["mkt_vol"], errors="coerce")
    panel = panel.dropna(subset=["session", "round", "mkt_prc"])
    panel["round"] = panel["round"].astype(int)
    # Volume missing → 0 (same spirit as market_io reader).
    panel["mkt_vol"] = panel["mkt_vol"].fillna(0.0)
    return (
        panel.sort_values(["session", "round"])
        .drop_duplicates(subset=["session", "round"], keep="first")
        .loc[:, ["session", "round", "mkt_prc", "mkt_vol"]]
    )


def build_mkt_agg_table(
    mkt_df: pd.DataFrame,
    *,
    group: str,
    fundamental_value: float,
    total_rounds: int,
) -> pd.DataFrame:
    """
    Across all sessions in the group: per formal round mean price, 95% CI,
    mean volume, and constant fundamental value.
    """
    panel = session_round_market_panel(mkt_df)
    formal = set(range(1, int(total_rounds) + 1))
    panel = panel[panel["round"].isin(formal)]

    rows: list[dict] = []
    for rnd in range(1, int(total_rounds) + 1):
        part = panel[panel["round"] == rnd]
        mean_p, ci_lo, ci_hi, n = _mean_and_ci(part["mkt_prc"])
        mean_v = (
            float(pd.to_numeric(part["mkt_vol"], errors="coerce").dropna().mean())
            if n > 0
            else float("nan")
        )
        rows.append(
            {
                "group": group,
                "round": rnd,
                "mean_price": round(mean_p, 4) if np.isfinite(mean_p) else np.nan,
                "ci_low": round(ci_lo, 4) if np.isfinite(ci_lo) else np.nan,
                "ci_up": round(ci_hi, 4) if np.isfinite(ci_hi) else np.nan,
                "mean_volume": round(mean_v, 4) if np.isfinite(mean_v) else np.nan,
                "fundamental_value": float(fundamental_value),
                "n": n,
            }
        )
    return pd.DataFrame(rows)


def load_group_mkt_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)
