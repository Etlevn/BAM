"""
Configuration file for LLM Trading Analysis project.
Centralizes all path configurations and experiment settings.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directory - use current working directory
BASE_DIR = os.getcwd()

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

# Model configuration
MODEL_CONFIG = {
    "num_llms": 20,
    "model_name": "gpt-4o"
}

# API configuration
API_CONFIG = {
    "api_mode": "expected_parrot",  # "openai" or "expected_parrot"
    "openai_api_key": os.getenv("OPENAI_API_KEY", ""),  # Load from .env file
    "expected_parrot_api_key": os.getenv("EXPECTED_PARROT_API_KEY", "")  # Load from .env file
}

# Battle Royale configuration
BATTLE_ROYALE_CONFIG = {
    "enabled": True,  # Enable/disable Battle Royale mode
    "assignment_strategy": "sequential",  # "random", "sequential", "balanced"
    "custom_models": [
        {
            "name": "gpt-4o",
            "count": 5,
            "description": "GPT-4 Omni model"
        },
        {
            "name": "claude-3-7-sonnet-20250219",
            "count": 5,
            "description": "Claude 3.7 Sonnet model"
        },
        {
            "name": "grok-3",
            "count": 5,
            "description": "Grok-3 model"
        },
        {
            "name": "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
            "count": 5,
            "description": "Llama-4-Maverick model"
        }
    ]
}

def get_exp_dir(model_name):
    """Get experiment directory for a specific model."""
    return os.path.join(EXP_DIR, model_name.replace("/", "_"))

def get_log_file(exp_name):
    """Get log file path for an experiment."""
    return os.path.join(LOG_DIR, f"{exp_name}.log") 