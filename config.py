"""
Configuration file for LLM Trading Analysis project.
Centralizes all path configurations and experiment settings.
"""

# ============================================================

# Experiment mode configuration
EXPERIMENT_MODE = "sgl"  # "br" for Battle Royale mode, "sgl" for Single model mode

# First-level batch folder under exp/ (required). Example: "1_GPT", "2_EP", "3_BR", "4_BAS".
# Empty / whitespace raises at run start via require_exp_group().
EXP_GROUP = "2_EP"

# Single model configuration
SINGLE_MODEL_CONFIG = {
    "num_llms": 20,  # Total number of LLM agents
    "model_name": "gpt-4o",  # Default model (used in single model mode)
    "description": "ChatGPT-4o",  # Optional human-readable description
    "service_name": "",  # Service name for the model (e.g., "deep_infra", "google", "together", ). Set to None or empty string to use default
}

# Battle Royale configuration
BATTLE_ROYALE_CONFIG = {
    "assignment_strategy": "sequential",  # "random", "sequential", "balanced"
    "custom_models": [
        {
            "name": "claude-3-7-sonnet-20250219",
            "count": 10,
            "description": "Claude 3.7 Sonnet",
            "service_name": ""
        },
        {
            "name": "gemini-2.0-flash-001",
            "count": 10,
            "description": "Gemini 2.0 Flash",
            "service_name": ""
        }
    ]
}     

# ============================================================

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directory - use the directory where this config file is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Experiment directories
EXP_DIR = os.path.join(BASE_DIR, "exp")
LOG_DIR = os.path.join(BASE_DIR, "log")
INIT_DIR = os.path.join(BASE_DIR, "init")

# Initialize directories
os.makedirs(EXP_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# Experiment configuration
EXPERIMENT_CONFIG = {
    "initial_cash": 100,
    "initial_stocks": 4,
    "stock_value": 14,
    "interest_rate": 0.05,
    "dividend_low": 0.4,
    "dividend_high": 1.0,
    "dividend_prob": 0.5,
    "practice_rounds": 3,
    "total_rounds": 20,
    "max_order_quantity": 5,  # Per-order share cap; used in prompts + valid.py
}

# API configuration
API_CONFIG = {
    "api_mode": "expected_parrot",  # "openai", "expected_parrot", or "deepseek"
    "openai_api_key": os.getenv("OPENAI_API_KEY", ""),  # Load from .env file
    "expected_parrot_api_key": os.getenv("EXPECTED_PARROT_API_KEY", ""),  # Load from .env file
    "deepseek_api_key": os.getenv("DEEPSEEK_API_KEY", "")  # Load from .env file
}

def get_llm_count():
    """
    Get the correct number of LLMs based on current mode.
    Returns the sum of custom_models in Battle Royale mode, or SINGLE_MODEL_CONFIG['num_llms'] in single model mode.
    """
    if EXPERIMENT_MODE == "br" and "custom_models" in BATTLE_ROYALE_CONFIG:
        total_configured = sum(model["count"] for model in BATTLE_ROYALE_CONFIG["custom_models"])
        print(f"[config.py] Battle Royale mode enabled: using {total_configured} total agents from custom_models")
        return total_configured
    elif EXPERIMENT_MODE == "sgl":
        print(f"[config.py] Single model mode: using {SINGLE_MODEL_CONFIG['num_llms']} agents")
        return SINGLE_MODEL_CONFIG["num_llms"]
    else:
        raise ValueError(f"Invalid EXPERIMENT_MODE: {EXPERIMENT_MODE}. Must be 'br' or 'sgl'")

# === Debug Configuration ===
DEBUG_CONFIG = {
    "save_raw_responses": False,  # Whether to save raw LLM responses before parsing
    "debug_directory": "debug"  # Directory to save debug files (relative to experiment directory)
}

# === Auto JSON Fix Configuration ===
AUTO_JSON_FIX = {
    "enabled": True,  # Whether to enable post-round automatic JSON fix
    "create_backup": True,  # Whether to create backup files when fixing
}

# === BAS Mode Configuration ===
# When True, overlay one shared bias sentence (BAS_BIAS_ID) onto the standard prompts.
USE_BAS_MODE = False
BAS_BIAS_ID = "amp_1"  # Key in init/prompt/bas_biases.json (e.g. amp_1..amp_20, sup_1..sup_20)

# === Prompt Files Configuration ===
# Standard templates only; BAS no longer swaps in full duplicate files.
PROMPT_FILES = {
    "experiment_start": "experiment_start.txt",
    "order_forecast_start": "order_forecast_start.txt",
    "order_forecast_end": "order_forecast_end.txt",
    "order_forecast_template": "order_forecast_template.json",
}

def sanitize_model_dirname(name: str) -> str:
    """Filesystem-safe model folder segment: strip and replace '/' with '_'."""
    return str(name).strip().replace("/", "_")


def require_exp_group() -> str:
    """Return EXP_GROUP or raise if unset (first-level batch folder is mandatory)."""
    group = str(EXP_GROUP).strip() if EXP_GROUP is not None else ""
    if not group:
        raise ValueError(
            "EXP_GROUP is required in config.py (e.g. '2_EP', '3_BR', '4_BAS'). "
            "Refusing to write experiments under a flat exp/timestamp path."
        )
    return group


def get_exp_series_name() -> str:
    """
    Second-level series folder under exp/{EXP_GROUP}/.

    - sgl: sanitized SINGLE_MODEL_CONFIG['model_name']
    - br: sanitized custom_models names joined with ' & '
    """
    if EXPERIMENT_MODE == "sgl":
        return sanitize_model_dirname(SINGLE_MODEL_CONFIG["model_name"])
    if EXPERIMENT_MODE == "br":
        models = BATTLE_ROYALE_CONFIG.get("custom_models") or []
        if not models:
            raise ValueError("Battle Royale mode requires BATTLE_ROYALE_CONFIG['custom_models']")
        return " & ".join(sanitize_model_dirname(m["name"]) for m in models)
    raise ValueError(f"Invalid EXPERIMENT_MODE: {EXPERIMENT_MODE}. Must be 'br' or 'sgl'")


def get_exp_series_dir() -> str:
    """Parent directory for new runs: exp/{EXP_GROUP}/{series}."""
    return os.path.join(EXP_DIR, require_exp_group(), get_exp_series_name())


def get_exp_dir(model_name=None):
    """
    Directory that holds timestamped runs for the current series.

    If model_name is provided (legacy callers), returns exp/{EXP_GROUP}/{sanitize(model_name)}.
    Otherwise uses get_exp_series_name() for the active mode.
    """
    group = require_exp_group()
    series = sanitize_model_dirname(model_name) if model_name else get_exp_series_name()
    return os.path.join(EXP_DIR, group, series)


def get_log_file(exp_name):
    """Get log file path for an experiment."""
    return os.path.join(LOG_DIR, f"{exp_name}.log")

def get_prompt_file_path(prompt_key, base_prompt_dir):
    """Return path to a standard prompt template under base_prompt_dir."""
    if prompt_key not in PROMPT_FILES:
        raise KeyError(f"Unknown prompt key {prompt_key!r}; known: {sorted(PROMPT_FILES)}")
    return os.path.join(base_prompt_dir, PROMPT_FILES[prompt_key]) 
