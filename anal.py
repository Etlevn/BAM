"""Entry: run market + rationality analysis for selected exp/ groups."""

from src.analysis.runner import run_groups

# ============================================================
# Config
# ============================================================

# First-level folder names under exp/ 
GROUPS = ["TEST"]               # ["SGL", "BR", "BAS"]

RUN_MARKET = True               # → metrics/<GROUP>_market.csv
RUN_MARKET_ROBUST = True        # → metrics/<GROUP>_market_robust_{sgl,br}.csv
RUN_RATIONAL = True             # → metrics/<GROUP>_rational.csv
RUN_RATIONAL_ROBUST = True      # → metrics/<GROUP>_rational_robust_{sgl,br}.csv

RUN_PLOTS = False               # → _<GROUP>/plots/market/<series>/<session>.png

# Figure 2 data: per-round mean price / 95% CI / mean volume from integ _mkt.csv.
RUN_MKT_AGG = True              # → <GROUP>_mkt_agg.csv (requires integ <GROUP>_mkt.csv)
RUN_MKT_AGG_PLOT = False        # → _<GROUP>/plots/mkt_agg/{mode}_{bas}_{series}.png

# Tables 2–4 variables: agent–round panel from integ _mkt + _rx.
RUN_BEHAVIOR = True             # → panels/<GROUP>_behavior.csv (requires integrate/)

# Tables 5–6 variables: session–round panel from integ _mkt + _rx.
RUN_EQUILIBRIUM = True          # → panels/<GROUP>_equilibrium.csv (requires integrate/)

# Tables 7–8 variables: agent–round panel from integ _mkt + _rx + _output.
RUN_COGNITION = True            # → panels/<GROUP>_cognition.csv (requires integrate/)

# Table 9: agent–round–mechanism from integ _mkt + nlp/_output_nlp (mode=sgl only).
RUN_MECHANISM = True            # → panels/<GROUP>_mechanism.csv; skip if missing nlp or no sgl

# Table 10: Amp/Sup vs same-mode base (only if BAS sessions exist).
RUN_INTERVENTION = True         # → <GROUP>_intervention.csv at _<GROUP>/ root; else skip

# ============================================================


def main() -> int:
    run_groups(
        GROUPS,
        run_market=RUN_MARKET,
        run_market_robust=RUN_MARKET_ROBUST,
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
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
