"""
Paper Table 4 — Belief–Action Coupling（信念—行动传导）

含义：检验当期多期限预期收益是否系统影响下一期净买入（Buy Dummy），
比较不同预测期限对交易决策的传导强度。

Y: buy_dummy_next  (net buy at t+1)
X: one of exp_ret_h0 / h2 / h5 / h10 at t (one horizon per column pair)
FE / cluster (locked):
  Spec 1: buy_dummy_next ~ exp_ret_h0  | Investor FE; cluster agent
  Spec 2: buy_dummy_next ~ exp_ret_h0  | Investor + Round + Simulation FE; cluster agent
  Spec 3: buy_dummy_next ~ exp_ret_h2  | Investor FE; cluster agent
  Spec 4: buy_dummy_next ~ exp_ret_h2  | Investor + Round + Simulation FE; cluster agent
  Spec 5: buy_dummy_next ~ exp_ret_h5  | Investor FE; cluster agent
  Spec 6: buy_dummy_next ~ exp_ret_h5  | Investor + Round + Simulation FE; cluster agent
  Spec 7: buy_dummy_next ~ exp_ret_h10 | Investor FE; cluster agent
  Spec 8: buy_dummy_next ~ exp_ret_h10 | Investor + Round + Simulation FE; cluster agent
agent id = "{session}|{llm}"
Input:  _<GROUP>/panels/<GROUP>_behavior.csv
Output: _<GROUP>/<GROUP>_belief_action.csv
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

_OUTCOME = "buy_dummy_next"
_REQUIRED_COLS = (
    _OUTCOME,
    "exp_ret_h0",
    "exp_ret_h2",
    "exp_ret_h5",
    "exp_ret_h10",
    "session",
    "llm",
    "round",
)

@dataclass(frozen=True)
class BeliefActionSpec:
    spec: int
    regressor: str
    fml: str
    fe_investor: bool
    fe_round: bool
    fe_simulation: bool

def _spec(spec: int, regressor: str, *, full_fe: bool) -> BeliefActionSpec:
    fe = "agent_id + round + session" if full_fe else "agent_id"
    return BeliefActionSpec(
        spec=spec,
        regressor=regressor,
        fml=f"{_OUTCOME} ~ {regressor} | {fe}",
        fe_investor=True,
        fe_round=full_fe,
        fe_simulation=full_fe,
    )

# Paper-locked; not user-configurable.
# Odd = Investor FE only; even = Investor + Round + Simulation FE.
SPECS: tuple[BeliefActionSpec, ...] = (
    _spec(1, "exp_ret_h0", full_fe=False),
    _spec(2, "exp_ret_h0", full_fe=True),
    _spec(3, "exp_ret_h2", full_fe=False),
    _spec(4, "exp_ret_h2", full_fe=True),
    _spec(5, "exp_ret_h5", full_fe=False),
    _spec(6, "exp_ret_h5", full_fe=True),
    _spec(7, "exp_ret_h10", full_fe=False),
    _spec(8, "exp_ret_h10", full_fe=True),
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

def prepare_belief_action_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Validate columns and add ``agent_id`` = ``{session}|{llm}``."""
    missing = [c for c in _REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"behavior panel missing columns: {missing}")
    out = df.copy()
    out["session"] = out["session"].astype(str)
    out["llm"] = out["llm"].astype(str)
    out["agent_id"] = out["session"] + "|" + out["llm"]
    out["round"] = pd.to_numeric(out["round"], errors="coerce")
    for c in (
        _OUTCOME,
        "exp_ret_h0",
        "exp_ret_h2",
        "exp_ret_h5",
        "exp_ret_h10",
    ):
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out

def _coef_rows(
    fit: Any,
    *,
    group: str,
    spec: BeliefActionSpec,
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
                "fe_investor": spec.fe_investor,
                "fe_round": spec.fe_round,
                "fe_simulation": spec.fe_simulation,
                "cluster": "agent",
            }
        )
    return rows

def fit_belief_action_specs(
    df: pd.DataFrame,
    *,
    group: str,
    print_summary: bool = True,
) -> tuple[list[Any], pd.DataFrame]:
    """Fit locked specs 1–8 (one expectation horizon per pair of FE sets)."""
    panel = prepare_belief_action_frame(df)
    fits: list[Any] = []
    rows: list[dict[str, Any]] = []

    for spec in SPECS:
        subset = [_OUTCOME, spec.regressor, "agent_id", "round"]
        if spec.fe_simulation:
            subset.append("session")
        data = panel.dropna(subset=subset).copy()

        fit = feols(spec.fml, data=data, vcov={"CRV1": "agent_id"})
        fits.append(fit)
        if print_summary:
            print(
                f"\n=== group={group} belief_action spec={spec.spec} "
                f"({_OUTCOME} ~ {spec.regressor}) ==="
            )
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

def run_belief_action_group(
    group: str,
    *,
    exp_root: Path | None = None,
    print_summary: bool = True,
) -> Path:
    """Fit specs 1–8 for one group; write ``_<GROUP>/<GROUP>_belief_action.csv``."""
    root = Path(exp_root) if exp_root is not None else Path(config.EXP_DIR)
    group_dir = resolve_group_dir(root, group)
    if group_dir is None:
        raise FileNotFoundError(f"Group folder not found under {root}: {group!r}")

    group_name = group_dir.name
    out_dir = ensure_cased_path(group_dir / f"_{group_name}")
    behavior = load_behavior_panel(out_dir, group_name)
    _fits, coefs = fit_belief_action_specs(
        behavior, group=group_name, print_summary=print_summary
    )
    out_path = research_csv(out_dir, group_name, "belief_action")
    write_table_csv(coefs, out_path)
    print(f"Saved {len(coefs)} coef rows → {out_path}")
    return out_path

def run_belief_action_groups(
    groups: list[str],
    *,
    exp_root: Path | None = None,
    print_summary: bool = True,
) -> list[Path]:
    if not groups:
        raise ValueError("GROUPS is empty")
    return [
        run_belief_action_group(g, exp_root=exp_root, print_summary=print_summary)
        for g in groups
    ]
