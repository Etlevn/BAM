"""Paper-aligned market metric helpers (FV deviation / PV variance)."""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence

import numpy as np


def mse_fv(prices: Sequence[float], fundamental_value: float) -> float:
    if not prices:
        raise ValueError("prices must be non-empty")
    return float(sum((float(p) - fundamental_value) ** 2 for p in prices) / len(prices))


def mse_fv_formal_rounds(
    prices_by_round: Mapping[int, float],
    fundamental_value: float,
    formal_rounds: Iterable[int] | None = None,
) -> float:
    if formal_rounds is None:
        formal_rounds = range(1, 21)
    vals = [float(prices_by_round[r]) for r in formal_rounds if r in prices_by_round]
    return mse_fv(vals, fundamental_value)


def amplitude_max_minus_fv(
    prices: Sequence[float],
    fundamental_value: float,
) -> float:
    if not prices:
        raise ValueError("prices must be non-empty")
    return float(max(prices) - fundamental_value)


def cross_section_pv_variance(portfolio_values: Sequence[float]) -> float:
    if not portfolio_values:
        raise ValueError("portfolio_values must be non-empty")
    return float(np.var(list(portfolio_values)))
