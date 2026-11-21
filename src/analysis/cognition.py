"""Agent–round cognition panel: stated action → beliefs / next-period trading."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.behavior import (
    _agent_round_orders,
    _coerce_mkt,
    _horizon_expected_returns,
)

# Match behavior._KEY so order merges don't invent mode_x/bas_x.
_KEY = ["group", "mode", "bas", "series", "session", "llm"]

# Default Stated Action lexicon (B1). Whole-word, case-insensitive.
# Excluded by design: order(s), bid(s), offer(s), long/short, hold*, trade*, fill*, execute*.
BUY_KEYWORDS: frozenset[str] = frozenset(
    {
        "buy",
        "buys",
        "buying",
        "bought",
        "purchase",
        "purchases",
        "purchasing",
        "purchased",
        "acquire",
        "acquires",
        "acquiring",
        "acquired",
    }
)

SELL_KEYWORDS: frozenset[str] = frozenset(
    {
        "sell",
        "sells",
        "selling",
        "sold",
        "liquidate",
        "liquidates",
        "liquidating",
        "liquidated",
    }
)

_TOKEN_RE = re.compile(r"[a-z]+(?:'[a-z]+)?", re.IGNORECASE)


def count_buy_sell_keywords(text: str | None) -> tuple[int, int] | None:
    """Return (n_buy, n_sell), or None if text is missing/blank."""
    if text is None:
        return None
    if isinstance(text, float) and np.isnan(text):
        return None
    s = str(text).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return None
    tokens = [t.lower() for t in _TOKEN_RE.findall(s)]
    n_buy = sum(1 for t in tokens if t in BUY_KEYWORDS)
    n_sell = sum(1 for t in tokens if t in SELL_KEYWORDS)
    return n_buy, n_sell


def encode_stated_action(text: str | None) -> float:
    """
    Stated Action ∈ {−1, 0, 1}, or NaN if text missing.

    net = n_buy − n_sell → sign; equal counts → 0. Missing ≠ 0.
    """
    counts = count_buy_sell_keywords(text)
    if counts is None:
        return float("nan")
    n_buy, n_sell = counts
    net = n_buy - n_sell
    if net > 0:
        return 1.0
    if net < 0:
        return -1.0
    return 0.0


def _encode_column(series: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    actions: list[float] = []
    buys: list[float] = []
    sells: list[float] = []
    for val in series:
        counts = count_buy_sell_keywords(val)
        if counts is None:
            actions.append(float("nan"))
            buys.append(float("nan"))
            sells.append(float("nan"))
        else:
            n_buy, n_sell = counts
            net = n_buy - n_sell
            actions.append(1.0 if net > 0 else (-1.0 if net < 0 else 0.0))
            buys.append(float(n_buy))
            sells.append(float(n_sell))
    return (
        pd.Series(actions, index=series.index, dtype=float),
        pd.Series(buys, index=series.index, dtype=float),
        pd.Series(sells, index=series.index, dtype=float),
    )


def build_cognition_panel(
    mkt: pd.DataFrame,
    rx: pd.DataFrame,
    output: pd.DataFrame,
    *,
    total_rounds: int = 20,
) -> pd.DataFrame:
    """
    Build agent–round panel for stated-action vs expectation / buy links.

    Requires integ ``_mkt``, ``_rx``, and ``_output`` (no fallback).

    Horizons follow Methods h in {0,2,5,10} as exp_ret_h*.
    Elicitation has no delta=1; long horizon alias is
    exp_ret_t10 = exp_ret_h10 only. See docs/paper/definition_audit.md.
    """
    mkt = _coerce_mkt(mkt)
    formal = set(range(1, int(total_rounds) + 1))
    mkt = mkt[mkt["round"].isin(formal)].copy()

    out = output.copy()
    out["round"] = pd.to_numeric(out["round"], errors="coerce")
    out = out.dropna(subset=["round", "session", "llm"])
    out["round"] = out["round"].astype(int)
    out = out[out["round"].isin(formal)].copy()

    merge_keys = [c for c in _KEY if c in mkt.columns and c in out.columns] + ["round"]
    text_cols = [c for c in ("plan", "insight") if c in out.columns]
    keep = merge_keys + text_cols
    # Prefer first occurrence if duplicates.
    out = out.loc[:, keep].drop_duplicates(subset=merge_keys, keep="first")

    panel = mkt.merge(out, on=merge_keys, how="left")

    if "plan" not in panel.columns:
        panel["plan"] = np.nan
    if "insight" not in panel.columns:
        panel["insight"] = np.nan

    panel["stated_action_plan"], panel["buy_kw_plan"], panel["sell_kw_plan"] = (
        _encode_column(panel["plan"])
    )
    (
        panel["stated_action_insight"],
        panel["buy_kw_insight"],
        panel["sell_kw_insight"],
    ) = _encode_column(panel["insight"])

    orders = _agent_round_orders(rx)
    panel = panel.merge(orders, on=_KEY + ["round"], how="left")
    for c in ("buy_submitted", "sell_submitted", "buy_dummy", "sell_dummy"):
        if c not in panel.columns:
            panel[c] = 0
        else:
            panel[c] = panel[c].fillna(0)

    panel = panel.sort_values(_KEY + ["round"])
    panel["buy_dummy_next"] = panel.groupby(_KEY, dropna=False)["buy_dummy"].shift(-1)

    exp_rows = [
        _horizon_expected_returns(
            row, float(row["mkt_prc"]) if pd.notna(row["mkt_prc"]) else np.nan
        )
        for _, row in panel.iterrows()
    ]
    exp_df = pd.DataFrame(exp_rows)
    panel = pd.concat([panel.reset_index(drop=True), exp_df], axis=1)

    # Long horizon only (Methods h=10). No silent t+1↔h2 alias.
    panel["exp_ret_t10"] = panel["exp_ret_h10"]

    # Drop bulky raw text from the analysis CSV.
    panel = panel.drop(columns=["plan", "insight"], errors="ignore")

    front = [
        "group",
        "mode",
        "bas",
        "series",
        "session",
        "round",
        "llm",
        "llm_type",
        "mkt_prc",
        "stated_action_plan",
        "stated_action_insight",
        "buy_kw_plan",
        "sell_kw_plan",
        "buy_kw_insight",
        "sell_kw_insight",
        "exp_ret_t10",
        "exp_ret_h0",
        "exp_ret_h2",
        "exp_ret_h5",
        "exp_ret_h10",
        "buy_dummy",
        "buy_dummy_next",
        "buy_submitted",
        "sell_submitted",
    ]
    cols = [c for c in front if c in panel.columns] + [
        c for c in panel.columns if c not in front
    ]
    return panel.loc[:, cols]


def load_cognition_inputs(
    out_dir: Path, group_name: str
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    from src.integ.paths import integ_csv

    mkt_path = integ_csv(out_dir, group_name, "mkt")
    rx_path = integ_csv(out_dir, group_name, "rx")
    output_path = integ_csv(out_dir, group_name, "output")
    if not mkt_path.is_file():
        raise FileNotFoundError(
            f"RUN_COGNITION requires {mkt_path}; run integ first (no fallback)."
        )
    if not rx_path.is_file():
        raise FileNotFoundError(
            f"RUN_COGNITION requires {rx_path}; run integ first (no fallback)."
        )
    if not output_path.is_file():
        raise FileNotFoundError(
            f"RUN_COGNITION requires {output_path}; run integ first (no fallback)."
        )
    from src.integ.paths import read_table_csv

    return (
        read_table_csv(mkt_path),
        read_table_csv(rx_path),
        read_table_csv(output_path),
    )
