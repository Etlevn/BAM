"""Entry: aggregate formal sessions under selected exp/ groups into _<GROUP>/integrate/."""

from src.integ.runner import run_groups

# ============================================================
# Config
# ============================================================

# First-level folder names under exp/ 
GROUPS = ["TEST"]      # ["SGL", "BR", "BAS"] 

RUN_ORDERS = True      # → integrate/<GROUP>_rx.csv
RUN_SNAPSHOTS = True   # → integrate/<GROUP>_mkt.csv
RUN_OUTPUTS = True     # → integrate/<GROUP>_output.csv

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
