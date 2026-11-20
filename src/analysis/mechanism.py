"""Agent–round–mechanism panel for Table 9 (bubble vs non-bubble scores)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Keep in sync with nlp.py MECHANISM_ORDER / Table 11.
MECHANISM_ORDER: tuple[str, ...] = (
    "rational_speculative_bubble",
    "synchronization_risk",
    "asymmetric_information",
    "extrapolation_vs_anchor",
    "diagnostic_expectations",
    "wavering_behavior",
    "disposition_effect",
    "momentum_vs_newswatcher",
    "feedback_trading",
    "overconfidence",
    "self_attribution_bias",
    "herding_contagion",
    "disagreement_heterogeneous_beliefs",
    "representativeness_heuristic",
    "new_era_thinking",
    "availability_bias",
    "limited_arbitrage_awareness",
    "loss_aversion",
    "narrative_tone",
    "statistical_testing",
)

_KEY = ["group", "series", "session", "llm"]


def parse_mechanism_scores(nlp_payload: Any) -> dict[str, float]:
    """
    Extract mechanism_id → numeric_score from a plan_nlp / insight_nlp cell.

    Missing / invalid JSON → empty dict (callers fill NaN per id).
    """
    if nlp_payload is None:
        return {}
    if isinstance(nlp_payload, float) and np.isnan(nlp_payload):
        return {}
    if isinstance(nlp_payload, dict):
        data = nlp_payload
    else:
        text = str(nlp_payload).strip()
        if not text or text.lower() in {"nan", "none", "null"}:
            return {}
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return {}
    if not isinstance(data, dict):
        return {}
    assessments = data.get("mechanism_assessments")
    if not isinstance(assessments, list):
        return {}
    out: dict[str, float] = {}
    for item in assessments:
        if not isinstance(item, dict):
            continue
        mid = item.get("mechanism_id")
        score = item.get("numeric_score")
        if mid is None or score is None:
            continue
        try:
            out[str(mid)] = float(score)
        except (TypeError, ValueError):
            continue
    return out


def build_mechanism_panel(
    mkt: pd.DataFrame,
    output_nlp: pd.DataFrame,
    *,
    fundamental_value: float = 14.0,
    total_rounds: int = 20,
    mechanism_order: tuple[str, ...] | list[str] | None = None,
) -> pd.DataFrame:
    """
    Long panel: agent × round × mechanism.

    ``bubble`` = 1{P_t > FV} (strict). Scores from ``plan_nlp`` / ``insight_nlp``.
    Requires integ ``_mkt`` and NLP ``_output_nlp`` (no fallback).
    """
    order = tuple(mechanism_order) if mechanism_order is not None else MECHANISM_ORDER
    mkt = mkt.copy()
    mkt["round"] = pd.to_numeric(mkt["round"], errors="coerce")
    mkt["mkt_prc"] = pd.to_numeric(mkt.get("mkt_prc"), errors="coerce")
    mkt = mkt.dropna(subset=["round", "session", "llm"])
    mkt["round"] = mkt["round"].astype(int)
    formal = set(range(1, int(total_rounds) + 1))
    mkt = mkt[mkt["round"].isin(formal)].copy()

    nlp = output_nlp.copy()
    nlp["round"] = pd.to_numeric(nlp["round"], errors="coerce")
    nlp = nlp.dropna(subset=["round", "session", "llm"])
    nlp["round"] = nlp["round"].astype(int)
    nlp = nlp[nlp["round"].isin(formal)].copy()

    merge_keys = [c for c in _KEY if c in mkt.columns and c in nlp.columns] + ["round"]
    score_cols = [c for c in ("plan_nlp", "insight_nlp") if c in nlp.columns]
    meta_keep = [
        c
        for c in (
            "group",
            "series",
            "session",
            "market_type",
            "bas",
            "round",
            "llm",
            "llm_type",
            "mkt_prc",
        )
        if c in mkt.columns
    ]
    nlp_keep = merge_keys + score_cols
    nlp = nlp.loc[:, nlp_keep].drop_duplicates(subset=merge_keys, keep="first")

    base = mkt.loc[:, meta_keep].merge(nlp, on=merge_keys, how="left")
    base["bubble"] = (
        pd.to_numeric(base["mkt_prc"], errors="coerce") > float(fundamental_value)
    ).astype(int)

    if "plan_nlp" not in base.columns:
        base["plan_nlp"] = np.nan
    if "insight_nlp" not in base.columns:
        base["insight_nlp"] = np.nan

    plan_maps = [parse_mechanism_scores(v) for v in base["plan_nlp"]]
    insight_maps = [parse_mechanism_scores(v) for v in base["insight_nlp"]]

    rows: list[dict] = []
    for pos, (_, row) in enumerate(base.iterrows()):
        pmap = plan_maps[pos]
        imap = insight_maps[pos]
        for mid in order:
            rows.append(
                {
                    "group": row.get("group"),
                    "series": row.get("series"),
                    "session": row.get("session"),
                    "market_type": row.get("market_type"),
                    "bas": row.get("bas"),
                    "round": int(row["round"]),
                    "llm": row.get("llm"),
                    "llm_type": row.get("llm_type"),
                    "mkt_prc": row.get("mkt_prc"),
                    "bubble": int(row["bubble"]),
                    "mechanism_id": mid,
                    "score_plan": pmap.get(mid, float("nan")),
                    "score_insight": imap.get(mid, float("nan")),
                }
            )

    out = pd.DataFrame(rows)
    front = [
        "group",
        "series",
        "session",
        "market_type",
        "bas",
        "round",
        "llm",
        "llm_type",
        "mkt_prc",
        "bubble",
        "mechanism_id",
        "score_plan",
        "score_insight",
    ]
    return out.loc[:, front]


def load_mechanism_inputs(
    out_dir: Path, group_name: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    mkt_path = out_dir / f"{group_name}_mkt.csv"
    nlp_path = out_dir / f"{group_name}_output_nlp.csv"
    if not mkt_path.is_file():
        raise FileNotFoundError(
            f"RUN_MECHANISM requires {mkt_path}; run integ first (no fallback)."
        )
    if not nlp_path.is_file():
        raise FileNotFoundError(
            f"RUN_MECHANISM requires {nlp_path}; run nlp RUN_POST first (no fallback)."
        )
    return pd.read_csv(mkt_path), pd.read_csv(nlp_path)
