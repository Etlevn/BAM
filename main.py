import os
import init
import prep
import ord
import proc
import mkt
import pfl
import config
import br  # Battle Royale module

# === Experiment Configuration ===
WORK_DIR = config.BASE_DIR  # <-- Use config file
NUM_LLMs = config.MODEL_CONFIG["num_llms"]  # Number of LLM agents
MODEL_NAME = config.MODEL_CONFIG["model_name"]  # <-- Set desired model name here (e.g., "gpt-4", "claude-3-5-sonnet-20240620")

def run_experiment(mode="main", model_name=MODEL_NAME, battle_manager=None):
    """
    Unified function to run either prac or main experiment.
    Only difference lies in the prompt generation module (prac vs ord).
    
    Args:
        mode: "main", "prac", or "refl"
        model_name: Default model name (used when Battle Royale is disabled)
        battle_manager: Battle Royale manager instance (optional)
    """
    experiment_config = init.get_experiment_config()
    total_rounds = experiment_config["practice_rounds"] if mode == "prac" else experiment_config["total_rounds"]

    if total_rounds == 0:
        print(f"[main.py] Skipping {mode} experiment: 0 rounds configured.")
        return

    # Step 1: Create experiment directory
    exp_run_dir = init.initialize_experiment(WORK_DIR)
    print(f"[main.py] Initialized {mode} experiment at: {exp_run_dir}")

    # Step 2: Prepare Round 0 files
    print(f"[main.py] Preparing Round 0 market & portfolio files for {mode}...")
    prep.prepare_round_zero(NUM_LLMs,total_rounds, mode=mode)

    # Step 2.5: Initialize Battle Royale if enabled
    if battle_manager:
        print(f"[main.py] Battle Royale mode enabled")
        print(f"[main.py] Assignment strategy: {battle_manager.model_config['assignment_strategy']}")
        if battle_manager.model_config.get('seed'):
            print(f"[main.py] Random seed: {battle_manager.model_config['seed']}")
        
        # Save Battle Royale configuration
        br_config_file = os.path.join(exp_run_dir, "battle_royale_config.json")
        battle_manager.save_assignment(br_config_file)
        print(f"[main.py] Battle Royale config saved to: {br_config_file}")
        
        # Print model assignment summary
        print("\n[main.py] Model Assignment Summary:")
        battle_manager.print_assignment_summary()
    else:
        print(f"[main.py] Battle Royale mode disabled, using single model: {model_name}")

    for round_num in range(1, total_rounds + 1):
        print(f"\n=== {mode.upper()} ROUND {round_num} ===")

        # Step 3: Run LLM round using appropriate prompt module
        if battle_manager:
            # Battle Royale mode: pass battle_manager to ord
            ord.run_experiment_round(exp_run_dir, round_num, NUM_LLMs, total_rounds, mode=mode, model_name=model_name, battle_manager=battle_manager)
        else:
            # Single model mode: use default model_name
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
        if battle_manager:
            ord.run_experiment_round(exp_run_dir, reflection_round, NUM_LLMs, total_rounds, mode="refl", model_name=model_name, battle_manager=battle_manager)
        else:
            ord.run_experiment_round(exp_run_dir, reflection_round, NUM_LLMs, total_rounds, mode="refl", model_name=model_name)

if __name__ == "__main__":
    init.initialize_experiment(WORK_DIR)
    experiment_config = init.get_experiment_config()

    # Initialize Battle Royale if enabled
    battle_manager = None
    if config.BATTLE_ROYALE_CONFIG["enabled"]:
        print(f"\n[main.py] Initializing Battle Royale mode...")
        
        # Check if custom models are configured
        if "custom_models" in config.BATTLE_ROYALE_CONFIG:
            print(f"[main.py] Using custom model configuration")
            # Create Battle Royale configuration with custom models
            br_config = br.create_battle_royale_config(
                total_agents=NUM_LLMs,
                models=config.BATTLE_ROYALE_CONFIG["custom_models"],
                assignment_strategy=config.BATTLE_ROYALE_CONFIG["assignment_strategy"],
                seed=config.BATTLE_ROYALE_CONFIG["seed"]
            )
        else:
            print(f"[main.py] Using default model configuration")
            # Create Battle Royale configuration with default models
            br_config = br.create_battle_royale_config(
                total_agents=NUM_LLMs,
                assignment_strategy=config.BATTLE_ROYALE_CONFIG["assignment_strategy"],
                seed=config.BATTLE_ROYALE_CONFIG["seed"]
            )
        
        # Create Battle Royale manager
        battle_manager = br.BattleRoyaleManager(br_config)
        print(f"[main.py] Battle Royale initialized with {NUM_LLMs} agents")
    else:
        print(f"\n[main.py] Battle Royale mode disabled, using single model: {MODEL_NAME}")

    # Optional: Run practice rounds
    if experiment_config.get("practice_rounds", 0) > 0:
        run_experiment(mode="prac", model_name=MODEL_NAME, battle_manager=battle_manager)

    # Always run main rounds
    run_experiment(mode="main", model_name=MODEL_NAME, battle_manager=battle_manager)