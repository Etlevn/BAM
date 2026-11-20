"""Scan selected exp groups and write analysis CSVs under _<GROUP>/."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

import config
from src.analysis.market import build_market_row
from src.analysis.plots import plot_group
from src.analysis.rationality import build_rational_row
from src.analysis.robustness import summarize_by_series
from src.integ.runner import ensure_cased_path, resolve_group_dir
from src.integ.session import SessionMeta, classify_group_sessions
from src.support.progress import track


MARKET_METRICS = ("mse", "amplitude", "pv_variance")
RATIONAL_METRICS = (
    "mse",
    "mean_error",
    "std_error",
    "skewness",
    "kurtosis",
    "t_stat_error",
    "p_val_error",
    "ar1_coef",
    "ar1_pval",
    "dw_stat",
)

_MARKET_COLUMNS = [
    "group",
    "series",
    "session",
    "rounds",
    "mse",
    "amplitude",
    "pv_variance",
]
_RATIONAL_COLUMNS = [
    "group",
    "series",
    "session",
    "mse",
    "mean_error",
    "std_error",
    "skewness",
    "kurtosis",
    "t_stat_error",
    "p_val_error",
    "ar1_coef",
    "ar1_pval",
    "dw_stat",
]


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path = ensure_cased_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"Saved {len(df)} rows → {path}")


def _fundamental_value() -> float:
    return float(config.EXPERIMENT_CONFIG.get("stock_value", 14))


def _total_rounds() -> int:
    return int(config.EXPERIMENT_CONFIG.get("total_rounds", 20))


def run_group(
    group: str,
    *,
    run_market: bool = True,
    run_market_robust: bool = True,
    run_rational: bool = True,
    run_rational_robust: bool = True,
    run_plots: bool = False,
    plots_folder: str = "plots",
    exp_root: Path | None = None,
) -> dict[str, Path]:
    root = Path(exp_root) if exp_root is not None else Path(config.EXP_DIR)
    group_dir = resolve_group_dir(root, group)
    if group_dir is None:
        return {}

    group_name = group_dir.name
    out_dir = ensure_cased_path(group_dir / f"_{group_name}")
    fv = _fundamental_value()
    total_rounds = _total_rounds()

    classified = classify_group_sessions(group_dir)
    sessions = classified.complete
    if not sessions:
        return {}

    # Plots need the same session metrics as market (title line).
    need_market = run_market or run_plots

    # One bar for all session-level work units in this group.
    work: list[tuple[str, SessionMeta]] = []
    if need_market:
        work.extend(("market", meta) for meta in sessions)
    if run_rational:
        work.extend(("rational", meta) for meta in sessions)

    market_rows: list[dict] = []
    rational_rows: list[dict] = []

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for kind, meta in track(work, label=f"anal {group_name}"):
            if kind == "market":
                row = build_market_row(
                    meta, fundamental_value=fv, total_rounds=total_rounds
                )
                if row is not None:
                    market_rows.append(row)
            else:
                row = build_rational_row(meta, total_rounds=total_rounds)
                if row is not None:
                    rational_rows.append(row)

    written: dict[str, Path] = {}

    if run_market:
        market_df = (
            pd.DataFrame(market_rows)
            if market_rows
            else pd.DataFrame(columns=_MARKET_COLUMNS)
        )
        market_path = out_dir / f"{group_name}_market.csv"
        _write_csv(market_df, market_path)
        written["market"] = market_path

        if run_market_robust:
            market_rob = summarize_by_series(market_df, MARKET_METRICS)
            market_rob_path = out_dir / f"{group_name}_market_robust.csv"
            _write_csv(market_rob, market_rob_path)
            written["market_robust"] = market_rob_path

    if run_rational:
        rational_df = (
            pd.DataFrame(rational_rows)[_RATIONAL_COLUMNS].round(4)
            if rational_rows
            else pd.DataFrame(columns=_RATIONAL_COLUMNS)
        )
        rational_path = out_dir / f"{group_name}_rational.csv"
        _write_csv(rational_df, rational_path)
        written["rational"] = rational_path

        if run_rational_robust:
            rational_rob = summarize_by_series(rational_df, RATIONAL_METRICS)
            rational_rob_path = out_dir / f"{group_name}_rational_robust.csv"
            _write_csv(rational_rob, rational_rob_path)
            written["rational_robust"] = rational_rob_path

    if run_plots:
        folder = str(plots_folder or "plots").strip() or "plots"
        plots_root = out_dir / folder
        written["plots"] = plot_group(
            sessions,
            market_rows,
            plots_root=plots_root,
            fundamental_value=fv,
            min_rounds=total_rounds,
        )

    return written


def run_groups(
    groups: Sequence[str] | Iterable[str],
    *,
    run_market: bool = True,
    run_market_robust: bool = True,
    run_rational: bool = True,
    run_rational_robust: bool = True,
    run_plots: bool = False,
    plots_folder: str = "plots",
    exp_root: Path | None = None,
) -> dict[str, dict[str, Path]]:
    results: dict[str, dict[str, Path]] = {}
    for group in groups:
        group = str(group).strip()
        if not group:
            continue
        results[group] = run_group(
            group,
            run_market=run_market,
            run_market_robust=run_market_robust,
            run_rational=run_rational,
            run_rational_robust=run_rational_robust,
            run_plots=run_plots,
            plots_folder=plots_folder,
            exp_root=exp_root,
        )
    return results
