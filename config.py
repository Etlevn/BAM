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
    "num_llms": 20,  # Total number of LLM agents
    "model_name": "deepcogito/cogito-v2-preview-deepseek-671b",  # Default model (used when Battle Royale is disabled)
    "service_name": "together"  # Service name for the model (e.g., "deep_infra", "google", "together", ). Set to None or empty string to use default
}

# Battle Royale configuration
BATTLE_ROYALE_CONFIG = {
    "enabled": False,  # Enable/disable Battle Royale mode
    "assignment_strategy": "sequential",  # "random", "sequential", "balanced"
    "custom_models": [
        {
            "name": "claude-3-7-sonnet-20250219",
            "count": 10,
            "description": "claude-3-7-sonnet",
            "service_name": None  
        },
        {
            "name": "gemini-2.0-flash-001",
            "count": 20,
            "description": "gemini-2.0-flash",
            "service_name": None
        }
    ]
}

def get_llm_count():
    """
    Get the correct number of LLMs based on current mode.
    Returns the sum of custom_models in Battle Royale mode, or MODEL_CONFIG['num_llms'] in single model mode.
    """
    if BATTLE_ROYALE_CONFIG["enabled"] and "custom_models" in BATTLE_ROYALE_CONFIG:
        total_configured = sum(model["count"] for model in BATTLE_ROYALE_CONFIG["custom_models"])
        print(f"[config.py] Battle Royale mode enabled: using {total_configured} total agents from custom_models")
        return total_configured
    else:
        print(f"[config.py] Single model mode: using {MODEL_CONFIG['num_llms']} agents")
        return MODEL_CONFIG["num_llms"]

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

def get_exp_dir(model_name):
    """Get experiment directory for a specific model."""
    return os.path.join(EXP_DIR, model_name.replace("/", "_"))

def get_log_file(exp_name):
    """Get log file path for an experiment."""
    return os.path.join(LOG_DIR, f"{exp_name}.log") 
