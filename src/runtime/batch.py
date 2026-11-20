"""Parallel batch launcher: concurrent main.py subprocesses with start stagger."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import config
from src.support.progress import ProgressBar, write_line

Runner = Callable[[int, str], int]

_ROUND_RE = re.compile(r"^===\s+(PRAC|MAIN)\s+ROUND\s+(\d+)\s+===", re.IGNORECASE)
_PROC_RE = re.compile(
    r"^\[(prac|main|refl)\]\s+Processing\s+(llm_\d+)\b", re.IGNORECASE
)
_SESSION_RE = re.compile(
    r"^\[(?:init\.py|runner)\]\s+"
    r"(?:Experiment run directory|Session directory):\s*(.+?)\s*$",
    re.IGNORECASE,
)

_MODE_LABEL = {"prac": "prac", "main": "formal", "refl": "refl"}

ENV_USE_BAS = "BAM_USE_BAS_MODE"
ENV_BIAS_ID = "BAM_BAS_BIAS_ID"


def _silent_llm_count() -> int:
    """Agent count from config without printing (unlike paths.get_llm_count)."""
    if config.EXPERIMENT_MODE == "br" and "custom_models" in config.BATTLE_ROYALE_CONFIG:
        return sum(int(m["count"]) for m in config.BATTLE_ROYALE_CONFIG["custom_models"])
    if config.EXPERIMENT_MODE == "sgl":
        return int(config.SINGLE_MODEL_CONFIG["num_llms"])
    raise ValueError(
        f"Invalid EXPERIMENT_MODE: {config.EXPERIMENT_MODE}. Must be 'br' or 'sgl'"
    )


def expected_progress_total(num_experiments: int) -> int:
    """experiments × (practice + formal + reflection?) × llm_count."""
    cfg = config.EXPERIMENT_CONFIG
    practice = int(cfg.get("practice_rounds", 0) or 0)
    formal = int(cfg.get("total_rounds", 0) or 0)
    reflection = 1 if practice > 0 else 0
    phases = practice + formal + reflection
    return max(0, int(num_experiments) * phases * _silent_llm_count())


def list_bas_as_bias_ids(
    catalog_path: str | os.PathLike[str] | None = None,
) -> list[str]:
    """Return amp_* then sup_* ids from bas_biases.json (40 entries when complete)."""
    path = (
        os.fspath(catalog_path)
        if catalog_path is not None
        else os.path.join(config.PROMPT_DIR, "bas_biases.json")
    )
    with open(path, encoding="utf-8") as f:
        catalog = json.load(f)
    amps = sorted(k for k in catalog if str(k).startswith("amp_"))
    sups = sorted(k for k in catalog if str(k).startswith("sup_"))
    return amps + sups


def build_job_plan(
    *,
    num_runs: int,
    run_all_bas: bool,
    bias_ids: list[str] | None = None,
) -> list[dict]:
    """Expand batch jobs. Each item: job_index, replicate, bias_id (or None)."""
    if num_runs < 1:
        return []
    if not run_all_bas:
        return [
            {"job_index": i, "replicate": i, "bias_id": None, "num_runs": num_runs}
            for i in range(1, num_runs + 1)
        ]
    ids = list(bias_ids) if bias_ids is not None else list_bas_as_bias_ids()
    jobs: list[dict] = []
    n = 0
    for bias_id in ids:
        for rep in range(1, num_runs + 1):
            n += 1
            jobs.append(
                {
                    "job_index": n,
                    "replicate": rep,
                    "bias_id": bias_id,
                    "num_runs": num_runs,
                }
            )
    return jobs


def _display_tag(state: dict) -> str:
    session = state.get("session")
    return f"[{session}]" if session else "[pending]"


def _handle_child_line(line: str, state: dict, bar: ProgressBar | None) -> None:
    """Parse one child stdout line; update status + progress on Processing events."""
    text = line.rstrip("\n").strip()

    m_sess = _SESSION_RE.match(text)
    if m_sess:
        session = os.path.basename(os.path.normpath(m_sess.group(1)))
        if session and state.get("session") != session:
            state["session"] = session
            write_line(f"[{session}] session ready")
        return

    m_round = _ROUND_RE.match(text)
    if m_round:
        state["mode"] = m_round.group(1).lower()
        state["round"] = int(m_round.group(2))
        return

    m_proc = _PROC_RE.match(text)
    if not m_proc:
        return

    mode = m_proc.group(1).lower()
    llm_id = m_proc.group(2)
    label = _MODE_LABEL.get(mode, mode)
    tag = _display_tag(state)
    if mode == "refl":
        status = f"{tag} refl · {llm_id}"
    else:
        rnd = state.get("round")
        rnd_s = f"r{rnd}" if rnd is not None else "r?"
        status = f"{tag} {label} {rnd_s} · {llm_id}"
    write_line(status)
    if bar is not None:
        bar.update(1)


def _default_runner(
    index: int,
    log_path: str,
    bar: ProgressBar | None = None,
    *,
    child_env: dict[str, str] | None = None,
) -> tuple[int, str | None]:
    """Run one full experiment; tee stdout to log and surface round/llm progress."""
    del index
    main_script = os.path.join(config.BASE_DIR, "main.py")
    state: dict = {"mode": None, "round": None, "session": None}
    env = os.environ.copy()
    if child_env:
        env.update(child_env)

    with open(log_path, "w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            [sys.executable, "-u", main_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=config.BASE_DIR,
            bufsize=1,
            env=env,
        )
        assert process.stdout is not None
        for line in process.stdout:
            log_file.write(line)
            log_file.flush()
            _handle_child_line(line, state, bar)
        process.wait()
        return process.returncode or 0, state.get("session")


def run_batch_main(
    *,
    num_runs: int = 10,
    max_workers: int = 4,
    runner: Runner | None = None,
    start_gap_s: float = 1.0,
    run_all_bas: bool = False,
) -> int:
    """Run experiments with up to ``max_workers`` concurrent children.

    When ``run_all_bas`` is True, expands to all amp/sup biases × ``num_runs``
    and forces BAS via child env overrides.
    Always waits for every run (no fail-fast). Returns 0 if all succeeded, else 1.
    """
    if num_runs < 1:
        print("NUM_RUNS must be >= 1")
        return 1

    jobs = build_job_plan(num_runs=num_runs, run_all_bas=run_all_bas)
    if run_all_bas and not jobs:
        print("RUN_ALL_BAS set but no amp_/sup_ ids found in bas_biases.json")
        return 1

    total_jobs = len(jobs)
    workers = max(1, min(max_workers, total_jobs))
    log_dir = config.LOG_DIR
    os.makedirs(log_dir, exist_ok=True)

    total_steps = expected_progress_total(total_jobs)
    write_line(
        f"Starting batch of {total_jobs} experiments "
        f"(num_runs={num_runs}, run_all_bas={run_all_bas}, "
        f"max_workers={workers}, start_gap={start_gap_s}s, "
        f"progress_total={total_steps}) via `main.py` ..."
    )
    t0 = time.time()

    launch_lock = threading.Lock()
    last_launch = 0.0

    with ProgressBar(total_steps, label="batch") as bar:

        def job(spec: dict) -> tuple[int, int, str | None, str | None]:
            nonlocal last_launch
            job_index = int(spec["job_index"])
            replicate = int(spec["replicate"])
            bias_id = spec.get("bias_id")
            log_path = os.path.join(log_dir, f"slot_{job_index:04d}.log")
            with launch_lock:
                now = time.monotonic()
                if last_launch > 0:
                    wait = start_gap_s - (now - last_launch)
                    if wait > 0:
                        time.sleep(wait)
                last_launch = time.monotonic()
                if bias_id:
                    write_line(
                        f"launching {bias_id} replicate {replicate}/{num_runs} "
                        f"(job {job_index}/{total_jobs}) ..."
                    )
                else:
                    write_line(f"launching run {job_index}/{total_jobs} ...")

            session: str | None = None
            if runner is not None:
                code = runner(job_index, log_path)
            else:
                child_env = None
                if bias_id is not None:
                    child_env = {
                        ENV_USE_BAS: "1",
                        ENV_BIAS_ID: str(bias_id),
                    }
                code, session = _default_runner(
                    job_index, log_path, bar=bar, child_env=child_env
                )
                if session:
                    dest = os.path.join(log_dir, f"{session}.log")
                    try:
                        os.replace(log_path, dest)
                    except OSError:
                        pass

            if session:
                tag = f"[{session}]"
            elif bias_id:
                tag = f"[{bias_id}#{replicate}]"
            else:
                tag = f"[run {job_index}/{total_jobs}]"
            status = "ok" if code == 0 else f"fail({code})"
            write_line(f"{tag} finished {status}")
            return job_index, code, session, bias_id

        results: dict[int, tuple[int, str | None, str | None]] = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(job, spec) for spec in jobs]
            for fut in as_completed(futures):
                job_index, code, session, bias_id = fut.result()
                results[job_index] = (code, session, bias_id)

    failed_labels = sorted(
        (sess or (f"{bias}-{i}" if bias else f"run-{i}"))
        for i, (c, sess, bias) in results.items()
        if c != 0
    )
    ok = total_jobs - len(failed_labels)
    elapsed = time.time() - t0
    print(
        f"\nBatch done in {elapsed:.2f}s: {ok}/{total_jobs} succeeded"
        + (f"; failed: {failed_labels}" if failed_labels else "")
    )
    return 0 if not failed_labels else 1
