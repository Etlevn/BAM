"""Scan selected exp groups and write aggregated CSVs under _<GROUP>/integrate/."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

import config
from src.integ.columns import order_leading_columns
from src.integ.orders import build_orders
from src.integ.outputs import build_outputs
from src.integ.paths import ensure_cased_path, integ_csv, write_table_csv
from src.integ.session import classify_group_sessions
from src.integ.snapshots import build_snapshots
from src.support.progress import track

# Re-export for callers that historically imported from runner.
__all__ = ["ensure_cased_path", "resolve_group_dir", "run_group", "run_groups"]


def _concat(frames: list[pd.DataFrame]) -> pd.DataFrame:
    nonempty = [f for f in frames if f is not None and not f.empty]
    if not nonempty:
        return pd.DataFrame()
    return order_leading_columns(pd.concat(nonempty, ignore_index=True))


def resolve_group_dir(exp_root: Path, group: str) -> Path | None:
    """
    Locate exp/<group> using case-insensitive match, but return the path with
    the on-disk first-level directory spelling (case preserved).
    """
    wanted = str(group).strip()
    if not wanted or not exp_root.is_dir():
        return None
    for child in exp_root.iterdir():
        if child.is_dir() and child.name.casefold() == wanted.casefold():
            return child
    return None


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path = write_table_csv(df, path)
    print(f"Saved {len(df)} rows → {path}")


def run_group(
    group: str,
    *,
    run_orders: bool = True,
    run_snapshots: bool = True,
    run_outputs: bool = True,
    exp_root: Path | None = None,
) -> dict[str, Path]:
    root = Path(exp_root) if exp_root is not None else Path(config.EXP_DIR)
    group_dir = resolve_group_dir(root, group)
    if group_dir is None:
        return {}

    group_name = group_dir.name
    out_dir = ensure_cased_path(group_dir / f"_{group_name}")

    classified = classify_group_sessions(group_dir)
    sessions = classified.complete
    if not sessions:
        return {}

    order_frames: list[pd.DataFrame] = []
    snap_frames: list[pd.DataFrame] = []
    out_frames: list[pd.DataFrame] = []

    for meta in track(sessions, label=f"integ {group_name}"):
        if run_orders:
            order_frames.append(build_orders(meta))
        if run_snapshots:
            snap_frames.append(build_snapshots(meta))
        if run_outputs:
            out_frames.append(build_outputs(meta))

    written: dict[str, Path] = {}
    if run_orders:
        path = integ_csv(out_dir, group_name, "rx")
        _write_csv(_concat(order_frames), path)
        written["rx"] = path
    if run_snapshots:
        path = integ_csv(out_dir, group_name, "mkt")
        _write_csv(_concat(snap_frames), path)
        written["mkt"] = path
    if run_outputs:
        path = integ_csv(out_dir, group_name, "output")
        _write_csv(_concat(out_frames), path)
        written["output"] = path
    return written


def run_groups(
    groups: Sequence[str] | Iterable[str],
    *,
    run_orders: bool = True,
    run_snapshots: bool = True,
    run_outputs: bool = True,
    exp_root: Path | None = None,
) -> dict[str, dict[str, Path]]:
    results: dict[str, dict[str, Path]] = {}
    for group in groups:
        group = str(group).strip()
        if not group:
            continue
        results[group] = run_group(
            group,
            run_orders=run_orders,
            run_snapshots=run_snapshots,
            run_outputs=run_outputs,
            exp_root=exp_root,
        )
    return results
