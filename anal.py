"""Entry: run market + rationality analysis for selected exp/ groups."""

from src.analysis.runner import run_groups

# ============================================================
# Config
# ============================================================

# First-level folder names under exp/ (e.g. "SGL", "BR").
GROUPS = ["TEST"]    # ["SGL", "BR", "BAS"]

RUN_MARKET = True              # → <GROUP>_market.csv
RUN_MARKET_ROBUST = True       # → <GROUP>_market_robust.csv (requires RUN_MARKET)
RUN_RATIONAL = True            # → <GROUP>_rational.csv
RUN_RATIONAL_ROBUST = True     # → <GROUP>_rational_robust.csv (requires RUN_RATIONAL)

RUN_PLOTS = True              # dual-axis price–volume PNGs (legacy style)
PLOTS_FOLDER = "plots"         # under exp/<GROUP>/_<GROUP>/ → <series>/<session>.png

# ============================================================


def main() -> int:
    run_groups(
        GROUPS,
        run_market=RUN_MARKET,
        run_market_robust=RUN_MARKET_ROBUST,
        run_rational=RUN_RATIONAL,
        run_rational_robust=RUN_RATIONAL_ROBUST,
        run_plots=RUN_PLOTS,
        plots_folder=PLOTS_FOLDER,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
