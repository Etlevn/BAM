"""Scan selected exp groups and write aggregated CSVs under _<GROUP>/."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

import config
from src.integ.columns import order_leading_columns
from src.integ.orders import build_orders
from src.integ.outputs import build_outputs
from src.integ.session import classify_group_sessions
from src.integ.snapshots import build_snapshots


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


def ensure_cased_path(path: Path) -> Path:
    """
    Ensure path's final component uses exactly path.name casing.
    On case-insensitive volumes, an existing `_sgl` must be two-step-renamed
    to `_SGL` (and likewise for CSV filenames).
    """
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    target_name = path.name

    existing: Path | None = None
    for child in parent.iterdir():
        if child.name.casefold() == target_name.casefold():
            existing = child
            break

    if existing is None:
        return parent / target_name

    if existing.name == target_name:
        return existing

    # Case-only rename via a unique temporary name.
    tmp = parent / f".{target_name}.{uuid.uuid4().hex}.tmp"
    existing.rename(tmp)
    tmp.rename(parent / target_name)
    return parent / target_name


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path = ensure_cased_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"Saved {len(df)} rows → {path}")


def run_group(
    group: str,
    *,
    run_orders: bool = True,
    run_snapshots: bool = True,
    run_outputs: bool = True,
    noncomplete_folder: str = "_incomplete",
    exp_root: Path | None = None,
) -> dict[str, Path]:
    root = Path(exp_root) if exp_root is not None else Path(config.EXP_DIR)
    group_dir = resolve_group_dir(root, group)
    if group_dir is None:
        print(f"Skip missing group: {root / group}")
        return {}

    # Output dir/file prefixes always mirror the on-disk first-level name.
    group_name = group_dir.name
    out_dir = ensure_cased_path(group_dir / f"_{group_name}")
    print("=" * 60)
    print(f"Group: {group_name}")
    print(f"Scan:  {group_dir}")
    print(f"Out:   {out_dir}")
    print(f"Non-complete bin: <series>/{noncomplete_folder}/")
    print("-" * 60)

    classified = classify_group_sessions(
        group_dir, noncomplete_folder=noncomplete_folder
    )
    sessions = classified.complete
    print(
        f"Complete formal sessions: {len(sessions)}; "
        f"moved non-complete: {len(classified.moved)}"
    )
    if not sessions:
        return {}

    order_frames: list[pd.DataFrame] = []
    snap_frames: list[pd.DataFrame] = []
    out_frames: list[pd.DataFrame] = []

    for i, meta in enumerate(sessions, 1):
        label = f"{meta.series}/{meta.simulation_index}"
        print(f"[{i}/{len(sessions)}] {label} ({meta.market_type})")
        if run_orders:
            order_frames.append(build_orders(meta))
        if run_snapshots:
            snap_frames.append(build_snapshots(meta))
        if run_outputs:
            out_frames.append(build_outputs(meta))

    written: dict[str, Path] = {}
    if run_orders:
        path = out_dir / f"{group_name}_rx.csv"
        _write_csv(_concat(order_frames), path)
        written["rx"] = path
    if run_snapshots:
        path = out_dir / f"{group_name}_mkt.csv"
        _write_csv(_concat(snap_frames), path)
        written["mkt"] = path
    if run_outputs:
        path = out_dir / f"{group_name}_output.csv"
        _write_csv(_concat(out_frames), path)
        written["output"] = path
    return written


def run_groups(
    groups: Sequence[str] | Iterable[str],
    *,
    run_orders: bool = True,
    run_snapshots: bool = True,
    run_outputs: bool = True,
    noncomplete_folder: str = "_incomplete",
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
            noncomplete_folder=noncomplete_folder,
            exp_root=exp_root,
        )
    print("=" * 60)
    print("Integration done.")
    return results
