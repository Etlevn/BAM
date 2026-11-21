"""Orchestrate NLP code / merge / miss for selected exp groups."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Sequence

import config
from src.integ.paths import ensure_cased_path, integ_csv, nlp_csv, nlp_dir
from src.integ.runner import resolve_group_dir
from src.nlp.code import run_code
from src.nlp.merge import merge_nlp_results
from src.nlp.miss import check_missing


def _group_out_dir(group_dir: Path) -> Path:
    return ensure_cased_path(group_dir / f"_{group_dir.name}")


def _output_csv(out_dir: Path, group_name: str) -> Path:
    """Integ ``_output.csv`` under ``_<GROUP>/integrate/``."""
    return integ_csv(out_dir, group_name, "output")


def _run_post(
    *,
    input_csv: Path,
    json_dir: Path,
    out_dir: Path,
    group_name: str,
    written: dict[str, Path],
) -> None:
    merge_path = nlp_csv(out_dir, group_name, "output_nlp")
    written["merge"] = merge_nlp_results(input_csv, json_dir, merge_path)
    miss_path = nlp_csv(out_dir, group_name, "output_miss")
    result = check_missing(input_csv, json_dir, miss_path)
    if result is not None:
        written["miss"] = result


def run_group(
    group: str,
    *,
    run_code_flag: bool = True,
    run_post: bool = True,
    run_refill_miss: bool = False,
    nlp_cfg: dict[str, Any] | None = None,
    prompt_path: Path | None = None,
    exp_root: Path | None = None,
) -> dict[str, Path]:
    if run_refill_miss and run_code_flag:
        raise ValueError(
            "RUN_REFILL_MISS and RUN_CODE are mutually exclusive; "
            "enable only one."
        )

    root = Path(exp_root) if exp_root is not None else Path(config.EXP_DIR)
    group_dir = resolve_group_dir(root, group)
    if group_dir is None:
        print(f"Skip missing group: {root / group}")
        return {}

    group_name = group_dir.name
    out_dir = _group_out_dir(group_dir)
    input_csv = _output_csv(out_dir, group_name)
    json_dir = nlp_dir(out_dir)
    written: dict[str, Path] = {}

    print("=" * 60)
    print(f"NLP group: {group_name}")
    print(f"Input: {input_csv}")
    print(f"JSON:  {json_dir}")

    if not input_csv.is_file():
        print(f"[ERROR] Missing integ output CSV: {input_csv}")
        return written

    cfg = dict(nlp_cfg or {})
    prompt = prompt_path or (Path(config.PROMPT_DIR) / "nlp_prmt.txt")

    if run_refill_miss:
        if run_post:
            print("[nlp] RUN_POST ignored while RUN_REFILL_MISS (refill already posts)")
        miss_path = nlp_csv(out_dir, group_name, "output_miss")
        if not miss_path.is_file():
            raise FileNotFoundError(
                f"RUN_REFILL_MISS requires {miss_path}; run RUN_POST first."
            )
        print(f"[nlp] Refill from miss: {miss_path}")
        run_code(
            miss_path,
            json_dir,
            cfg=cfg,
            prompt_path=prompt,
            skip_existing=True,
        )
        written["nlp_dir"] = json_dir
        _run_post(
            input_csv=input_csv,
            json_dir=json_dir,
            out_dir=out_dir,
            group_name=group_name,
            written=written,
        )
        return written

    if run_code_flag:
        run_code(input_csv, json_dir, cfg=cfg, prompt_path=prompt)
        written["nlp_dir"] = json_dir

    if run_post:
        _run_post(
            input_csv=input_csv,
            json_dir=json_dir,
            out_dir=out_dir,
            group_name=group_name,
            written=written,
        )

    return written


def run_groups(
    groups: Sequence[str] | Iterable[str],
    *,
    run_code_flag: bool = True,
    run_post: bool = True,
    run_refill_miss: bool = False,
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
            run_refill_miss=run_refill_miss,
            nlp_cfg=nlp_cfg,
            prompt_path=prompt_path,
            exp_root=exp_root,
        )
    print("=" * 60)
    print("NLP done.")
    return results
