"""
Paper Table 2 — Disposition Effect（处置效应）

含义：检验相对持仓成本（WAPP）浮盈时，Agent 是否更倾向卖出；
控制多期限平均预期后，看 Gain Dummy 对 Sell Dummy 是否仍显著。

Y: sell_dummy
X: gain_dummy; specs 3–4 also avg_expectation
FE / cluster (locked):
  Spec 1: sell_dummy ~ gain_dummy | Investor FE; cluster agent
  Spec 2: sell_dummy ~ gain_dummy | Investor + Round + Simulation FE; cluster agent
  Spec 3: sell_dummy ~ gain_dummy + avg_expectation | Investor FE; cluster agent
  Spec 4: sell_dummy ~ gain_dummy + avg_expectation | Investor + Round + Simulation FE; cluster agent
agent id = "{session}|{llm}"
Input:  _<GROUP>/panels/<GROUP>_behavior.csv
Output: _<GROUP>/<GROUP>_disposition.csv
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dataclasses import dataclass

import pandas as pd
from pyfixest.estimation import feols
import config
from src.integ.paths import ensure_cased_path, panel_csv, read_table_csv, research_csv, write_table_csv
from src.integ.runner import resolve_group_dir

_REQUIRED_COLS = (
    "sell_dummy",
    "gain_dummy",
    "avg_expectation",
    "session",
    "llm",
    "round",
)

@dataclass(frozen=True)
class DispositionSpec:
    spec: int
    fml: str
    fe_investor: bool
    fe_round: bool
    fe_simulation: bool
    needs_avg_expectation: bool

# Paper-locked; not user-configurable.
SPECS: tuple[DispositionSpec, ...] = (
    DispositionSpec(
        spec=1,
        fml="sell_dummy ~ gain_dummy | agent_id",
        fe_investor=True,
        fe_round=False,
        fe_simulation=False,
        needs_avg_expectation=False,
    ),
    DispositionSpec(
        spec=2,
        fml="sell_dummy ~ gain_dummy | agent_id + round + session",
        fe_investor=True,
        fe_round=True,
        fe_simulation=True,
        needs_avg_expectation=False,
    ),
    DispositionSpec(
        spec=3,
        fml="sell_dummy ~ gain_dummy + avg_expectation | agent_id",
        fe_investor=True,
        fe_round=False,
        fe_simulation=False,
        needs_avg_expectation=True,
    ),
    DispositionSpec(
        spec=4,
        fml="sell_dummy ~ gain_dummy + avg_expectation | agent_id + round + session",
        fe_investor=True,
        fe_round=True,
        fe_simulation=True,
        needs_avg_expectation=True,
    ),
)

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

def prepare_disposition_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Validate columns and add ``agent_id`` = ``{session}|{llm}``."""
    missing = [c for c in _REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"behavior panel missing columns: {missing}")
    out = df.copy()
    out["session"] = out["session"].astype(str)
    out["llm"] = out["llm"].astype(str)
    out["agent_id"] = out["session"] + "|" + out["llm"]
    out["round"] = pd.to_numeric(out["round"], errors="coerce")
    for c in ("sell_dummy", "gain_dummy", "avg_expectation"):
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out

def _coef_rows(
    fit: Any,
    *,
    group: str,
    spec: DispositionSpec,
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
                "spec": spec.spec,
                "term": str(term),
                "coef": float(row["Estimate"]),
                "std_err": float(row["Std. Error"]),
                "t": float(row["t value"]),
                "p": p,
                "star": _stars(p),
                "n": n,
                "adj_r2": adj_r2,
                "fe_investor": spec.fe_investor,
                "fe_round": spec.fe_round,
                "fe_simulation": spec.fe_simulation,
                "cluster": "agent",
            }
        )
    return rows

def fit_disposition_specs(
    df: pd.DataFrame,
    *,
    group: str,
    print_summary: bool = True,
) -> tuple[list[Any], pd.DataFrame]:
    """
    Fit locked specs 1–4.

    Specs 3–4 listwise-drop rows with missing ``avg_expectation``.
    """
    panel = prepare_disposition_frame(df)
    fits: list[Any] = []
    rows: list[dict[str, Any]] = []

    for spec in SPECS:
        data = panel
        if spec.needs_avg_expectation:
            data = panel.dropna(subset=["avg_expectation"]).copy()
        # Base outcome / gain must be non-missing for all specs.
        data = data.dropna(subset=["sell_dummy", "gain_dummy", "agent_id", "round"])
        if spec.fe_simulation:
            data = data.dropna(subset=["session"])

        fit = feols(spec.fml, data=data, vcov={"CRV1": "agent_id"})
        fits.append(fit)
        if print_summary:
            print(f"\n=== group={group} disposition spec={spec.spec} ===")
            fit.summary()
        rows.extend(_coef_rows(fit, group=group, spec=spec))

    return fits, pd.DataFrame(rows)

def behavior_csv_path(out_dir: Path, group_name: str) -> Path:
    return panel_csv(out_dir, group_name, "behavior")

def load_behavior_panel(out_dir: Path, group_name: str) -> pd.DataFrame:
    path = behavior_csv_path(out_dir, group_name)
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing behavior panel: {path}. "
            "Run anal.py with RUN_BEHAVIOR=True first."
        )
    return read_table_csv(path)

def run_disposition_group(
    group: str,
    *,
    exp_root: Path | None = None,
    print_summary: bool = True,
) -> Path:
    """Fit specs 1–4 for one group; write ``_<GROUP>/<GROUP>_disposition.csv``."""
    root = Path(exp_root) if exp_root is not None else Path(config.EXP_DIR)
    group_dir = resolve_group_dir(root, group)
    if group_dir is None:
        raise FileNotFoundError(f"Group folder not found under {root}: {group!r}")

    group_name = group_dir.name
    out_dir = ensure_cased_path(group_dir / f"_{group_name}")
    behavior = load_behavior_panel(out_dir, group_name)
    _fits, coefs = fit_disposition_specs(
        behavior, group=group_name, print_summary=print_summary
    )
    out_path = research_csv(out_dir, group_name, "disposition")
    write_table_csv(coefs, out_path)
    print(f"Saved {len(coefs)} coef rows → {out_path}")
    return out_path

def run_disposition_groups(
    groups: list[str],
    *,
    exp_root: Path | None = None,
    print_summary: bool = True,
) -> list[Path]:
    if not groups:
        raise ValueError("GROUPS is empty")
    return [
        run_disposition_group(g, exp_root=exp_root, print_summary=print_summary)
        for g in groups
    ]
