"""Entry: aggregate formal sessions under selected exp/ groups into _<GROUP>/."""

from src.integ.runner import run_groups

# ============================================================
# Config
# ============================================================

# First-level folder names under exp/ (e.g. "SGL", "BR").
GROUPS = ["TEST"]    # ["SGL", "BR", "BAS"] 

RUN_ORDERS = True      # → <GROUP>_rx.csv
RUN_SNAPSHOTS = True   # → <GROUP>_mkt.csv
RUN_OUTPUTS = True     # → <GROUP>_output.csv

# ============================================================


def main() -> int:
    run_groups(
        GROUPS,
        run_orders=RUN_ORDERS,
        run_snapshots=RUN_SNAPSHOTS,
        run_outputs=RUN_OUTPUTS,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
