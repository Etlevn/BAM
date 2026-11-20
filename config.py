"""
Experiment parameters only. Path/count helpers live in src.runtime.paths.
"""

import os

from dotenv import load_dotenv

# ============================================================
# Paths
# ============================================================

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXP_DIR = os.path.join(BASE_DIR, "exp")
LOG_DIR = os.path.join(BASE_DIR, "log")
PROMPT_DIR = os.path.join(BASE_DIR, "prompt")

os.makedirs(EXP_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ============================================================
# Experiment mode
# ============================================================

EXPERIMENT_MODE = "sgl"  # "br" or "sgl"

# First-level batch folder under exp/ (required). Example: "1_GPT", "2_EP", "3_BR", "4_BAS".
EXP_GROUP = "TEST"

SINGLE_MODEL_CONFIG = {
    "num_llms": 20,
    "model_name": "gpt-6-luna",
    "service_name": "",
}

BATTLE_ROYALE_CONFIG = {
    "assignment_strategy": "sequential",  # "random", "sequential", "balanced"
    "custom_models": [
        {
            "name": "gpt-5-nano",
            "count": 10,
            "service_name": "",
        },
        {
            "name": "gpt-6-luna",
            "count": 10,
            "service_name": "",
        },
    ],
}


# ============================================================
# Market / settlement parameters
# ============================================================

EXPERIMENT_CONFIG = {
    "initial_cash": 100,
    "initial_stocks": 4,
    "stock_value": 14,
    "interest_rate": 0.05,
    "dividend_low": 0.4,
    "dividend_high": 1.0,
    "dividend_prob": 0.5,
    # "fixed" = E[d] each round (legacy 0.7); "random" = common draw low/high.
    "dividend_mode": "fixed",
    "dividend_seed": None,
    "practice_rounds": 3,
    "total_rounds": 20,
    "max_order_quantity": 5,
}

API_CONFIG = {
    "api_mode": "openai",  # "openai", "expected_parrot", or "deepseek"
    "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
    "expected_parrot_api_key": os.getenv("EXPECTED_PARROT_API_KEY", ""),
    "deepseek_api_key": os.getenv("DEEPSEEK_API_KEY", ""),
}

DEBUG_CONFIG = {
    "save_raw_responses": False,
    "debug_directory": "debug",
}

AUTO_JSON_FIX = {
    "enabled": True,
    "create_backup": True,
}

# ============================================================
# BAS mode
# ============================================================

USE_BAS_MODE = True
# "base" | "amp_NN" | "sup_NN" (prompt/bas_biases.json); works for sgl and br.
BAS_BIAS_ID = "base"

# Optional per-process overrides (used by batch RUN_ALL_BAS children).
_bas_mode_env = os.getenv("BAM_USE_BAS_MODE")
if _bas_mode_env is not None and _bas_mode_env.strip() != "":
    USE_BAS_MODE = _bas_mode_env.strip().lower() in {"1", "true", "yes", "on"}
_bas_bias_env = os.getenv("BAM_BAS_BIAS_ID")
if _bas_bias_env is not None and _bas_bias_env.strip() != "":
    BAS_BIAS_ID = _bas_bias_env.strip()

PROMPT_FILES = {
    "experiment_start": "experiment_start.txt",
    "order_forecast_start": "order_forecast_start.txt",
    "order_forecast_end": "order_forecast_end.txt",
    "order_forecast_template": "order_forecast_template.json",
}
