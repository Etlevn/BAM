"""
Paper Table 6 — Disagreement & Trading Volume（预期分歧与成交量）

含义：用同期 Agent 平均价格预期的横截面标准差衡量分歧，
检验异质预期是否与更高美元成交量相关。

Y: dollar_volume = P(t) * V(t)
X: disagreement = cross-sectional SD of agents' average forecast prices
FE / cluster (locked; market-level panel):
  Spec 1: Y ~ X                         (no FE)
  Spec 2: Y ~ X | Round FE
  Spec 3: Y ~ X | Simulation FE
  Spec 4: Y ~ X | Round + Simulation + Market Type FE
cluster = session (simulation)
Market Type FE = mode
Input:  _<GROUP>/panels/<GROUP>_equilibrium.csv
Output: _<GROUP>/<GROUP>_disagreement.csv
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

_OUTCOME = "dollar_volume"
_REGRESSOR = "disagreement"
_REQUIRED_COLS = (
    _OUTCOME,
    _REGRESSOR,
    "session",
    "round",
    "mode",
)

@dataclass(frozen=True)
class DisagreementSpec:
    spec: int
    fml: str
    fe_round: bool
    fe_simulation: bool
    fe_market_type: bool

def _fml(*, fe_round: bool, fe_simulation: bool, fe_market_type: bool) -> str:
    fe_parts: list[str] = []
    if fe_round:
        fe_parts.append("round")
    if fe_simulation:
        fe_parts.append("session")
    if fe_market_type:
        fe_parts.append("mode")
    rhs = f"{_OUTCOME} ~ {_REGRESSOR}"
    if not fe_parts:
        return rhs
    return f"{rhs} | {' + '.join(fe_parts)}"

def _spec(
    spec: int,
    *,
    fe_round: bool,
    fe_simulation: bool,
    fe_market_type: bool,
) -> DisagreementSpec:
    return DisagreementSpec(
        spec=spec,
        fml=_fml(
            fe_round=fe_round,
            fe_simulation=fe_simulation,
            fe_market_type=fe_market_type,
        ),
        fe_round=fe_round,
        fe_simulation=fe_simulation,
        fe_market_type=fe_market_type,
    )

# Locked FE columns for disagreement → next price change:
# (1) none; (2) Round; (3) Simulation; (4) Round + Simulation + Market Type
SPECS: tuple[DisagreementSpec, ...] = (
    _spec(1, fe_round=False, fe_simulation=False, fe_market_type=False),
    _spec(2, fe_round=True, fe_simulation=False, fe_market_type=False),
    _spec(3, fe_round=False, fe_simulation=True, fe_market_type=False),
    _spec(4, fe_round=True, fe_simulation=True, fe_market_type=True),
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

def prepare_disagreement_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Validate equilibrium columns; coerce types for FE/cluster."""
    missing = [c for c in _REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"equilibrium panel missing columns: {missing}")
    out = df.copy()
    out["session"] = out["session"].astype(str)
    out["mode"] = out["mode"].astype(str)
    out["round"] = pd.to_numeric(out["round"], errors="coerce")
    out[_OUTCOME] = pd.to_numeric(out[_OUTCOME], errors="coerce")
    out[_REGRESSOR] = pd.to_numeric(out[_REGRESSOR], errors="coerce")
    return out

def _coef_rows(
    fit: Any,
    *,
    group: str,
    spec: DisagreementSpec,
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
                "outcome": _OUTCOME,
                "term": str(term),
                "coef": float(row["Estimate"]),
                "std_err": float(row["Std. Error"]),
                "t": float(row["t value"]),
                "p": p,
                "star": _stars(p),
                "n": n,
                "adj_r2": adj_r2,
                "fe_round": spec.fe_round,
                "fe_simulation": spec.fe_simulation,
                "fe_market_type": spec.fe_market_type,
                "cluster": "session",
            }
        )
    return rows

def fit_disagreement_specs(
    df: pd.DataFrame,
    *,
    group: str,
    print_summary: bool = True,
) -> tuple[list[Any], pd.DataFrame]:
    """Fit locked specs 1–4; SE clustered at simulation (``session``)."""
    panel = prepare_disagreement_frame(df)
    fits: list[Any] = []
    rows: list[dict[str, Any]] = []

    base = panel.dropna(subset=[_OUTCOME, _REGRESSOR, "session", "round", "mode"]).copy()

    for spec in SPECS:
        fit = feols(spec.fml, data=base, vcov={"CRV1": "session"})
        fits.append(fit)
        if print_summary:
            print(f"\n=== group={group} disagreement spec={spec.spec} ===")
            fit.summary()
        rows.extend(_coef_rows(fit, group=group, spec=spec))

    return fits, pd.DataFrame(rows)

def equilibrium_csv_path(out_dir: Path, group_name: str) -> Path:
    return panel_csv(out_dir, group_name, "equilibrium")

def load_equilibrium_panel(out_dir: Path, group_name: str) -> pd.DataFrame:
    path = equilibrium_csv_path(out_dir, group_name)
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing equilibrium panel: {path}. "
            "Run anal.py with RUN_EQUILIBRIUM=True first."
        )
    return read_table_csv(path)

def run_disagreement_group(
    group: str,
    *,
    exp_root: Path | None = None,
    print_summary: bool = True,
) -> Path:
    """Fit specs 1–4 for one group; write ``_<GROUP>/<GROUP>_disagreement.csv``."""
    root = Path(exp_root) if exp_root is not None else Path(config.EXP_DIR)
    group_dir = resolve_group_dir(root, group)
    if group_dir is None:
        raise FileNotFoundError(f"Group folder not found under {root}: {group!r}")

    group_name = group_dir.name
    out_dir = ensure_cased_path(group_dir / f"_{group_name}")
    equilibrium = load_equilibrium_panel(out_dir, group_name)
    _fits, coefs = fit_disagreement_specs(
        equilibrium, group=group_name, print_summary=print_summary
    )
    out_path = research_csv(out_dir, group_name, "disagreement")
    write_table_csv(coefs, out_path)
    print(f"Saved {len(coefs)} coef rows → {out_path}")
    return out_path

def run_disagreement_groups(
    groups: list[str],
    *,
    exp_root: Path | None = None,
    print_summary: bool = True,
) -> list[Path]:
    if not groups:
        raise ValueError("GROUPS is empty")
    return [
        run_disagreement_group(g, exp_root=exp_root, print_summary=print_summary)
        for g in groups
    ]
