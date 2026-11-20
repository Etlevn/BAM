"""Scan selected exp groups and write analysis CSVs under _<GROUP>/."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

import config
from src.analysis.behavior import build_behavior_panel, load_behavior_inputs
from src.analysis.br_agg import expand_market_by_model, is_br_group
from src.analysis.cognition import build_cognition_panel, load_cognition_inputs
from src.analysis.equilibrium import build_equilibrium_panel, load_equilibrium_inputs
from src.analysis.intervention import (
    build_intervention_panel,
    load_intervention_inputs,
    summarize_intervention_by_mechanism,
)
from src.analysis.market import build_market_row
from src.analysis.mechanism import build_mechanism_panel, load_mechanism_inputs
from src.analysis.mkt_agg import build_mkt_agg_table, load_group_mkt_csv
from src.analysis.plots import plot_group, plot_mkt_agg
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


def _initial_stocks() -> float:
    return float(config.EXPERIMENT_CONFIG.get("initial_stocks", 4))


def run_group(
    group: str,
    *,
    run_market: bool = True,
    run_market_robust: bool = True,
    run_market_agg_robust: bool = False,
    run_mkt_agg: bool = False,
    run_mkt_agg_plot: bool = False,
    run_behavior: bool = False,
    run_equilibrium: bool = False,
    run_cognition: bool = False,
    run_mechanism: bool = False,
    run_intervention: bool = False,
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
    initial_stocks = _initial_stocks()

    classified = classify_group_sessions(group_dir)
    sessions = classified.complete
    # integ-only tasks need no complete sessions list.
    integ_only = (
        run_mkt_agg
        or run_mkt_agg_plot
        or run_behavior
        or run_equilibrium
        or run_cognition
        or run_mechanism
        or run_intervention
    )
    if not sessions and not integ_only:
        return {}

    # Plots need the same session metrics as market (title line).
    need_market = (run_market or run_plots) and bool(sessions)

    # One bar for all session-level work units in this group.
    work: list[tuple[str, SessionMeta]] = []
    if need_market:
        work.extend(("market", meta) for meta in sessions)
    if run_rational and sessions:
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

        # BR only: explode pair→model in memory, write robust only (SGL-style means).
        if is_br_group(group_name) and run_market_agg_robust:
            market_agg = expand_market_by_model(market_df)
            agg_rob = summarize_by_series(market_agg, MARKET_METRICS)
            agg_rob_path = out_dir / f"{group_name}_market_agg_robust.csv"
            _write_csv(agg_rob, agg_rob_path)
            written["market_agg_robust"] = agg_rob_path

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

    if run_plots and sessions:
        folder = str(plots_folder or "plots").strip() or "plots"
        plots_root = out_dir / folder
        written["plots"] = plot_group(
            sessions,
            market_rows,
            plots_root=plots_root,
            fundamental_value=fv,
            min_rounds=total_rounds,
        )

    mkt_agg_df: pd.DataFrame | None = None
    mkt_agg_path = out_dir / f"{group_name}_mkt_agg.csv"

    if run_mkt_agg:
        integ_mkt = out_dir / f"{group_name}_mkt.csv"
        if not integ_mkt.is_file():
            raise FileNotFoundError(
                f"RUN_MKT_AGG requires integ output {integ_mkt}; "
                f"run integ for group {group_name!r} first (no fallback)."
            )
        mkt_df = load_group_mkt_csv(integ_mkt)
        mkt_agg_df = build_mkt_agg_table(
            mkt_df,
            group=group_name,
            fundamental_value=fv,
            total_rounds=total_rounds,
        )
        _write_csv(mkt_agg_df, mkt_agg_path)
        written["mkt_agg"] = mkt_agg_path

    if run_mkt_agg_plot:
        if mkt_agg_df is None:
            if not mkt_agg_path.is_file():
                raise FileNotFoundError(
                    f"RUN_MKT_AGG_PLOT requires {mkt_agg_path}; "
                    f"enable RUN_MKT_AGG first (no fallback)."
                )
            mkt_agg_df = pd.read_csv(mkt_agg_path)
        folder = str(plots_folder or "plots").strip() or "plots"
        plot_path = out_dir / folder / "_mkt_agg.png"
        written["mkt_agg_plot"] = plot_mkt_agg(
            mkt_agg_df, save_path=plot_path, group=group_name
        )

    if run_behavior:
        mkt_df, rx_df = load_behavior_inputs(out_dir, group_name)
        behavior_df = build_behavior_panel(
            mkt_df,
            rx_df,
            fundamental_value=fv,
            initial_stocks=initial_stocks,
            total_rounds=total_rounds,
        )
        behavior_path = out_dir / f"{group_name}_behavior.csv"
        _write_csv(behavior_df, behavior_path)
        written["behavior"] = behavior_path

    if run_equilibrium:
        mkt_df, rx_df = load_equilibrium_inputs(out_dir, group_name)
        eq_df = build_equilibrium_panel(
            mkt_df, rx_df, total_rounds=total_rounds
        )
        eq_path = out_dir / f"{group_name}_equilibrium.csv"
        _write_csv(eq_df, eq_path)
        written["equilibrium"] = eq_path

    if run_cognition:
        mkt_df, rx_df, output_df = load_cognition_inputs(out_dir, group_name)
        cog_df = build_cognition_panel(
            mkt_df, rx_df, output_df, total_rounds=total_rounds
        )
        cog_path = out_dir / f"{group_name}_cognition.csv"
        _write_csv(cog_df, cog_path)
        written["cognition"] = cog_path

    if run_mechanism:
        mkt_df, nlp_df = load_mechanism_inputs(out_dir, group_name)
        mech_df = build_mechanism_panel(
            mkt_df,
            nlp_df,
            fundamental_value=fv,
            total_rounds=total_rounds,
        )
        mech_path = out_dir / f"{group_name}_mechanism.csv"
        _write_csv(mech_df, mech_path)
        written["mechanism"] = mech_path

    if run_intervention:
        mkt_df, market_df = load_intervention_inputs(out_dir, group_name)
        iv_df = build_intervention_panel(
            mkt_df,
            bas_market=market_df,
            total_rounds=total_rounds,
        )
        iv_path = out_dir / f"{group_name}_intervention.csv"
        _write_csv(iv_df, iv_path)
        written["intervention"] = iv_path

        iv_mech = summarize_intervention_by_mechanism(iv_df)
        iv_mech_path = out_dir / f"{group_name}_intervention_mech.csv"
        _write_csv(iv_mech, iv_mech_path)
        written["intervention_mech"] = iv_mech_path

    return written


def run_groups(
    groups: Sequence[str] | Iterable[str],
    *,
    run_market: bool = True,
    run_market_robust: bool = True,
    run_market_agg_robust: bool = False,
    run_mkt_agg: bool = False,
    run_mkt_agg_plot: bool = False,
    run_behavior: bool = False,
    run_equilibrium: bool = False,
    run_cognition: bool = False,
    run_mechanism: bool = False,
    run_intervention: bool = False,
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
            run_market_agg_robust=run_market_agg_robust,
            run_mkt_agg=run_mkt_agg,
            run_mkt_agg_plot=run_mkt_agg_plot,
            run_behavior=run_behavior,
            run_equilibrium=run_equilibrium,
            run_cognition=run_cognition,
            run_mechanism=run_mechanism,
            run_intervention=run_intervention,
            run_rational=run_rational,
            run_rational_robust=run_rational_robust,
            run_plots=run_plots,
            plots_folder=plots_folder,
            exp_root=exp_root,
        )
    return results
