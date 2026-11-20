"""Session-level market metrics: MSE(FV), Amplitude, PV Variance."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.analysis.market_io import (
    portfolio_values_in_round,
    read_market_prices,
    read_market_prices_by_round,
)
from src.analysis.metrics import amplitude_max_minus_fv, mse_fv_formal_rounds
from src.integ.session import SessionMeta


def _mean_pv_variance(input_dir, formal_rounds: range) -> float | None:
    period_vars: list[float] = []
    for r in formal_rounds:
        vals = portfolio_values_in_round(input_dir / f"r{r}")
        if vals:
            period_vars.append(float(np.var(vals)))
    if not period_vars:
        return None
    return float(np.mean(period_vars))


def build_market_row(
    meta: SessionMeta,
    *,
    fundamental_value: float,
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

    formal = list(range(1, min(actual_rounds, total_rounds) + 1))
    mse = mse_fv_formal_rounds(
        prices_by_round, fundamental_value, formal_rounds=formal
    )
    formal_prices = [prices_by_round[r] for r in formal if r in prices_by_round]
    amplitude = (
        amplitude_max_minus_fv(formal_prices, fundamental_value)
        if formal_prices
        else None
    )
    pv_var = _mean_pv_variance(meta.path / "input", range(1, total_rounds + 1))

    return {
        "group": meta.group,
        "series": meta.series,
        "session": meta.simulation_index,
        "rounds": actual_rounds,
        "mse": round(float(mse), 2) if mse is not None else None,
        "amplitude": round(float(amplitude), 2) if amplitude is not None else None,
        "pv_variance": round(float(pv_var), 2) if pv_var is not None else None,
    }


def build_market_table(
    sessions: list[SessionMeta],
    *,
    fundamental_value: float,
    total_rounds: int,
) -> pd.DataFrame:
    rows = [
        build_market_row(
            meta, fundamental_value=fundamental_value, total_rounds=total_rounds
        )
        for meta in sessions
    ]
    rows = [r for r in rows if r is not None]
    if not rows:
        return pd.DataFrame(
            columns=[
                "group",
                "series",
                "session",
                "rounds",
                "mse",
                "amplitude",
                "pv_variance",
            ]
        )
    return pd.DataFrame(rows)
