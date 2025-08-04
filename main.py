import init
import prep
import ord
import proc
import mkt
import pfl

# === Experiment Configuration ===
WORK_DIR = "/Users/etlevn/Documents/PycharmProjects/LLM_Trd"  # <-- Set your base working directory here
NUM_LLMs = 20  # Number of LLM agents
MODEL_NAME = "gpt-4o"  # <-- Set desired model name here (e.g., "gpt-4", "claude-3-5-sonnet-20240620")

def run_experiment(mode="main", model_name=MODEL_NAME):
    """
    Unified function to run either prac or main experiment.
    Only difference lies in the prompt generation module (prac vs ord).
    """
    config = init.get_experiment_config()
    total_rounds = config["practice_rounds"] if mode == "prac" else config["total_rounds"]

    if total_rounds == 0:
        print(f"[main.py] Skipping {mode} experiment: 0 rounds configured.")
        return

    # Step 1: Create experiment directory
    exp_run_dir = init.initialize_experiment(WORK_DIR)
    print(f"[main.py] Initialized {mode} experiment at: {exp_run_dir}")

    # Step 2: Prepare Round 0 files
    print(f"[main.py] Preparing Round 0 market & portfolio files for {mode}...")
    prep.prepare_round_zero(NUM_LLMs,total_rounds, mode=mode)

    for round_num in range(1, total_rounds + 1):
        print(f"\n=== {mode.upper()} ROUND {round_num} ===")

        # Step 3: Run LLM round using appropriate prompt module
        ord.run_experiment_round(exp_run_dir, round_num, NUM_LLMs, total_rounds, mode=mode, model_name=model_name)

        # Step 4: Process output and update order book
        proc.prepare_next_round(WORK_DIR, exp_run_dir, round_num, NUM_LLMs)

        # Step 5: Market price clearing
        mkt.compute_market_price(exp_run_dir, round_num)

        # Step 6: Portfolio + market text file generation
        pfl.compute_market_and_portfolio_all(WORK_DIR, exp_run_dir, round_num, NUM_LLMs, total_rounds)

    # Step 7: After all prac rounds, run reflection prompt
    if mode == "prac":
        reflection_round = total_rounds + 1
        print(f"\n[main.py] Running reflection step after practice rounds...")
        ord.run_experiment_round(exp_run_dir, reflection_round, NUM_LLMs, total_rounds, mode="refl", model_name=model_name)

if __name__ == "__main__":
    init.initialize_experiment(WORK_DIR)
    config = init.get_experiment_config()

    # Optional: Run practice rounds
    if config.get("practice_rounds", 0) > 0:
        run_experiment(mode="prac", model_name=MODEL_NAME)

    # Always run main rounds
    run_experiment(mode="main", model_name=MODEL_NAME)