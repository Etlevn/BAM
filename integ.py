"""Entry: aggregate formal sessions under selected exp/ groups into _<GROUP>/."""

from src.integ.runner import run_groups

# ============================================================
# Config
# ============================================================

# First-level folder names under exp/ (e.g. "SGL", "BR").
GROUPS = ["SGL", "BR", "BAS"]

RUN_ORDERS = True      # → <GROUP>_rx.csv
RUN_SNAPSHOTS = True   # → <GROUP>_mkt.csv
RUN_OUTPUTS = True     # → <GROUP>_output.csv

# Non-complete sessions are moved under exp/<GROUP>/<series>/<this>/<session>/.
# Leading "_" is added automatically if omitted (e.g. "incomplete" → "_incomplete").
NONCOMPLETE_FOLDER = "_incomplete"

# ============================================================


def main() -> int:
    run_groups(
        GROUPS,
        run_orders=RUN_ORDERS,
        run_snapshots=RUN_SNAPSHOTS,
        run_outputs=RUN_OUTPUTS,
        noncomplete_folder=NONCOMPLETE_FOLDER,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
