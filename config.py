"""
Configuration file for LLM Trading Analysis project.
Centralizes all path configurations and experiment settings.
"""

# ============================================================

# Experiment mode configuration
EXPERIMENT_MODE = "sgl"  # "br" for Battle Royale mode, "sgl" for Single model mode

# Single model configuration
SINGLE_MODEL_CONFIG = {
    "num_llms": 20,  # Total number of LLM agents
    "model_name": "gemini-2.0-flash-001",  # Default model (used in single model mode)
    "description": "",  # Optional human-readable description
    "service_name": "",  # Service name for the model (e.g., "deep_infra", "google", "together", ). Set to None or empty string to use default
}

# Battle Royale configuration
BATTLE_ROYALE_CONFIG = {
    "assignment_strategy": "sequential",  # "random", "sequential", "balanced"
    "custom_models": [
        {
            "name": "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
            "count": 10,
            "description": "Llama 4 Maverick",
            "service_name": ""
        },
        {
            "name": "deepseek-ai/DeepSeek-V3-0324",
            "count": 10,
            "description": "DeepSeek V3",
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
    "total_rounds": 20
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

# === Prompt Files Configuration ===
# Specify the filenames for all prompt files used in the experiment
# All files should be located in init/prompt/ directory
PROMPT_FILES = {
    "experiment_start": "experiment_start_sup_4.txt",  # Main experiment start prompt
    "experiment_conditions": "experiment_conditions.json",  # Experiment conditions
    "order_forecast_start": "order_forecast_start.txt",  # Order forecast start prompt
    "order_forecast_end": "order_forecast_end_sup_4.txt",  # Order forecast end prompt
    "order_forecast_template": "order_forecast_template.json",  # Order forecast template
}

def get_exp_dir(model_name):
    """Get experiment directory for a specific model."""
    return os.path.join(EXP_DIR, model_name.replace("/", "_"))

def get_log_file(exp_name):
    """Get log file path for an experiment."""
    return os.path.join(LOG_DIR, f"{exp_name}.log") 
