"""
Paper Table 8 — Reasoning → Trading（文字推理 → 交易行为）

含义：用当期 Plans/Insights 的 Stated Action 解释下一期净买入，
比较两类文本对真实交易方向的预测力。

Y: buy_dummy_next
X: stated_action_plan or stated_action_insight (one per column)
FE / cluster (locked):
  Spec 1: buy_dummy_next ~ stated_action_plan    | Investor FE; cluster session
  Spec 2: buy_dummy_next ~ stated_action_plan    | Investor+Round+Simulation FE; cluster session
  Spec 3: buy_dummy_next ~ stated_action_insight | Investor FE; cluster session
  Spec 4: buy_dummy_next ~ stated_action_insight | full FE; cluster session
agent id (Investor FE) = "{session}|{llm}"
Input:  _<GROUP>/panels/<GROUP>_cognition.csv
Output: _<GROUP>/<GROUP>_stated_action.csv
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
    "stated_action_plan",
    "stated_action_insight",
    "session",
    "llm",
    "round",
)

@dataclass(frozen=True)
class StatedActionSpec:
    spec: int
    regressor: str
    fml: str
    fe_investor: bool
    fe_round: bool
    fe_simulation: bool

def _spec(spec: int, regressor: str, *, full_fe: bool) -> StatedActionSpec:
    fe = "agent_id + round + session" if full_fe else "agent_id"
    return StatedActionSpec(
        spec=spec,
        regressor=regressor,
        fml=f"{_OUTCOME} ~ {regressor} | {fe}",
        fe_investor=True,
        fe_round=full_fe,
        fe_simulation=full_fe,
    )

# Paper-locked; cluster at simulation (session).
SPECS: tuple[StatedActionSpec, ...] = (
    _spec(1, "stated_action_plan", full_fe=False),
    _spec(2, "stated_action_plan", full_fe=True),
    _spec(3, "stated_action_insight", full_fe=False),
    _spec(4, "stated_action_insight", full_fe=True),
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

def prepare_stated_action_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Validate cognition columns and add ``agent_id``."""
    missing = [c for c in _REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"cognition panel missing columns: {missing}")
    out = df.copy()
    out["session"] = out["session"].astype(str)
    out["llm"] = out["llm"].astype(str)
    out["agent_id"] = out["session"] + "|" + out["llm"]
    out["round"] = pd.to_numeric(out["round"], errors="coerce")
    for c in (_OUTCOME, "stated_action_plan", "stated_action_insight"):
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out

def _coef_rows(
    fit: Any,
    *,
    group: str,
    spec: StatedActionSpec,
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
                "cluster": "session",
            }
        )
    return rows

def fit_stated_action_specs(
    df: pd.DataFrame,
    *,
    group: str,
    print_summary: bool = True,
) -> tuple[list[Any], pd.DataFrame]:
    """Fit locked specs 1–4; SE clustered at ``session``."""
    panel = prepare_stated_action_frame(df)
    fits: list[Any] = []
    rows: list[dict[str, Any]] = []

    for spec in SPECS:
        subset = [_OUTCOME, spec.regressor, "agent_id", "round", "session"]
        data = panel.dropna(subset=subset).copy()

        fit = feols(spec.fml, data=data, vcov={"CRV1": "session"})
        fits.append(fit)
        if print_summary:
            print(
                f"\n=== group={group} stated_action spec={spec.spec} "
                f"({_OUTCOME} ~ {spec.regressor}) ==="
            )
            fit.summary()
        rows.extend(_coef_rows(fit, group=group, spec=spec))

    return fits, pd.DataFrame(rows)

def cognition_csv_path(out_dir: Path, group_name: str) -> Path:
    return panel_csv(out_dir, group_name, "cognition")

def load_cognition_panel(out_dir: Path, group_name: str) -> pd.DataFrame:
    path = cognition_csv_path(out_dir, group_name)
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing cognition panel: {path}. "
            "Run anal.py with RUN_COGNITION=True first."
        )
    return read_table_csv(path)

def run_stated_action_group(
    group: str,
    *,
    exp_root: Path | None = None,
    print_summary: bool = True,
) -> Path:
    """Fit specs 1–4 for one group; write ``_<GROUP>/<GROUP>_stated_action.csv``."""
    root = Path(exp_root) if exp_root is not None else Path(config.EXP_DIR)
    group_dir = resolve_group_dir(root, group)
    if group_dir is None:
        raise FileNotFoundError(f"Group folder not found under {root}: {group!r}")

    group_name = group_dir.name
    out_dir = ensure_cased_path(group_dir / f"_{group_name}")
    cognition = load_cognition_panel(out_dir, group_name)
    _fits, coefs = fit_stated_action_specs(
        cognition, group=group_name, print_summary=print_summary
    )
    out_path = research_csv(out_dir, group_name, "stated_action")
    write_table_csv(coefs, out_path)
    print(f"Saved {len(coefs)} coef rows → {out_path}")
    return out_path

def run_stated_action_groups(
    groups: list[str],
    *,
    exp_root: Path | None = None,
    print_summary: bool = True,
) -> list[Path]:
    if not groups:
        raise ValueError("GROUPS is empty")
    return [
        run_stated_action_group(g, exp_root=exp_root, print_summary=print_summary)
        for g in groups
    ]
