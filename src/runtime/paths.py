"""Path helpers and derived config accessors (logic extracted from config.py)."""

from __future__ import annotations

import os
import re

import config


def get_llm_count() -> int:
    """Agent count from Battle Royale custom_models or SINGLE_MODEL_CONFIG."""
    if config.EXPERIMENT_MODE == "br" and "custom_models" in config.BATTLE_ROYALE_CONFIG:
        total_configured = sum(
            model["count"] for model in config.BATTLE_ROYALE_CONFIG["custom_models"]
        )
        print(
            f"[paths] Battle Royale mode enabled: using {total_configured} "
            "total agents from custom_models"
        )
        return total_configured
    if config.EXPERIMENT_MODE == "sgl":
        print(
            f"[paths] Single model mode: using {config.SINGLE_MODEL_CONFIG['num_llms']} agents"
        )
        return config.SINGLE_MODEL_CONFIG["num_llms"]
    raise ValueError(
        f"Invalid EXPERIMENT_MODE: {config.EXPERIMENT_MODE}. Must be 'br' or 'sgl'"
    )


def sanitize_model_dirname(name: str) -> str:
    """Filesystem-safe model folder segment: strip and replace '/' with '_'."""
    return str(name).strip().replace("/", "_")


def require_exp_group() -> str:
    """Return EXP_GROUP or raise if unset (first-level batch folder is mandatory)."""
    group = str(config.EXP_GROUP).strip() if config.EXP_GROUP is not None else ""
    if not group:
        raise ValueError(
            "EXP_GROUP is required in config.py (e.g. '2_EP', '3_BR', '4_BAS'). "
            "Refusing to write experiments under a flat exp/timestamp path."
        )
    return group


def bas_series_prefix(bias_id: str) -> str:
    """Map bias id to series prefix: base→b, amp_01→a01, sup_20→s20."""
    text = str(bias_id).strip()
    if text.lower() == "base":
        return "b"
    m = re.fullmatch(r"(amp|sup)_(\d{2})", text)
    if not m:
        raise ValueError(
            f"Invalid BAS_BIAS_ID {bias_id!r}; expected 'base', 'amp_NN', or 'sup_NN' "
            "with two-digit index (e.g. 'base', 'amp_01', 'sup_20')"
        )
    family, num = m.group(1), m.group(2)
    return ("a" if family == "amp" else "s") + num


def get_exp_series_name() -> str:
    """Series folder under exp/{EXP_GROUP}/; BAS mode adds b_/aNN_/sNN_ prefix."""
    if config.EXPERIMENT_MODE == "sgl":
        base = sanitize_model_dirname(config.SINGLE_MODEL_CONFIG["model_name"])
    elif config.EXPERIMENT_MODE == "br":
        models = config.BATTLE_ROYALE_CONFIG.get("custom_models") or []
        if not models:
            raise ValueError(
                "Battle Royale mode requires BATTLE_ROYALE_CONFIG['custom_models']"
            )
        base = " & ".join(sanitize_model_dirname(m["name"]) for m in models)
    else:
        raise ValueError(
            f"Invalid EXPERIMENT_MODE: {config.EXPERIMENT_MODE}. Must be 'br' or 'sgl'"
        )
    if config.USE_BAS_MODE:
        return f"{bas_series_prefix(config.BAS_BIAS_ID)}_{base}"
    return base


def get_exp_series_dir() -> str:
    """Parent directory for new runs: exp/{EXP_GROUP}/{series}."""
    return os.path.join(config.EXP_DIR, require_exp_group(), get_exp_series_name())


def get_exp_dir(model_name=None) -> str:
    """
    Directory that holds timestamped runs for the current series.

    If model_name is provided (legacy callers), returns exp/{EXP_GROUP}/{sanitize(model_name)}.
    Otherwise uses get_exp_series_name() for the active mode.
    """
    group = require_exp_group()
    series = sanitize_model_dirname(model_name) if model_name else get_exp_series_name()
    return os.path.join(config.EXP_DIR, group, series)


def get_log_file(exp_name: str) -> str:
    """Get log file path for an experiment."""
    return os.path.join(config.LOG_DIR, f"{exp_name}.log")


def get_prompt_file_path(prompt_key: str, base_prompt_dir: str) -> str:
    """Return path to a standard prompt template under base_prompt_dir."""
    if prompt_key not in config.PROMPT_FILES:
        raise KeyError(
            f"Unknown prompt key {prompt_key!r}; known: {sorted(config.PROMPT_FILES)}"
        )
    return os.path.join(base_prompt_dir, config.PROMPT_FILES[prompt_key])
