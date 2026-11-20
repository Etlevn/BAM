"""Orchestrate NLP code / merge / miss for selected exp groups."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Sequence

import config
from src.integ.runner import ensure_cased_path, resolve_group_dir
from src.nlp.code import run_code
from src.nlp.merge import merge_nlp_results
from src.nlp.miss import check_missing


def _group_out_dir(group_dir: Path) -> Path:
    return ensure_cased_path(group_dir / f"_{group_dir.name}")


def _output_csv(out_dir: Path, group_name: str) -> Path:
    # Prefer cased match for <GROUP>_output.csv
    exact = out_dir / f"{group_name}_output.csv"
    if exact.is_file():
        return exact
    lower = out_dir / f"{group_name.lower()}_output.csv"
    if lower.is_file():
        return lower
    # Case-insensitive scan
    for p in out_dir.glob("*_output.csv"):
        if p.name.lower() == f"{group_name.lower()}_output.csv":
            return p
    return exact


def run_group(
    group: str,
    *,
    run_code_flag: bool = True,
    run_post: bool = True,
    nlp_cfg: dict[str, Any] | None = None,
    prompt_path: Path | None = None,
    exp_root: Path | None = None,
) -> dict[str, Path]:
    root = Path(exp_root) if exp_root is not None else Path(config.EXP_DIR)
    group_dir = resolve_group_dir(root, group)
    if group_dir is None:
        print(f"Skip missing group: {root / group}")
        return {}

    group_name = group_dir.name
    out_dir = _group_out_dir(group_dir)
    input_csv = _output_csv(out_dir, group_name)
    nlp_dir = ensure_cased_path(out_dir / "nlp")
    written: dict[str, Path] = {}

    print("=" * 60)
    print(f"NLP group: {group_name}")
    print(f"Input: {input_csv}")
    print(f"JSON:  {nlp_dir}")

    if not input_csv.is_file():
        print(f"[ERROR] Missing integ output CSV: {input_csv}")
        return written

    cfg = dict(nlp_cfg or {})
    prompt = prompt_path or (Path(config.PROMPT_DIR) / "nlp_prmt.txt")

    if run_code_flag:
        run_code(input_csv, nlp_dir, cfg=cfg, prompt_path=prompt)
        written["nlp_dir"] = nlp_dir

    if run_post:
        merge_path = out_dir / f"{group_name}_output_nlp.csv"
        written["merge"] = merge_nlp_results(input_csv, nlp_dir, merge_path)
        miss_path = out_dir / f"{group_name}_output_miss.csv"
        result = check_missing(input_csv, nlp_dir, miss_path)
        if result is not None:
            written["miss"] = result

    return written


def run_groups(
    groups: Sequence[str] | Iterable[str],
    *,
    run_code_flag: bool = True,
    run_post: bool = True,
    nlp_cfg: dict[str, Any] | None = None,
    prompt_path: Path | None = None,
    exp_root: Path | None = None,
) -> dict[str, dict[str, Path]]:
    results: dict[str, dict[str, Path]] = {}
    for group in groups:
        group = str(group).strip()
        if not group:
            continue
        results[group] = run_group(
            group,
            run_code_flag=run_code_flag,
            run_post=run_post,
            nlp_cfg=nlp_cfg,
            prompt_path=prompt_path,
            exp_root=exp_root,
        )
    print("=" * 60)
    print("NLP done.")
    return results
