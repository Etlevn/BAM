import os

from src.portfolio import dividend as dividend_mod
from src.runtime import setup


def prepare_round_zero(
    num_llms,
    total_rounds,
    mode="main",
    io_root=None,
    require_reflections=False,
):
    """
    Generate round-0 market/portfolio/plans/insights under {io_root}/input/r0/.

    For mode=="main" with require_reflections=True, existing reflection files
    (written by the practice refl step into formal input/r0) are preserved;
    missing ones raise. Without practice, writes "(NONE)" reflections.
    For mode=="prac", always writes "(NONE)" reflections.
    """
    if not io_root:
        raise ValueError("io_root is required (session or prac I/O root)")

    experiment_config = setup.get_experiment_config()
    r0_dir = os.path.join(io_root, "input", "r0")
    os.makedirs(r0_dir, exist_ok=True)

    market_price = experiment_config["stock_value"]
    initial_cash = experiment_config["initial_cash"]
    initial_stocks = experiment_config["initial_stocks"]
    interest_rate = experiment_config["interest_rate"]
    buyback_price = experiment_config["stock_value"]

    dividend_earned = initial_stocks * dividend_mod.expected_dividend_per_share(
        experiment_config
    )
    interest_earned = initial_cash * interest_rate
    stock_value = initial_stocks * market_price
    expected_redemption = initial_stocks * buyback_price
    remaining_rounds = total_rounds
    market_volume = 0

    for i in range(1, num_llms + 1):
        llm_id = f"llm_{i:03d}"

        market_txt_path = os.path.join(r0_dir, f"{llm_id}_r0_market.txt")
        with open(market_txt_path, "w", encoding="utf-8") as f:
            f.write(f"""Round 0:

- Market + Portfolio Data:

  - Market price: {market_price}
  - Market volume: {market_volume}
  - # of shares owned: {initial_stocks}
  - Current cash: {initial_cash}
  - Stock value: {stock_value}
  - Dividend earned: {dividend_earned}
  - Interest earned: {interest_earned}
  - Submitted orders:
    - No Submitted orders
  - Executed trades:
    - No executed trades """)

        print(f"[prep.py] Created {market_txt_path}")

        portfolio_txt_path = os.path.join(r0_dir, f"{llm_id}_r0_portfolio.txt")
        with open(portfolio_txt_path, "w", encoding="utf-8") as f:
            f.write(f"""Your Portfolio (Round 0, {remaining_rounds} rounds remaining):

- Market price (Previous Round): {market_price}
- Buyback price: {buyback_price}
- # of shares owned: {initial_stocks}
- Current cash: {initial_cash}
- Stock value: {stock_value}
- Expected redemption value: {expected_redemption}""")

        print(f"[prep.py] Created {portfolio_txt_path}")

        plans_txt_path = os.path.join(r0_dir, f"{llm_id}_r0_plans.txt")
        with open(plans_txt_path, "w", encoding="utf-8") as f:
            f.write("(NONE)\n")
        print(f"[prep.py] Created {plans_txt_path}")

        insights_txt_path = os.path.join(r0_dir, f"{llm_id}_r0_insights.txt")
        with open(insights_txt_path, "w", encoding="utf-8") as f:
            f.write("(NONE)\n")
        print(f"[prep.py] Created {insights_txt_path}")

        reflection_dest = os.path.join(r0_dir, f"{llm_id}_r0_reflection.txt")

        if mode == "main" and require_reflections:
            if not os.path.exists(reflection_dest):
                raise FileNotFoundError(
                    f"Missing practice reflection for {llm_id}: {reflection_dest}"
                )
            print(f"[prep.py] Preserved existing reflection {reflection_dest}")
            continue

        if mode == "main":
            content = "(NONE)\n"
            print(f"[prep.py] No practice reflections required; default for {llm_id}")
        else:
            content = "(NONE)\n"
            print(f"[prep.py] [prac mode] Created default reflection for {llm_id}")

        with open(reflection_dest, "w", encoding="utf-8") as dest_file:
            dest_file.write(content)
        print(f"[prep.py] Created {reflection_dest}")
