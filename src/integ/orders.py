"""Build order/trade rows (rx) from market/r*.csv."""

from __future__ import annotations

import pandas as pd

from src.integ.columns import order_leading_columns
from src.integ.session import SessionMeta, market_rounds


def build_orders(meta: SessionMeta) -> pd.DataFrame:
    rounds = market_rounds(meta.path)
    if not rounds:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    market_dir = meta.path / "market"
    for round_num in rounds:
        csv_file = market_dir / f"r{round_num}.csv"
        if not csv_file.is_file():
            continue
        try:
            df = pd.read_csv(csv_file)
        except Exception:
            continue
        if df.empty:
            continue
        out = df.copy()
        out["group"] = meta.group
        out["series"] = meta.series
        out["session"] = meta.simulation_index
        out["bas"] = meta.bas
        out["market_type"] = meta.market_type
        out["round"] = round_num
        if "llm" in out.columns:
            out["llm_type"] = out["llm"].map(meta.assignments)
        else:
            out["llm"] = None
            out["llm_type"] = None
        frames.append(out)

    if not frames:
        return pd.DataFrame()
    return order_leading_columns(pd.concat(frames, ignore_index=True))
