"""Shared CLI helpers: apply mode / BAS / model onto config."""

from __future__ import annotations

import re

import config
from src.prompts import fill as prompt_fill
from src.runtime.paths import bas_series_prefix

_BIAS_RE = re.compile(r"^(amp|sup)_\d{2}$", re.IGNORECASE)


def _parse_models(raw: str) -> list[str]:
    text = str(raw).strip()
    if not text:
        raise ValueError("model must be non-empty")
    if "&" in text:
        parts = [p.strip() for p in text.split("&")]
    else:
        parts = [p.strip() for p in text.split(",")]
    parts = [p for p in parts if p]
    if not parts:
        raise ValueError("model must be non-empty")
    return parts


def _normalize_bas(bas: str) -> tuple[bool, str | None]:
    """Return (use_bas, bias_id)."""
    text = str(bas).strip()
    low = text.lower()
    if low in {"off", "none", "no", "false", "0", "-"}:
        return False, None
    if low == "base":
        return True, "base"
    if _BIAS_RE.match(text):
        return True, text.lower()
    try:
        prompt_fill.load_bas_bias(text)
    except KeyError as exc:
        raise ValueError(
            f"unknown bas id {bas!r}; use base, amp_NN, sup_NN, or off"
        ) from exc
    return True, text


def apply_run_overrides(*, mode: str, bas: str, model: str) -> None:
    """Mutate ``config`` in place from CLI values; other settings stay as in config.py."""
    mode_l = str(mode).strip().lower()
    if mode_l not in {"sgl", "br"}:
        raise ValueError(f"mode must be sgl or br, got {mode!r}")

    use_bas, bias_id = _normalize_bas(bas)
    models = _parse_models(model)

    config.EXPERIMENT_MODE = mode_l
    config.USE_BAS_MODE = use_bas
    if use_bas:
        assert bias_id is not None
        config.BAS_BIAS_ID = bias_id
        bas_series_prefix(bias_id)

    if mode_l == "sgl":
        if len(models) != 1:
            raise ValueError("sgl expects a single model name (not a comma list)")
        config.SINGLE_MODEL_CONFIG = {
            **config.SINGLE_MODEL_CONFIG,
            "model_name": models[0],
        }
    else:
        if len(models) == 1:
            raise ValueError(
                "br expects two models: 'modelA,modelB' (or 'A & B')"
            )
        if len(models) > 2:
            raise ValueError("br currently expects exactly two model names")
        existing = list(config.BATTLE_ROYALE_CONFIG.get("custom_models") or [])
        if len(existing) >= 2:
            counts = [int(existing[0].get("count", 10)), int(existing[1].get("count", 10))]
            services = [
                str(existing[0].get("service_name", "")),
                str(existing[1].get("service_name", "")),
            ]
        else:
            total = int(config.SINGLE_MODEL_CONFIG.get("num_llms", 20))
            counts = [total // 2, total - total // 2]
            services = ["", ""]
        config.BATTLE_ROYALE_CONFIG = {
            **config.BATTLE_ROYALE_CONFIG,
            "custom_models": [
                {"name": models[0], "count": counts[0], "service_name": services[0]},
                {"name": models[1], "count": counts[1], "service_name": services[1]},
            ],
        }
