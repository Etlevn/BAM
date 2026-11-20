import datetime
import os

import pandas as pd

import config
from src.runtime import paths

# Global directory variables
PROMPT_DIR = None
EXP_INPUT_DIR = None
EXP_OUTPUT_DIR = None
EXP_MARKET_DIR = None

# Cached experiment config dictionary
_experiment_config = None


def get_experiment_config():
    """
    Returns experiment configuration from config.py.
    Uses internal cache to avoid redundant reads.
    """
    global _experiment_config
    if _experiment_config is not None:
        return _experiment_config

    _experiment_config = config.EXPERIMENT_CONFIG
    return _experiment_config


def bind_exp_dirs(io_root: str) -> None:
    """Point EXP_* globals at input/output/market under io_root."""
    global EXP_INPUT_DIR, EXP_OUTPUT_DIR, EXP_MARKET_DIR
    EXP_INPUT_DIR = os.path.join(io_root, "input")
    EXP_OUTPUT_DIR = os.path.join(io_root, "output")
    EXP_MARKET_DIR = os.path.join(io_root, "market")


def ensure_io_dirs(io_root: str, *, init_mkt: bool = True) -> str:
    """
    Create input/output/market under io_root, bind globals, optionally seed mkt.csv.
    Returns io_root.
    """
    bind_exp_dirs(io_root)
    os.makedirs(EXP_INPUT_DIR, exist_ok=True)
    os.makedirs(EXP_OUTPUT_DIR, exist_ok=True)
    os.makedirs(EXP_MARKET_DIR, exist_ok=True)

    if init_mkt:
        stock_value = get_experiment_config()["stock_value"]
        mkt_csv_path = os.path.join(EXP_MARKET_DIR, "mkt.csv")
        if not os.path.exists(mkt_csv_path):
            pd.DataFrame(
                {"round": [0], "mkt": [stock_value], "vol": [0]}
            ).to_csv(mkt_csv_path, index=False)
            print(
                f"[init.py] Market price initialized at {stock_value} "
                f"and saved to {mkt_csv_path}"
            )
    return io_root


def ensure_prac_dirs(exp_run_dir: str) -> str:
    """Create nested prac/{input,output,market} under the session timestamp dir."""
    prac_root = os.path.join(exp_run_dir, "prac")
    return ensure_io_dirs(prac_root, init_mkt=True)


def _claim_run_dirname(parent: str) -> str:
    """
    Second-precision timestamp folder (YYYYMMDD_HHMMSS).
    On same-second collision, wait and retry until a free name is claimed.
    """
    import time

    while True:
        name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        exp_run_dir = os.path.join(parent, name)
        try:
            os.makedirs(exp_run_dir)
            return exp_run_dir
        except FileExistsError:
            time.sleep(0.25)


def initialize_experiment(WORK_DIR):
    """
    Initializes the experiment environment by:
    - Changing working directory
    - Creating exp/{EXP_GROUP}/{series}/{YYYYMMDD_HHMMSS}/ with input/output/market
    - Setting PROMPT_DIR for read-only templates under prompt/
    - Initializing mkt.csv with stock_value from configuration

    Returns:
        exp_run_dir (str): path to the current experiment run folder
    """
    global PROMPT_DIR

    os.chdir(WORK_DIR)

    PROMPT_DIR = os.path.join(WORK_DIR, "prompt")

    EXP_DIR = os.path.join(WORK_DIR, "exp")
    os.makedirs(EXP_DIR, exist_ok=True)

    group = paths.require_exp_group()
    series = paths.get_exp_series_name()
    parent = os.path.join(EXP_DIR, group, series)
    os.makedirs(parent, exist_ok=True)

    exp_run_dir = _claim_run_dirname(parent)
    ensure_io_dirs(exp_run_dir, init_mkt=True)

    print(f"[init.py] Experiment run directory: {exp_run_dir}")

    return exp_run_dir
