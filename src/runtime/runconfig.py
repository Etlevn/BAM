"""Unified session config.json: build, write, completeness status."""

from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any

import config

CONFIG_FILENAME = "config.json"
LEGACY_CONFIG_NAMES = ("sgl_config.json", "br_config.json")
_ROUND_DIR_RE = re.compile(r"^r(\d+)$")


def experiment_snapshot() -> dict[str, Any]:
    """Result-relevant snapshot from config.py (no secrets/paths)."""
    return {
        "EXP_GROUP": config.EXP_GROUP,
        "EXPERIMENT_MODE": config.EXPERIMENT_MODE,
        "USE_BAS_MODE": bool(config.USE_BAS_MODE),
        "BAS_BIAS_ID": config.BAS_BIAS_ID if config.USE_BAS_MODE else None,
        "EXPERIMENT_CONFIG": copy.deepcopy(config.EXPERIMENT_CONFIG),
    }


def _model_entry(name: str, count: int, service_name: str = "") -> dict[str, Any]:
    return {
        "name": name,
        "count": int(count),
        "service_name": service_name or "",
    }


def build_sgl_session_config(num_llms: int, model_name: str, service_name: str = "") -> dict[str, Any]:
    assignments = {f"llm_{i:03d}": model_name for i in range(1, num_llms + 1)}
    return {
        "num_llms": num_llms,
        "models": [_model_entry(model_name, num_llms, service_name)],
        "assignment_strategy": None,
        "assignments": assignments,
        "experiment": experiment_snapshot(),
        "status": "running",
    }


def build_br_session_config(battle_manager: Any) -> dict[str, Any]:
    mc = battle_manager.model_config
    models = []
    for m in mc.get("models") or []:
        models.append(
            _model_entry(
                str(m["name"]),
                int(m["count"]),
                str(m.get("service_name") or ""),
            )
        )
    assignments = {
        str(k): str(v) for k, v in (battle_manager.model_assignment or {}).items()
    }
    return {
        "num_llms": int(mc["total_agents"]),
        "models": models,
        "assignment_strategy": mc.get("assignment_strategy"),
        "assignments": assignments,
        "experiment": experiment_snapshot(),
        "status": "running",
    }


def config_path(exp_run_dir: str | os.PathLike[str]) -> Path:
    return Path(exp_run_dir) / CONFIG_FILENAME


def write_session_config(exp_run_dir: str | os.PathLike[str], data: dict[str, Any]) -> Path:
    path = config_path(exp_run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path


def load_session_config(exp_run_dir: str | os.PathLike[str]) -> dict[str, Any] | None:
    """Load unified config.json, else first legacy file if present."""
    root = Path(exp_run_dir)
    primary = root / CONFIG_FILENAME
    if primary.is_file():
        return json.loads(primary.read_text(encoding="utf-8"))
    for name in LEGACY_CONFIG_NAMES:
        p = root / name
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    return None


def count_output_rounds(io_root: str | os.PathLike[str]) -> int:
    out = Path(io_root) / "output"
    if not out.is_dir():
        return 0
    n = 0
    for p in out.iterdir():
        if p.is_dir() and _ROUND_DIR_RE.match(p.name):
            n += 1
    return n


def evaluate_completeness(
    exp_run_dir: str | os.PathLike[str],
    *,
    practice_rounds: int | None = None,
    total_rounds: int | None = None,
) -> str:
    """
    Criterion A: formal rounds >= total_rounds; if practice_rounds > 0,
    prac/ must exist with >= practice_rounds.
    """
    root = Path(exp_run_dir)
    if practice_rounds is None or total_rounds is None:
        cfg = load_session_config(root) or {}
        exp = cfg.get("experiment") or {}
        ec = exp.get("EXPERIMENT_CONFIG") or {}
        if practice_rounds is None:
            practice_rounds = int(ec.get("practice_rounds", 0) or 0)
        if total_rounds is None:
            total_rounds = int(ec.get("total_rounds", 0) or 0)

    practice_rounds = int(practice_rounds or 0)
    total_rounds = int(total_rounds or 0)

    main_n = count_output_rounds(root)
    if total_rounds > 0 and main_n < total_rounds:
        return "incomplete"

    if practice_rounds > 0:
        prac = root / "prac"
        if not prac.is_dir():
            return "incomplete"
        if count_output_rounds(prac) < practice_rounds:
            return "incomplete"

    if total_rounds <= 0 and practice_rounds <= 0:
        return "incomplete"

    return "complete"


def update_status(exp_run_dir: str | os.PathLike[str], status: str | None = None) -> str:
    """Recompute or set status on config.json (creates nothing if missing)."""
    path = config_path(exp_run_dir)
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if status is None:
        status = evaluate_completeness(exp_run_dir)
    data["status"] = status
    # Drop obsolete keys if present from older drafts / legacy merges
    for k in ("mode", "expected", "observed", "checked_at", "model_name", "service_name"):
        data.pop(k, None)
    write_session_config(exp_run_dir, data)
    return status
