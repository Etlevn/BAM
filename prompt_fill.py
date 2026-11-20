"""
Fill trader prompt templates from experiment config and optional BAS bias text.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Mapping

import config


def interest_rate_pct(rate: float) -> str:
    """Format interest rate as percent digits without the % sign (e.g. 0.05 -> '5')."""
    pct = rate * 100.0
    if abs(pct - round(pct)) < 1e-9:
        return str(int(round(pct)))
    return f"{pct:g}"


def load_bas_bias(bias_id: str, catalog_path: str | os.PathLike[str] | None = None) -> str:
    """Load one bias sentence from bas_biases.json by id (e.g. 'amp_1')."""
    path = catalog_path
    if path is None:
        path = os.path.join(config.BASE_DIR, "init", "prompt", "bas_biases.json")
    with open(path, encoding="utf-8") as f:
        catalog: dict[str, str] = json.load(f)
    if bias_id not in catalog:
        raise KeyError(f"Unknown BAS_BIAS_ID {bias_id!r}; known: {sorted(catalog)}")
    return catalog[bias_id]


def _collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip() + ("\n" if text.endswith("\n") else "")


def fill_experiment_start(
    text: str,
    cfg: Mapping[str, Any],
    *,
    use_bas: bool = False,
    bias_text: str = "",
) -> str:
    """Replace config placeholders and BAS slots in experiment_start template."""
    replacements = {
        "<PRACTICE_ROUNDS>": str(cfg["practice_rounds"]),
        "<TOTAL_ROUNDS>": str(cfg["total_rounds"]),
        "<INITIAL_CASH>": str(cfg["initial_cash"]),
        "<INITIAL_STOCKS>": str(cfg["initial_stocks"]),
        "<DIVIDEND_LOW>": str(cfg["dividend_low"]),
        "<DIVIDEND_HIGH>": str(cfg["dividend_high"]),
        "<DIVIDEND_PROB>": str(cfg["dividend_prob"]),
        "<INTEREST_RATE_PCT>": interest_rate_pct(float(cfg["interest_rate"])),
        "<INTEREST_RATE>": interest_rate_pct(float(cfg["interest_rate"])),
        "<STOCK_VALUE>": str(cfg["stock_value"]),
        "<MAX_ORDER_QUANTITY>": str(cfg.get("max_order_quantity", 5)),
    }
    out = text
    for key, val in replacements.items():
        out = out.replace(key, val)

    if use_bas and bias_text:
        out = (
            out.replace("<BAS_PARAGRAPH>", bias_text)
            .replace("<BAS_PAREN_A>", f"( {bias_text} )")
            .replace("<BAS_PAREN_B>", f"( {bias_text} )")
            .replace("<BAS_BULLET>", f"- {bias_text}")
        )
    else:
        out = (
            out.replace("<BAS_PARAGRAPH>", "")
            .replace("<BAS_PAREN_A>", "")
            .replace("<BAS_PAREN_B>", "")
            .replace("<BAS_BULLET>", "")
        )

    return _collapse_blank_lines(out)


def fill_order_forecast_end(
    text: str,
    *,
    limit_price_min: int,
    limit_price_max: int,
    max_order_quantity: int = 5,
    use_bas: bool = False,
    bias_text: str = "",
) -> str:
    """Replace limit/order placeholders and optional BAS end bullet."""
    out = (
        text.replace("<MIN_LIMIT_PRICE>", str(limit_price_min))
        .replace("<MAX_LIMIT_PRICE>", str(limit_price_max))
        .replace("<MAX_ORDER_QUANTITY>", str(max_order_quantity))
    )
    if use_bas and bias_text:
        out = out.replace("<BAS_END_BULLET>", f"- {bias_text}")
    else:
        out = out.replace("<BAS_END_BULLET>", "")
    return _collapse_blank_lines(out)
