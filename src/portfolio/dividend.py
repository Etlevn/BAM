"""
Per-round dividend settlement (common across all agents).

Modes (EXPERIMENT_CONFIG['dividend_mode']):
  - "fixed":  pay E[d] = low*prob + high*(1-prob) every round (legacy default; 0.7)
  - "random": one common Bernoulli draw of low or high each round
"""

from __future__ import annotations

import random
from typing import Any, Mapping


def expected_dividend_per_share(cfg: Mapping[str, Any]) -> float:
    low = float(cfg["dividend_low"])
    high = float(cfg["dividend_high"])
    prob = float(cfg["dividend_prob"])
    return low * prob + high * (1.0 - prob)


def resolve_round_dividend_per_share(
    cfg: Mapping[str, Any],
    *,
    round_num: int | None = None,
    rng: random.Random | None = None,
) -> float:
    """
    Dividend paid per share this round (identical for every trader).

    If dividend_mode is "random" and rng is None, builds a Random from
    optional cfg['dividend_seed'] mixed with round_num for reproducibility.
    """
    mode = str(cfg.get("dividend_mode", "fixed")).strip().lower()
    if mode == "fixed":
        return expected_dividend_per_share(cfg)
    if mode == "random":
        low = float(cfg["dividend_low"])
        high = float(cfg["dividend_high"])
        prob = float(cfg["dividend_prob"])
        if rng is None:
            seed = cfg.get("dividend_seed")
            if seed is None:
                rng = random.Random()
            else:
                # Independent reproducible draw per round when seed is set.
                base = int(seed)
                r = 0 if round_num is None else int(round_num)
                rng = random.Random((base << 16) ^ (r * 0x9E3779B9))
        return low if rng.random() < prob else high
    raise ValueError(
        f"Invalid dividend_mode {mode!r}; expected 'fixed' or 'random'."
    )
