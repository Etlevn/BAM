"""Entry: batch-run full experiments using settings in config.py."""

from src.runtime.batch import run_batch_main

# ============================================================
# Config
# ============================================================

# How many full experiments per config cell (each calls main.py).
NUM_RUNS = 1

# Max concurrent experiment processes.
MAX_WORKERS = 10

# Cycle base + amp/sup (41) × NUM_RUNS; uses config EXPERIMENT_MODE (sgl or br).
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
