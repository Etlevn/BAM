"""
Configuration file for LLM Trading Analysis project.
Centralizes all path configurations and experiment settings.
"""

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
    "api_mode": "expected_parrot",  # "openai" or "expected_parrot"
    "openai_api_key": os.getenv("OPENAI_API_KEY", ""),  # Load from .env file
    "expected_parrot_api_key": os.getenv("EXPECTED_PARROT_API_KEY", "")  # Load from .env file
}

# Model configuration
MODEL_CONFIG = {
    "num_llms": 23,  # Total number of LLM agents
    "model_name": "gpt-4o"  # Default model (used when Battle Royale is disabled)
}

# Battle Royale configuration
BATTLE_ROYALE_CONFIG = {
    "enabled": True,  # Enable/disable Battle Royale mode
    "assignment_strategy": "sequential",  # "random", "sequential", "balanced"
    "custom_models": [
        {
            "name": "claude-3-7-sonnet-20250219",
            "count": 20,
            "description": "claude-3-7-sonnet"
        },
        {
            "name": "gemini-2.0-flash-001",
            "count": 6,
            "description": "gemini-2.0-flash"
        }
    ]
}

def validate_model_configuration():
    """
    Validate that the total number of models matches the configured num_llms.
    """
    if BATTLE_ROYALE_CONFIG["enabled"] and "custom_models" in BATTLE_ROYALE_CONFIG:
        total_configured = sum(model["count"] for model in BATTLE_ROYALE_CONFIG["custom_models"])
        if total_configured != MODEL_CONFIG["num_llms"]:
            print(f"[config.py] WARNING: Model count mismatch!")
            print(f"[config.py] MODEL_CONFIG['num_llms'] = {MODEL_CONFIG['num_llms']}")
            print(f"[config.py] Total custom_models count = {total_configured}")
            print(f"[config.py] Please update MODEL_CONFIG['num_llms'] to {total_configured}")
            return False
        else:
            print(f"[config.py] Model configuration validated: {total_configured} total agents")
            return True
    return True

def get_total_model_count():
    """
    Get the total number of models from Battle Royale configuration.
    """
    if BATTLE_ROYALE_CONFIG["enabled"] and "custom_models" in BATTLE_ROYALE_CONFIG:
        return sum(model["count"] for model in BATTLE_ROYALE_CONFIG["custom_models"])
    return MODEL_CONFIG["num_llms"]

# === Auto JSON Fix Configuration ===
AUTO_JSON_FIX = {
    "enabled": True,  # Whether to enable post-round automatic JSON fix
    "create_backup": True,  # Whether to create backup files when fixing
    "verbose_logging": True,  # Whether to show detailed fix logs
}

def get_exp_dir(model_name):
    """Get experiment directory for a specific model."""
    return os.path.join(EXP_DIR, model_name.replace("/", "_"))

def get_log_file(exp_name):
    """Get log file path for an experiment."""
    return os.path.join(LOG_DIR, f"{exp_name}.log") 