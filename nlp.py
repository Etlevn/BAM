"""Entry: NLP mechanism coding / merge / miss for selected exp/ groups."""

from pathlib import Path

import config
from src.nlp.runner import run_groups

# ============================================================
# Config
# ============================================================

# First-level folder names under exp/ (e.g. "SGL", "BR").
GROUPS = ["SGL"]  # ["SGL", "BR", "BAS"]

RUN_CODE = False    # → _<GROUP>/nlp/*.json
RUN_POST = True    # → _<GROUP>/<GROUP>_output_nlp.csv + _output_miss.csv

# Prompt (sole template).
PROMPT_FILE = "nlp_prmt.txt"  # under config.PROMPT_DIR (prompt/)

# API / processing (formerly nlp_config.json).
API_MODE = "deepseek"
MODEL_NAME = "deepseek-flash"
MAX_WORKERS = 100
MAX_PROCESSING_ROWS = None  # int or None
SAVE_INDIVIDUAL_JSON = True
EVALUATE_PLAN = True
EVALUATE_INSIGHT = True

MECHANISM_ORDER = [
    "rational_speculative_bubble",
    "synchronization_risk",
    "asymmetric_information",
    "extrapolation_vs_anchor",
    "diagnostic_expectations",
    "wavering_behavior",
    "disposition_effect",
    "momentum_vs_newswatcher",
    "feedback_trading",
    "overconfidence",
    "self_attribution_bias",
    "herding_contagion",
    "disagreement_heterogeneous_beliefs",
    "representativeness_heuristic",
    "new_era_thinking",
    "availability_bias",
    "limited_arbitrage_awareness",
    "loss_aversion",
    "narrative_tone",
    "statistical_testing",
]

# ============================================================


def _nlp_cfg() -> dict:
    return {
        "api_mode": API_MODE,
        "model_name": MODEL_NAME,
        "max_workers": MAX_WORKERS,
        "max_processing_rows": MAX_PROCESSING_ROWS,
        "save_individual_json": SAVE_INDIVIDUAL_JSON,
        "evaluate_plan": EVALUATE_PLAN,
        "evaluate_insight": EVALUATE_INSIGHT,
        "mechanism_order": list(MECHANISM_ORDER),
    }


def main() -> int:
    prompt_path = Path(config.PROMPT_DIR) / PROMPT_FILE
    run_groups(
        GROUPS,
        run_code_flag=RUN_CODE,
        run_post=RUN_POST,
        nlp_cfg=_nlp_cfg(),
        prompt_path=prompt_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
