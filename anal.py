"""Entry: run market + rationality analysis for selected exp/ groups."""

from src.analysis.runner import run_groups

# ============================================================
# Config
# ============================================================

# First-level folder names under exp/ (e.g. "SGL", "BR").
GROUPS = ["SGL", "BR"]    # ["SGL", "BR", "BAS"]

RUN_MARKET = True              # → <GROUP>_market.csv
RUN_MARKET_ROBUST = True       # → <GROUP>_market_robust.csv (requires RUN_MARKET)
RUN_RATIONAL = True            # → <GROUP>_rational.csv
RUN_RATIONAL_ROBUST = True     # → <GROUP>_rational_robust.csv (requires RUN_RATIONAL)

# BR only: explode pair→model in memory → unweighted mean/CI (like SGL robust).
RUN_MARKET_AGG_ROBUST = True   # → BR_market_agg_robust.csv (requires RUN_MARKET)

# Figure 2 data: per-round mean price / 95% CI / mean volume from integ _mkt.csv.
RUN_MKT_AGG = True             # → <GROUP>_mkt_agg.csv (requires integ <GROUP>_mkt.csv)
RUN_MKT_AGG_PLOT = False       # → <GROUP>/plots/_mkt_agg.png (needs mkt_agg CSV or RUN_MKT_AGG)

# Tables 2–4 variables: agent–round panel from integ _mkt + _rx.
RUN_BEHAVIOR = True            # → <GROUP>_behavior.csv (requires integ; no fallback)

# Tables 5–6 variables: session–round panel from integ _mkt + _rx.
RUN_EQUILIBRIUM = True         # → <GROUP>_equilibrium.csv (requires integ; no fallback)

# Tables 7–8 variables: agent–round panel from integ _mkt + _rx + _output.
RUN_COGNITION = True           # → <GROUP>_cognition.csv (requires integ; no fallback)

# Table 9 variables: agent–round–mechanism from integ _mkt + _output_nlp.
RUN_MECHANISM = True           # → <GROUP>_mechanism.csv (requires nlp RUN_POST; no fallback)

RUN_INTERVENTION = False       # → BAS_intervention*.csv (Amp/Sup vs in-group base)

RUN_PLOTS = False              # dual-axis price–volume PNGs (legacy style)
PLOTS_FOLDER = "plots"         # under exp/<GROUP>/_<GROUP>/ → <series>/<session>.png

# ============================================================


def main() -> int:
    run_groups(
        GROUPS,
        run_market=RUN_MARKET,
        run_market_robust=RUN_MARKET_ROBUST,
        run_market_agg_robust=RUN_MARKET_AGG_ROBUST,
        run_mkt_agg=RUN_MKT_AGG,
        run_mkt_agg_plot=RUN_MKT_AGG_PLOT,
        run_behavior=RUN_BEHAVIOR,
        run_equilibrium=RUN_EQUILIBRIUM,
        run_cognition=RUN_COGNITION,
        run_mechanism=RUN_MECHANISM,
        run_intervention=RUN_INTERVENTION,
        run_rational=RUN_RATIONAL,
        run_rational_robust=RUN_RATIONAL_ROBUST,
        run_plots=RUN_PLOTS,
        plots_folder=PLOTS_FOLDER,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
