"""Entry: run paper FE/table research jobs for selected exp/ groups."""

from research.belief_action import run_belief_action_groups
from research.bid_offer import run_bid_offer_groups
from research.disagreement import run_disagreement_groups
from research.disposition import run_disposition_groups
from research.extrapolation import run_extrapolation_groups
from research.mechanism_bubble import run_mechanism_bubble_groups
from research.stated_action import run_stated_action_groups
from research.stated_belief import run_stated_belief_groups

# ============================================================
# Config
# ============================================================

# First-level folder names under exp/ (e.g. "SGL", "BR", "TEST").
GROUPS = ["TEST"]    # ["SGL", "BR", "BAS"]

# Tables 2–4 (need panels/_behavior.csv)
RUN_DISPOSITION = True          # → <GROUP>_disposition.csv
RUN_EXTRAPOLATION = True        # → <GROUP>_extrapolation.csv
RUN_BELIEF_ACTION = True        # → <GROUP>_belief_action.csv

# Tables 5–6 (need panels/_equilibrium.csv)
RUN_BID_OFFER = True            # → <GROUP>_bid_offer.csv
RUN_DISAGREEMENT = True         # → <GROUP>_disagreement.csv

# Tables 7–8 (need panels/_cognition.csv)
RUN_STATED_BELIEF = True        # → <GROUP>_stated_belief.csv
RUN_STATED_ACTION = True        # → <GROUP>_stated_action.csv

# Table 9 FE (need panels/_mechanism.csv)
RUN_MECHANISM_BUBBLE = True     # → <GROUP>_mechanism_bubble.csv

# ============================================================


def main() -> int:
    if not GROUPS:
        raise ValueError("GROUPS is empty")

    if RUN_DISPOSITION:
        run_disposition_groups(GROUPS)
    if RUN_EXTRAPOLATION:
        run_extrapolation_groups(GROUPS)
    if RUN_BELIEF_ACTION:
        run_belief_action_groups(GROUPS)
    if RUN_BID_OFFER:
        run_bid_offer_groups(GROUPS)
    if RUN_DISAGREEMENT:
        run_disagreement_groups(GROUPS)
    if RUN_STATED_BELIEF:
        run_stated_belief_groups(GROUPS)
    if RUN_STATED_ACTION:
        run_stated_action_groups(GROUPS)
    if RUN_MECHANISM_BUBBLE:
        run_mechanism_bubble_groups(GROUPS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
