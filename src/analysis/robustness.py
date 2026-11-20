"""Cross-session robustness summaries grouped by series (long format)."""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd
from scipy import stats


def summarize_by_series(
    df: pd.DataFrame,
    metrics: Sequence[str],
    *,
    round_mean: int = 2,
    round_cv: int = 3,
) -> pd.DataFrame:
    """
    Long table: one row per (group, series, Metric) with mean/std/CV/95% CI.
    """
    if df.empty:
        return pd.DataFrame(
            columns=[
                "group",
                "series",
                "Metric",
                "Mean",
                "StdDev",
                "CV",
                "95% CI Lower",
                "95% CI Upper",
                "CI Width / Mean",
                "n",
            ]
        )

    rows: list[dict] = []
    grouped = df.groupby(["group", "series"], dropna=False, sort=True)
    for (group, series), part in grouped:
        for metric in metrics:
            values = pd.to_numeric(part.get(metric), errors="coerce").dropna()
            n = int(len(values))
            if n == 0:
                rows.append(
                    {
                        "group": group,
                        "series": series,
                        "Metric": metric,
                        "Mean": np.nan,
                        "StdDev": np.nan,
                        "CV": np.nan,
                        "95% CI Lower": np.nan,
                        "95% CI Upper": np.nan,
                        "CI Width / Mean": np.nan,
                        "n": 0,
                    }
                )
                continue
            mean = float(values.mean())
            std = float(values.std(ddof=1)) if n > 1 else 0.0
            cv = (std / mean) if mean != 0 else np.nan
            # t.interval warns when scale (SEM) is 0 or non-finite (identical values).
            if n <= 1 or not np.isfinite(std) or std == 0.0:
                ci_low = ci_up = mean
            else:
                try:
                    sem = float(stats.sem(values))
                    if not np.isfinite(sem) or sem == 0.0:
                        ci_low = ci_up = mean
                    else:
                        ci_low, ci_up = stats.t.interval(
                            confidence=0.95,
                            df=n - 1,
                            loc=mean,
                            scale=sem,
                        )
                        ci_low, ci_up = float(ci_low), float(ci_up)
                except Exception:
                    ci_low = ci_up = np.nan
            ci_width = (
                (ci_up - ci_low)
                if (np.isfinite(ci_up) and np.isfinite(ci_low))
                else np.nan
            )
            ci_ratio = (
                (ci_width / mean)
                if (mean != 0 and np.isfinite(ci_width))
                else np.nan
            )
            rows.append(
                {
                    "group": group,
                    "series": series,
                    "Metric": metric,
                    "Mean": round(mean, round_mean),
                    "StdDev": round(std, round_mean) if np.isfinite(std) else np.nan,
                    "CV": round(cv, round_cv) if np.isfinite(cv) else np.nan,
                    "95% CI Lower": round(ci_low, round_mean)
                    if np.isfinite(ci_low)
                    else np.nan,
                    "95% CI Upper": round(ci_up, round_mean)
                    if np.isfinite(ci_up)
                    else np.nan,
                    "CI Width / Mean": round(ci_ratio, round_cv)
                    if np.isfinite(ci_ratio)
                    else np.nan,
                    "n": n,
                }
            )
    return pd.DataFrame(rows)
