"""Agent–round behavior panel for Tables 2–4 (from integ _mkt + _rx)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# Include mode/bas so mixed groups (e.g. TEST) never merge/WAPP across arms.
_KEY = ["group", "mode", "bas", "series", "session", "llm"]


def _coerce_mkt(mkt: pd.DataFrame) -> pd.DataFrame:
    df = mkt.copy()
    df["round"] = pd.to_numeric(df["round"], errors="coerce")
    for c in (
        "mkt_prc",
        "stk_num",
        "fcst_1_prc",
        "fcst_2_prc",
        "fcst_3_prc",
        "fcst_4_prc",
        "fcst_1_rnd",
        "fcst_2_rnd",
        "fcst_3_rnd",
        "fcst_4_rnd",
    ):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["round", "session", "llm"])
    df["round"] = df["round"].astype(int)
    return df


def _agent_round_orders(rx: pd.DataFrame) -> pd.DataFrame:
    """Aggregate submitted and filled orders to agent–round."""
    df = rx.copy()
    df["round"] = pd.to_numeric(df["round"], errors="coerce")
    df["num"] = pd.to_numeric(df["num"], errors="coerce").fillna(0.0)
    df["ord"] = pd.to_numeric(df["ord"], errors="coerce").fillna(0.0)
    df["deal"] = pd.to_numeric(df["deal"], errors="coerce").fillna(0.0)
    df["b/s"] = df["b/s"].astype(str).str.upper().str.strip()
    df = df.dropna(subset=["round", "session", "llm"])
    df["round"] = df["round"].astype(int)

    buy = df["b/s"].eq("BUY")
    sell = df["b/s"].eq("SELL")
    df["buy_sub"] = np.where(buy, df["num"], 0.0)
    df["sell_sub"] = np.where(sell, df["num"], 0.0)
    df["buy_fill"] = np.where(buy & (df["ord"] > 0), df["ord"], 0.0)
    df["buy_fill_cost"] = np.where(
        buy & (df["ord"] > 0), df["ord"] * df["deal"], 0.0
    )

    gcols = [c for c in _KEY if c in df.columns] + ["round"]
    out = (
        df.groupby(gcols, dropna=False, sort=False)
        .agg(
            buy_submitted=("buy_sub", "sum"),
            sell_submitted=("sell_sub", "sum"),
            buy_filled_qty=("buy_fill", "sum"),
            buy_filled_cost=("buy_fill_cost", "sum"),
        )
        .reset_index()
    )
    out["sell_dummy"] = (out["sell_submitted"] > out["buy_submitted"]).astype(int)
    out["buy_dummy"] = (out["buy_submitted"] > out["sell_submitted"]).astype(int)
    return out


def _avg_expectation(row: pd.Series) -> float:
    vals = [
        row.get("fcst_1_prc"),
        row.get("fcst_2_prc"),
        row.get("fcst_3_prc"),
        row.get("fcst_4_prc"),
    ]
    nums = [float(v) for v in vals if v is not None and np.isfinite(float(v))]
    if not nums:
        return float("nan")
    return float(np.mean(nums))


def _horizon_expected_returns(row: pd.Series, price: float) -> dict[str, float]:
    """Map forecast horizons {0,2,5,10} → expected return vs current mkt_prc."""
    out = {
        "exp_ret_h0": float("nan"),
        "exp_ret_h2": float("nan"),
        "exp_ret_h5": float("nan"),
        "exp_ret_h10": float("nan"),
    }
    if not np.isfinite(price) or price == 0:
        return out
    rnd = int(row["round"])
    for i in range(1, 5):
        fr = row.get(f"fcst_{i}_rnd")
        fp = row.get(f"fcst_{i}_prc")
        if fr is None or fp is None or not np.isfinite(float(fr)) or not np.isfinite(
            float(fp)
        ):
            continue
        delta = int(float(fr)) - rnd
        key = {0: "exp_ret_h0", 2: "exp_ret_h2", 5: "exp_ret_h5", 10: "exp_ret_h10"}.get(
            delta
        )
        if key:
            out[key] = float(fp) / price - 1.0
    return out


def _compute_wapp_and_gain(
    panel: pd.DataFrame,
    *,
    fundamental_value: float,
    initial_stocks: float,
) -> pd.DataFrame:
    """
    Per agent path: WAPP starts at FV with endowed shares.
    Gain_t uses P_{t-1} (or FV for t=1) vs WAPP at start of t.
    Buys (filled) update WAPP; sells do not.
    """
    parts: list[pd.DataFrame] = []
    group_cols = [c for c in _KEY if c in panel.columns]
    for _, g in panel.groupby(group_cols, dropna=False, sort=False):
        g = g.sort_values("round").copy()
        wapp = float(fundamental_value)
        shares = float(initial_stocks)
        wapps: list[float] = []
        gains: list[int] = []
        prev_price = float(fundamental_value)

        for _, row in g.iterrows():
            wapps.append(wapp)
            gains.append(1 if prev_price > wapp else 0)

            qty = float(row.get("buy_filled_qty") or 0.0)
            cost = float(row.get("buy_filled_cost") or 0.0)
            if qty > 0 and shares >= 0:
                # Existing inventory weight = shares at start of round.
                wapp = (shares * wapp + cost) / (shares + qty)

            # End-of-round holdings from integ snapshot when available.
            if pd.notna(row.get("stk_num")):
                shares = float(row["stk_num"])
            else:
                shares = shares + qty  # sells ignored for WAPP share base next round
                # If no stk_num, approximate with buys only (conservative).

            if pd.notna(row.get("mkt_prc")):
                prev_price = float(row["mkt_prc"])

        g["wapp"] = wapps
        g["gain_dummy"] = gains
        parts.append(g)

    if not parts:
        return panel
    return pd.concat(parts, ignore_index=True)


def build_behavior_panel(
    mkt: pd.DataFrame,
    rx: pd.DataFrame,
    *,
    fundamental_value: float = 14.0,
    initial_stocks: float = 4.0,
    total_rounds: int = 20,
) -> pd.DataFrame:
    """
    Build agent–round panel with Table 2–4 variables.

    Requires integ ``_mkt`` and ``_rx`` (no session fallback).
    """
    mkt = _coerce_mkt(mkt)
    formal = set(range(1, int(total_rounds) + 1))
    mkt = mkt[mkt["round"].isin(formal)].copy()

    orders = _agent_round_orders(rx)
    panel = mkt.merge(orders, on=_KEY + ["round"], how="left")
    for c in (
        "buy_submitted",
        "sell_submitted",
        "buy_filled_qty",
        "buy_filled_cost",
        "sell_dummy",
        "buy_dummy",
    ):
        if c not in panel.columns:
            panel[c] = 0.0 if c != "sell_dummy" and c != "buy_dummy" else 0
        else:
            panel[c] = panel[c].fillna(0)

    panel = _compute_wapp_and_gain(
        panel,
        fundamental_value=fundamental_value,
        initial_stocks=initial_stocks,
    )

    panel["avg_expectation"] = panel.apply(_avg_expectation, axis=1)

    # Realized simple returns by session (market price path).
    panel = panel.sort_values(_KEY + ["round"])
    panel["ret"] = panel.groupby(_KEY, dropna=False)["mkt_prc"].pct_change()
    for lag in range(1, 5):
        panel[f"ret_lag{lag}"] = panel.groupby(_KEY, dropna=False)["ret"].shift(lag)

    exp_rows = [
        _horizon_expected_returns(row, float(row["mkt_prc"]) if pd.notna(row["mkt_prc"]) else np.nan)
        for _, row in panel.iterrows()
    ]
    exp_df = pd.DataFrame(exp_rows)
    panel = pd.concat([panel.reset_index(drop=True), exp_df], axis=1)

    # Table 4: expectations at t explain buy at t+1.
    panel["buy_dummy_next"] = panel.groupby(_KEY, dropna=False)["buy_dummy"].shift(-1)

    # Stable column order: identity + behavior fields + leftover mkt fields.
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
        "stk_num",
        "wapp",
        "gain_dummy",
        "sell_dummy",
        "buy_dummy",
        "buy_dummy_next",
        "avg_expectation",
        "ret",
        "ret_lag1",
        "ret_lag2",
        "ret_lag3",
        "ret_lag4",
        "exp_ret_h0",
        "exp_ret_h2",
        "exp_ret_h5",
        "exp_ret_h10",
        "buy_submitted",
        "sell_submitted",
        "buy_filled_qty",
    ]
    cols = [c for c in front if c in panel.columns] + [
        c for c in panel.columns if c not in front
    ]
    return panel.loc[:, cols]


def load_behavior_inputs(out_dir: Path, group_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    from src.integ.paths import integ_csv

    mkt_path = integ_csv(out_dir, group_name, "mkt")
    rx_path = integ_csv(out_dir, group_name, "rx")
    if not mkt_path.is_file():
        raise FileNotFoundError(
            f"RUN_BEHAVIOR requires {mkt_path}; run integ first (no fallback)."
        )
    if not rx_path.is_file():
        raise FileNotFoundError(
            f"RUN_BEHAVIOR requires {rx_path}; run integ first (no fallback)."
        )
    from src.integ.paths import read_table_csv

    return read_table_csv(mkt_path), read_table_csv(rx_path)
