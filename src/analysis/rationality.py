"""Session-level forecast rationality metrics."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import ttest_1samp
from statsmodels.stats.stattools import durbin_watson

from src.analysis.market_io import read_market_prices, read_market_prices_by_round
from src.integ.session import SessionMeta


def _distribution(df: pd.DataFrame) -> dict[str, float]:
    return {
        "mean_error": float(df["error"].mean()),
        "std_error": float(df["error"].std()),
        "skewness": float(df["error"].skew()),
        "kurtosis": float(df["error"].kurtosis()),
    }


def _unbiasedness(df: pd.DataFrame) -> dict[str, float]:
    t_stat, p_val = ttest_1samp(df["error"], popmean=0)
    return {"t_stat_error": float(t_stat), "p_val_error": float(p_val)}


def _autocorrelation(df: pd.DataFrame) -> dict[str, float]:
    nan_out = {"ar1_coef": np.nan, "ar1_pval": np.nan, "dw_stat": np.nan}
    df_sorted = df.sort_values(by=["agent", "predicted_round"]).copy()
    df_sorted["error_lag"] = df_sorted.groupby("agent")["error"].shift(1)
    df_lagged = df_sorted.dropna(subset=["error", "error_lag"])
    if len(df_lagged) < 2:
        return nan_out
    # Constant lag → design matrix [1, c] is singular with the intercept.
    if float(np.nanstd(df_lagged["error_lag"])) == 0.0:
        return nan_out
    X = sm.add_constant(df_lagged["error_lag"])
    y = df_lagged["error"]
    model = sm.OLS(y, X).fit()
    resid = np.asarray(model.resid, dtype=float)
    dw = (
        float(durbin_watson(resid))
        if resid.size > 1 and float(np.nansum(resid**2)) > 0.0
        else np.nan
    )
    return {
        "ar1_coef": float(model.params.get("error_lag", np.nan)),
        "ar1_pval": float(model.pvalues.get("error_lag", np.nan)),
        "dw_stat": dw,
    }


def build_rational_row(
    meta: SessionMeta,
    *,
    total_rounds: int,
) -> dict[str, Any] | None:
    mkt_path = meta.path / "market" / "mkt.csv"
    if not mkt_path.is_file():
        return None
    try:
        prices = read_market_prices(mkt_path)
        prices_by_round = read_market_prices_by_round(mkt_path)
    except Exception:
        return None

    actual_rounds = len(prices) - 1
    if actual_rounds < total_rounds:
        return None

    output_dir = meta.path / "output"
    if not output_dir.is_dir():
        return None

    forecast_rows: list[dict[str, Any]] = []
    round_dirs: list[int] = []
    for d in output_dir.iterdir():
        if d.is_dir() and d.name.startswith("r"):
            try:
                round_dirs.append(int(d.name[1:]))
            except Exception:
                pass

    for r in sorted(round_dirs):
        round_dir = output_dir / f"r{r}"
        for fpath in sorted(round_dir.glob("*.json")):
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
            except Exception:
                continue
            forecasts = data.get("new_content", {}).get("price_forecasts", [])
            parts = fpath.name.split("_")
            agent_id = parts[1] if len(parts) > 1 else "unknown"
            if not isinstance(forecasts, list):
                continue
            for item in forecasts:
                try:
                    pred_round = int(item.get("round"))
                    forecast = float(item.get("forecasted_price"))
                except Exception:
                    continue
                if pred_round not in prices_by_round:
                    continue
                true_price = prices_by_round[pred_round]
                forecast_rows.append(
                    {
                        "agent": agent_id,
                        "predicted_round": pred_round,
                        "forecast": forecast,
                        "true_price": true_price,
                        "error": forecast - true_price,
                    }
                )

    if not forecast_rows:
        return None

    df = pd.DataFrame(forecast_rows)
    row: dict[str, Any] = {
        "group": meta.group,
        "series": meta.series,
        "session": meta.simulation_index,
        "mse": float(np.mean((df["forecast"] - df["true_price"]) ** 2)),
    }
    row.update(_distribution(df))
    row.update(_unbiasedness(df))
    row.update(_autocorrelation(df))
    return row


def build_rational_table(
    sessions: list[SessionMeta],
    *,
    total_rounds: int,
) -> pd.DataFrame:
    rows = [
        build_rational_row(meta, total_rounds=total_rounds) for meta in sessions
    ]
    rows = [r for r in rows if r is not None]
    cols = [
        "group",
        "series",
        "session",
        "mse",
        "mean_error",
        "std_error",
        "skewness",
        "kurtosis",
        "t_stat_error",
        "p_val_error",
        "ar1_coef",
        "ar1_pval",
        "dw_stat",
    ]
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows)[cols].round(4)
