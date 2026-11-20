"""Fail-fast checks for the configured LLM API backend."""

from __future__ import annotations

import config


def ensure_api_ready() -> None:
    """
    Validate that the selected API mode can run before any experiment starts.

    Raises RuntimeError / ValueError on missing packages, keys, or unknown mode.
    """
    mode = str(config.API_CONFIG.get("api_mode", "")).strip().lower()
    if mode == "openai":
        try:
            import openai  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "API_CONFIG['api_mode'] is 'openai' but package 'openai' is not installed. "
                "Install it (e.g. `.venv/bin/pip install openai`) or switch api_mode to "
                "'expected_parrot' / 'deepseek'."
            ) from e
        if not (config.API_CONFIG.get("openai_api_key") or "").strip():
            raise RuntimeError(
                "API mode is 'openai' but OPENAI_API_KEY is empty. Set it in .env."
            )
        return

    if mode == "deepseek":
        try:
            from openai import OpenAI  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "API_CONFIG['api_mode'] is 'deepseek' but package 'openai' "
                "(OpenAI-compatible client) is not installed."
            ) from e
        if not (config.API_CONFIG.get("deepseek_api_key") or "").strip():
            raise RuntimeError(
                "API mode is 'deepseek' but DEEPSEEK_API_KEY is empty. Set it in .env."
            )
        return

    if mode == "expected_parrot":
        try:
            import edsl  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "API_CONFIG['api_mode'] is 'expected_parrot' but package 'edsl' is not installed."
            ) from e
        if not (config.API_CONFIG.get("expected_parrot_api_key") or "").strip():
            raise RuntimeError(
                "API mode is 'expected_parrot' but EXPECTED_PARROT_API_KEY is empty. "
                "Set it in .env."
            )
        return

    raise ValueError(
        f"Unknown API mode {mode!r}. Expected 'openai', 'expected_parrot', or 'deepseek'."
    )
