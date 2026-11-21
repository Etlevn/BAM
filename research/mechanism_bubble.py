"""
Paper Table 9 — Mechanisms in Bubble vs Non-Bubble（泡沫期认知机制）

含义：对 20 种行为/认知机制的 Plan/Insight NLP 评分，比较泡沫期
（P_t > FV）与非泡沫期的差异；系数 ≈ 论文表中的泡沫差额。

For each mechanism_id and score channel (plan / insight):
  score_* ~ bubble | Investor + Round + Simulation FE
cluster = agent (session|llm)
Difference in the paper table ≈ coef on bubble.

Input:  _<GROUP>/panels/<GROUP>_mechanism.csv  (anal RUN_MECHANISM; sgl + bas=nan panel)
Output: _<GROUP>/<GROUP>_mechanism_bubble.csv
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

from dataclasses import dataclass

import config
import numpy as np
import pandas as pd
from pyfixest.estimation import feols

from src.analysis.mechanism import MECHANISM_ORDER
from src.integ.paths import ensure_cased_path, panel_csv, read_table_csv, research_csv, write_table_csv
from src.integ.runner import resolve_group_dir

_REQUIRED_COLS = (
    "bubble",
    "mechanism_id",
    "score_plan",
    "score_insight",
    "session",
    "llm",
    "round",
)

_SCORE_COLS = ("score_plan", "score_insight")

@dataclass(frozen=True)
class MechanismBubbleSpec:
    mechanism_id: str
    outcome: str
    fml: str

def _stars(p: float) -> str:
    if pd.isna(p):
        return ""
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.1:
        return "*"
    return ""

def prepare_mechanism_bubble_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Validate mechanism panel columns and add ``agent_id``."""
    missing = [c for c in _REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"mechanism panel missing columns: {missing}")
    out = df.copy()
    out["session"] = out["session"].astype(str)
    out["llm"] = out["llm"].astype(str)
    out["agent_id"] = out["session"] + "|" + out["llm"]
    out["round"] = pd.to_numeric(out["round"], errors="coerce")
    out["bubble"] = pd.to_numeric(out["bubble"], errors="coerce")
    out["mechanism_id"] = out["mechanism_id"].astype(str)
    for c in _SCORE_COLS:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out

def _iter_specs(mechanism_ids: list[str]) -> list[MechanismBubbleSpec]:
    specs: list[MechanismBubbleSpec] = []
    for mid in mechanism_ids:
        for outcome in _SCORE_COLS:
            specs.append(
                MechanismBubbleSpec(
                    mechanism_id=mid,
                    outcome=outcome,
                    fml=f"{outcome} ~ bubble | agent_id + round + session",
                )
            )
    return specs

_MIN_STD = 1e-12

def _skip_msg(group: str, spec: MechanismBubbleSpec, reason: str) -> None:
    print(
        f"\n=== group={group} mechanism_bubble "
        f"{spec.mechanism_id} / {spec.outcome} SKIP ({reason}) ==="
    )

def _has_usable_score_variation(data: pd.DataFrame, outcome: str) -> bool:
    """False when scores are constant / all-zero (degenerate FE fit → nan t)."""
    y = pd.to_numeric(data[outcome], errors="coerce").dropna()
    if y.nunique(dropna=True) < 2:
        return False
    return float(y.std(ddof=0)) >= _MIN_STD

def _coef_rows(
    fit: Any,
    *,
    group: str,
    spec: MechanismBubbleSpec,
) -> list[dict[str, Any]]:
    tidy = fit.tidy()
    n = int(getattr(fit, "_N", len(tidy)))
    adj_r2 = float(getattr(fit, "_adj_r2", float("nan")))
    rows: list[dict[str, Any]] = []
    for term, row in tidy.iterrows():
        p = float(row["Pr(>|t|)"])
        rows.append(
            {
                "group": group,
                "mechanism_id": spec.mechanism_id,
                "outcome": spec.outcome,
                "term": str(term),
                "coef": float(row["Estimate"]),
                "std_err": float(row["Std. Error"]),
                "t": float(row["t value"]),
                "p": p,
                "star": _stars(p),
                "n": n,
                "adj_r2": adj_r2,
                "fe_investor": True,
                "fe_round": True,
                "fe_simulation": True,
                "cluster": "agent",
            }
        )
    return rows

def _bubble_inference_ok(rows: list[dict[str, Any]]) -> bool:
    bubble_rows = [r for r in rows if r["term"] == "bubble"]
    if not bubble_rows:
        return False
    t = bubble_rows[0]["t"]
    se = bubble_rows[0]["std_err"]
    return bool(np.isfinite(t) and np.isfinite(se))

def fit_mechanism_bubble_specs(
    df: pd.DataFrame,
    *,
    group: str,
    print_summary: bool = True,
) -> tuple[list[Any], pd.DataFrame]:
    """
    Fit score ~ bubble | FE for each mechanism × {score_plan, score_insight}.

    Reported ``Difference`` ≈ coefficient on ``bubble``.
    Specs with no score variation (nan t / zero RMSE) are skipped.
    """
    panel = prepare_mechanism_bubble_frame(df)
    present = set(panel["mechanism_id"].unique())
    ordered = [m for m in MECHANISM_ORDER if m in present]
    extras = sorted(present - set(MECHANISM_ORDER))
    mechanism_ids = ordered + extras
    if not mechanism_ids:
        raise ValueError("mechanism panel has no mechanism_id values")

    fits: list[Any] = []
    rows: list[dict[str, Any]] = []

    for spec in _iter_specs(mechanism_ids):
        sub = panel.loc[panel["mechanism_id"] == spec.mechanism_id].copy()
        data = sub.dropna(
            subset=[spec.outcome, "bubble", "agent_id", "round", "session"]
        )
        if data.empty:
            if print_summary:
                _skip_msg(group, spec, "empty after dropna")
            continue
        if data["bubble"].nunique(dropna=True) < 2:
            if print_summary:
                _skip_msg(group, spec, "bubble has no variation")
            continue
        if not _has_usable_score_variation(data, spec.outcome):
            if print_summary:
                _skip_msg(group, spec, "score has no residual variation")
            continue

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                fit = feols(spec.fml, data=data, vcov={"CRV1": "agent_id"})
                coef_rows = _coef_rows(fit, group=group, spec=spec)
        except ValueError as exc:
            if print_summary:
                _skip_msg(group, spec, str(exc).strip().splitlines()[0][:120])
            continue

        if not _bubble_inference_ok(coef_rows):
            if print_summary:
                _skip_msg(group, spec, "non-finite bubble t/SE")
            continue

        fits.append(fit)
        if print_summary:
            print(
                f"\n=== group={group} mechanism_bubble "
                f"{spec.mechanism_id} / {spec.outcome} ==="
            )
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                fit.summary()
        rows.extend(coef_rows)

    if not rows:
        raise ValueError(
            "No mechanism_bubble specs estimated "
            "(need non-missing scores and bubble variation)."
        )
    return fits, pd.DataFrame(rows)

def mechanism_csv_path(out_dir: Path, group_name: str) -> Path:
    return panel_csv(out_dir, group_name, "mechanism")

def load_mechanism_panel(out_dir: Path, group_name: str) -> pd.DataFrame:
    path = mechanism_csv_path(out_dir, group_name)
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing mechanism panel: {path}. "
            "Run anal.py with RUN_MECHANISM=True (requires nlp output) first."
        )
    return read_table_csv(path)

def run_mechanism_bubble_group(
    group: str,
    *,
    exp_root: Path | None = None,
    print_summary: bool = True,
) -> Path:
    """Fit all mechanism×score specs; write ``_<GROUP>/<GROUP>_mechanism_bubble.csv``."""
    root = Path(exp_root) if exp_root is not None else Path(config.EXP_DIR)
    group_dir = resolve_group_dir(root, group)
    if group_dir is None:
        raise FileNotFoundError(f"Group folder not found under {root}: {group!r}")

    group_name = group_dir.name
    out_dir = ensure_cased_path(group_dir / f"_{group_name}")
    mechanism = load_mechanism_panel(out_dir, group_name)
    _fits, coefs = fit_mechanism_bubble_specs(
        mechanism, group=group_name, print_summary=print_summary
    )
    out_path = research_csv(out_dir, group_name, "mechanism_bubble")
    write_table_csv(coefs, out_path)
    print(f"Saved {len(coefs)} coef rows → {out_path}")
    return out_path

def run_mechanism_bubble_groups(
    groups: list[str],
    *,
    exp_root: Path | None = None,
    print_summary: bool = True,
) -> list[Path]:
    if not groups:
        raise ValueError("GROUPS is empty")
    return [
        run_mechanism_bubble_group(g, exp_root=exp_root, print_summary=print_summary)
        for g in groups
    ]

