"""Session–round equilibrium panel for Tables 5–6 (from integ _mkt + _rx)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

_SESS_KEY = ["group", "series", "session"]


def _session_round_prices(mkt: pd.DataFrame) -> pd.DataFrame:
    df = mkt.copy()
    df["round"] = pd.to_numeric(df["round"], errors="coerce")
    df["mkt_prc"] = pd.to_numeric(df["mkt_prc"], errors="coerce")
    df["mkt_vol"] = pd.to_numeric(df["mkt_vol"], errors="coerce").fillna(0.0)
    df = df.dropna(subset=["session", "round", "mkt_prc"])
    df["round"] = df["round"].astype(int)
    keep = [c for c in _SESS_KEY + ["market_type", "bas", "round", "mkt_prc", "mkt_vol"] if c in df.columns]
    return (
        df.sort_values(_SESS_KEY + ["round"])
        .drop_duplicates(subset=_SESS_KEY + ["round"], keep="first")
        .loc[:, keep]
    )


def _bid_offer_by_round(rx: pd.DataFrame) -> pd.DataFrame:
    df = rx.copy()
    df["round"] = pd.to_numeric(df["round"], errors="coerce")
    df["num"] = pd.to_numeric(df["num"], errors="coerce").fillna(0.0)
    df["b/s"] = df["b/s"].astype(str).str.upper().str.strip()
    df = df.dropna(subset=["session", "round"])
    df["round"] = df["round"].astype(int)
    df["buy_q"] = np.where(df["b/s"].eq("BUY"), df["num"], 0.0)
    df["sell_q"] = np.where(df["b/s"].eq("SELL"), df["num"], 0.0)
    gcols = [c for c in _SESS_KEY if c in df.columns] + ["round"]
    out = (
        df.groupby(gcols, dropna=False, sort=False)
        .agg(buy_submitted=("buy_q", "sum"), sell_submitted=("sell_q", "sum"))
        .reset_index()
    )
    out["bid_offer_gap"] = out["buy_submitted"] - out["sell_submitted"]
    return out


def _agent_avg_expectation(mkt: pd.DataFrame) -> pd.DataFrame:
    df = mkt.copy()
    df["round"] = pd.to_numeric(df["round"], errors="coerce")
    for c in ("fcst_1_prc", "fcst_2_prc", "fcst_3_prc", "fcst_4_prc"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["session", "round", "llm"])
    df["round"] = df["round"].astype(int)
    fcst_cols = [c for c in ("fcst_1_prc", "fcst_2_prc", "fcst_3_prc", "fcst_4_prc") if c in df.columns]
    if not fcst_cols:
        df["avg_expectation"] = np.nan
    else:
        df["avg_expectation"] = df[fcst_cols].mean(axis=1, skipna=True)
    gcols = [c for c in _SESS_KEY if c in df.columns] + ["round", "llm"]
    return df.loc[:, gcols + ["avg_expectation"]]


def _disagreement_by_round(agent_exp: pd.DataFrame) -> pd.DataFrame:
    gcols = [c for c in _SESS_KEY if c in agent_exp.columns] + ["round"]

    def _std(s: pd.Series) -> float:
        vals = pd.to_numeric(s, errors="coerce").dropna()
        if len(vals) < 2:
            return float("nan")
        return float(vals.std(ddof=1))

    out = (
        agent_exp.groupby(gcols, dropna=False, sort=False)
        .agg(
            disagreement=("avg_expectation", _std),
            n_agents=("avg_expectation", lambda s: int(pd.to_numeric(s, errors="coerce").notna().sum())),
        )
        .reset_index()
    )
    return out


def build_equilibrium_panel(
    mkt: pd.DataFrame,
    rx: pd.DataFrame,
    *,
    total_rounds: int = 20,
) -> pd.DataFrame:
    """
    Session–round panel: bid–offer gap, ΔP_{t+1}, disagreement, dollar volume.
    """
    formal = set(range(1, int(total_rounds) + 1))
    prices = _session_round_prices(mkt)
    prices = prices[prices["round"].isin(formal)].copy()

    gaps = _bid_offer_by_round(rx)
    gaps = gaps[gaps["round"].isin(formal)]

    agent_exp = _agent_avg_expectation(mkt)
    agent_exp = agent_exp[agent_exp["round"].isin(formal)]
    disagree = _disagreement_by_round(agent_exp)

    panel = prices.merge(gaps, on=_SESS_KEY + ["round"], how="left")
    panel = panel.merge(disagree, on=_SESS_KEY + ["round"], how="left")

    panel = panel.sort_values(_SESS_KEY + ["round"])
    panel["price_change_next"] = panel.groupby(_SESS_KEY, dropna=False)["mkt_prc"].shift(
        -1
    ) - panel["mkt_prc"]
    panel["dollar_volume"] = panel["mkt_prc"] * panel["mkt_vol"]

    for c in ("bid_offer_gap", "buy_submitted", "sell_submitted"):
        if c in panel.columns:
            panel[c] = panel[c].fillna(0.0)
    if "n_agents" in panel.columns:
        panel["n_agents"] = panel["n_agents"].fillna(0).astype(int)

    front = [
        "group",
        "series",
        "session",
        "market_type",
        "bas",
        "round",
        "mkt_prc",
        "mkt_vol",
        "price_change_next",
        "bid_offer_gap",
        "buy_submitted",
        "sell_submitted",
        "disagreement",
        "dollar_volume",
        "n_agents",
    ]
    cols = [c for c in front if c in panel.columns] + [
        c for c in panel.columns if c not in front
    ]
    return panel.loc[:, cols]


def load_equilibrium_inputs(
    out_dir: Path, group_name: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    mkt_path = out_dir / f"{group_name}_mkt.csv"
    rx_path = out_dir / f"{group_name}_rx.csv"
    if not mkt_path.is_file():
        raise FileNotFoundError(
            f"RUN_EQUILIBRIUM requires {mkt_path}; run integ first (no fallback)."
        )
    if not rx_path.is_file():
        raise FileNotFoundError(
            f"RUN_EQUILIBRIUM requires {rx_path}; run integ first (no fallback)."
        )
    return pd.read_csv(mkt_path), pd.read_csv(rx_path)
