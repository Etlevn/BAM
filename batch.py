"""Entry: batch-run full experiments using settings in config.py."""

from src.runtime.batch import run_batch_main

# ============================================================
# Config
# ============================================================

# How many full experiments per config cell (each calls main.py).
NUM_RUNS = 1

# Max concurrent experiment processes.
MAX_WORKERS = 10

# When True: force BAS on, cycle all amp_01–20 + sup_01–20 (40 biases) × NUM_RUNS.
# Example: NUM_RUNS=10 → 400 experiments. Uses same model/series settings from config.py.
RUN_ALL_BAS = True

# ============================================================


def main() -> int:
    return run_batch_main(
        num_runs=NUM_RUNS,
        max_workers=MAX_WORKERS,
        run_all_bas=RUN_ALL_BAS,
    )


if __name__ == "__main__":
    raise SystemExit(main())
