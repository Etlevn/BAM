"""Parallel plan/insight mechanism coding for one group's _output.csv."""

from __future__ import annotations

import concurrent.futures
import time
from pathlib import Path
from typing import Any

import pandas as pd

from src.nlp import utils as nlp_utils
from src.support.progress import ProgressBar, track, write_line


def _thread_print(
    thread_id: int,
    index: int,
    message: str,
    total_samples: int | None = None,
    max_threads: int | None = None,
) -> None:
    padded_index = (
        str(index).rjust(len(str(total_samples))) if total_samples else str(index)
    )
    padded_thread = (
        str(thread_id).rjust(len(str(max_threads))) if max_threads else str(thread_id)
    )
    write_line(f"[THD {padded_thread}] Idx {padded_index} | {message}")


def process_single_row(
    index: int,
    row_data: dict[str, Any],
    cfg: dict[str, Any],
    system_prompt: str,
    output_dir: Path,
    thread_id: int = 1,
    total_samples: int | None = None,
    max_threads: int | None = None,
    *,
    skip_existing: bool = False,
) -> dict[str, Any]:
    start_time = time.time()
    sess = nlp_utils.session_id(row_data)
    round_num = str(row_data.get("round", "Unknown"))
    agent_id = str(row_data.get("llm", "Unknown"))

    _thread_print(
        thread_id,
        index + 1,
        f"[INFO] Sess:{sess},Round:{round_num},Agent:{agent_id}",
        total_samples,
        max_threads,
    )

    results: dict[str, Any] = {
        "index": index,
        "session": sess,
        "agent_id": agent_id,
        "round": round_num,
        "plan_success": False,
        "insight_success": False,
        "plan_file": None,
        "insight_file": None,
        "plan_skipped": False,
        "insight_skipped": False,
    }

    api_mode = cfg["api_mode"]
    model_name = cfg["model_name"]
    mechanisms = cfg["mechanism_order"]
    save_json = cfg.get("save_individual_json", True)

    plan_name = nlp_utils.generate_output_filename(sess, round_num, agent_id, "plan")
    insight_name = nlp_utils.generate_output_filename(
        sess, round_num, agent_id, "insight"
    )
    plan_path = output_dir / plan_name
    insight_path = output_dir / insight_name

    do_plan = bool(cfg.get("evaluate_plan", True))
    if do_plan and skip_existing and plan_path.is_file():
        results["plan_success"] = True
        results["plan_skipped"] = True
        results["plan_file"] = plan_name
        _thread_print(
            thread_id,
            index + 1,
            f"[SKIP] Plan exists: {plan_name}",
            total_samples,
            max_threads,
        )
        do_plan = False

    if do_plan:
        _thread_print(
            thread_id, index + 1, "[PROC] Evaluating PLAN...", total_samples, max_threads
        )
        plan_text = str(row_data.get("plan", "No plan provided"))
        plan_prompt = nlp_utils.build_evaluation_prompt(
            system_prompt, "plan", plan_text, row_data
        )
        plan_result = nlp_utils.call_llm_for_evaluation(
            plan_prompt, model_name=model_name, api_mode=api_mode
        )
        is_valid, errors = nlp_utils.validate_evaluation_result(plan_result, mechanisms)
        if is_valid:
            _thread_print(
                thread_id,
                index + 1,
                "[DONE] Plan evaluation successful",
                total_samples,
                max_threads,
            )
            results["plan_success"] = True
            plan_result["evaluation_target"] = "PLAN"
            plan_result["agent_info"] = {
                "llm_id": agent_id,
                "round": round_num,
                "mode": row_data.get("mode", "N/A"),
            }
            if save_json:
                if nlp_utils.save_json_result(plan_result, plan_path):
                    _thread_print(
                        thread_id, index + 1, f"[SAVE] {plan_name}", total_samples, max_threads
                    )
                    results["plan_file"] = plan_name
        else:
            _thread_print(
                thread_id,
                index + 1,
                "[ERROR] Plan evaluation failed:",
                total_samples,
                max_threads,
            )
            for error in errors:
                _thread_print(
                    thread_id, index + 1, f"  - {error}", total_samples, max_threads
                )

    do_insight = bool(cfg.get("evaluate_insight", True))
    if do_insight and skip_existing and insight_path.is_file():
        results["insight_success"] = True
        results["insight_skipped"] = True
        results["insight_file"] = insight_name
        _thread_print(
            thread_id,
            index + 1,
            f"[SKIP] Insight exists: {insight_name}",
            total_samples,
            max_threads,
        )
        do_insight = False

    if do_insight:
        _thread_print(
            thread_id,
            index + 1,
            "[PROC] Evaluating INSIGHT...",
            total_samples,
            max_threads,
        )
        insight_text = str(row_data.get("insight", "No insight provided"))
        insight_prompt = nlp_utils.build_evaluation_prompt(
            system_prompt, "insight", insight_text, row_data
        )
        insight_result = nlp_utils.call_llm_for_evaluation(
            insight_prompt, model_name=model_name, api_mode=api_mode
        )
        is_valid, errors = nlp_utils.validate_evaluation_result(
            insight_result, mechanisms
        )
        if is_valid:
            _thread_print(
                thread_id,
                index + 1,
                "[DONE] Insight evaluation successful",
                total_samples,
                max_threads,
            )
            results["insight_success"] = True
            insight_result["evaluation_target"] = "INSIGHT"
            insight_result["agent_info"] = {
                "llm_id": agent_id,
                "round": round_num,
                "mode": row_data.get("mode", "N/A"),
            }
            if save_json:
                if nlp_utils.save_json_result(insight_result, insight_path):
                    _thread_print(
                        thread_id,
                        index + 1,
                        f"[SAVE] {insight_name}",
                        total_samples,
                        max_threads,
                    )
                    results["insight_file"] = insight_name
        else:
            _thread_print(
                thread_id,
                index + 1,
                "[ERROR] Insight evaluation failed:",
                total_samples,
                max_threads,
            )
            for error in errors:
                _thread_print(
                    thread_id, index + 1, f"  - {error}", total_samples, max_threads
                )

    elapsed = time.time() - start_time
    _thread_print(
        thread_id,
        index + 1,
        f"[DONE] Completed in {elapsed:.2f} seconds",
        total_samples,
        max_threads,
    )
    return results


def run_code(
    input_csv: Path,
    output_dir: Path,
    *,
    cfg: dict[str, Any],
    prompt_path: Path,
    skip_existing: bool = False,
) -> list[dict[str, Any]]:
    start_time = time.time()
    system_prompt = nlp_utils.load_prompt_template(prompt_path)

    if input_csv.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(input_csv, engine="openpyxl")
    else:
        df = pd.read_csv(input_csv, keep_default_na=False)

    missing = nlp_utils.required_columns(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    df = nlp_utils.filter_sgl_rows(df, label="nlp code")

    max_rows = cfg.get("max_processing_rows")
    if max_rows is not None and len(df) > int(max_rows):
        print(f"[INFO] Limiting processing to {max_rows} rows")
        df = df.head(int(max_rows))

    sort_cols = [
        c for c in ("session", "simulation_index", "round", "llm") if c in df.columns
    ]
    if sort_cols:
        df = df.sort_values(by=sort_cols, ascending=True).reset_index(drop=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    max_workers = int(cfg.get("max_workers") or 1)
    total_samples = len(df)
    mode = "refill-skip-existing" if skip_existing else "full"
    print(
        f"[INFO] Coding {total_samples} rows ({mode}) "
        f"with {max_workers} workers → {output_dir}"
    )

    all_results: list[dict[str, Any]] = []

    if max_workers > 1:
        with ProgressBar(total_samples, label="nlp code") as bar:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
                futures = []
                thread_counter = 1
                for idx, row in df.iterrows():
                    futures.append(
                        ex.submit(
                            process_single_row,
                            idx,
                            row.to_dict(),
                            cfg,
                            system_prompt,
                            output_dir,
                            thread_counter,
                            total_samples,
                            max_workers,
                            skip_existing=skip_existing,
                        )
                    )
                    thread_counter = (thread_counter % max_workers) + 1
                for fut in concurrent.futures.as_completed(futures):
                    try:
                        all_results.append(fut.result())
                    except Exception as exc:
                        write_line(f"[ERROR] Task failed: {exc}")
                    bar.update(1)
    else:
        for idx, row in track(list(df.iterrows()), label="nlp code"):
            try:
                all_results.append(
                    process_single_row(
                        idx,
                        row.to_dict(),
                        cfg,
                        system_prompt,
                        output_dir,
                        1,
                        total_samples,
                        max_workers,
                        skip_existing=skip_existing,
                    )
                )
            except Exception as exc:
                write_line(f"[ERROR] Row {idx} failed: {exc}")

    plan_ok = sum(1 for r in all_results if r["plan_success"])
    insight_ok = sum(1 for r in all_results if r["insight_success"])
    print(
        f"[INFO] Plan {plan_ok}/{len(all_results)} | "
        f"Insight {insight_ok}/{len(all_results)} | "
        f"{time.time() - start_time:.1f}s"
    )
    return all_results
