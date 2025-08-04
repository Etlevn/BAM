"""
Configuration file for LLM Trading Analysis project.
Centralizes all path configurations and experiment settings.
"""

import os

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
    "openai_api_key": "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"
}

def get_exp_dir(model_name):
    """Get experiment directory for a specific model."""
    return os.path.join(EXP_DIR, model_name.replace("/", "_"))

def get_log_file(exp_name):
    """Get log file path for an experiment."""
    return os.path.join(LOG_DIR, f"{exp_name}.log") 