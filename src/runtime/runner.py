"""Experiment run loop (logic extracted from main.py)."""

from __future__ import annotations

import os

import config
from src.agents import battle as battle_mod
from src.agents import trading
from src.market import clearing, orders
from src.portfolio import prepare, settle
from src.runtime import paths, runconfig, setup
from src.support import collect, repair


def _write_session_config(exp_run_dir: str, model_name, battle_manager, num_llms: int) -> str | None:
    """Write unified config.json (sgl/br isomorphic) with status=running."""
    if config.EXPERIMENT_MODE == "br":
        print("[runner] Battle Royale mode enabled")
        print(
            f"[runner] Assignment strategy: "
            f"{battle_manager.model_config['assignment_strategy']}"
        )
        if battle_manager.model_config.get("seed"):
            print(f"[runner] Random seed: {battle_manager.model_config['seed']}")
        data = runconfig.build_br_session_config(battle_manager)
        path = runconfig.write_session_config(exp_run_dir, data)
        print(f"[runner] Session config saved to: {path}")
        print("\n[runner] Model Assignment Summary:")
        battle_manager.print_assignment_summary()
        return model_name

    if config.EXPERIMENT_MODE == "sgl":
        if model_name is None:
            model_name = config.SINGLE_MODEL_CONFIG["model_name"]
        print(f"[runner] Single model mode enabled, using model: {model_name}")
        data = runconfig.build_sgl_session_config(
            num_llms,
            model_name,
            config.SINGLE_MODEL_CONFIG.get("service_name", ""),
        )
        path = runconfig.write_session_config(exp_run_dir, data)
        print(f"[runner] Session config saved to: {path}")
        return model_name

    raise ValueError(f"Invalid EXPERIMENT_MODE: {config.EXPERIMENT_MODE}")


def run_experiment(
    mode="main",
    model_name=None,
    battle_manager=None,
    num_llms=None,
    exp_run_dir=None,
):
    """
    Run practice or main experiment rounds inside an existing session directory.

    Args:
        mode: "main" or "prac"
        model_name: Model name (single-model mode)
        battle_manager: Battle Royale manager (optional)
        num_llms: Agent count (defaults to paths.get_llm_count())
        exp_run_dir: Session timestamp directory (required)
    """
    if exp_run_dir is None:
        raise ValueError("exp_run_dir is required (create the session once in start())")

    if num_llms is None:
        num_llms = paths.get_llm_count()

    work_dir = config.BASE_DIR
    experiment_config = setup.get_experiment_config()
    total_rounds = (
        experiment_config["practice_rounds"]
        if mode == "prac"
        else experiment_config["total_rounds"]
    )

    if total_rounds == 0:
        print(f"[runner] Skipping {mode} experiment: 0 rounds configured.")
        return

    if mode == "prac":
        io_root = setup.ensure_prac_dirs(exp_run_dir)
        print(f"[runner] Practice I/O root: {io_root}")
        require_reflections = False
    elif mode == "main":
        io_root = setup.ensure_io_dirs(exp_run_dir, init_mkt=True)
        print(f"[runner] Formal I/O root: {io_root}")
        practice_rounds = int(experiment_config.get("practice_rounds", 0) or 0)
        require_reflections = practice_rounds > 0
    else:
        raise ValueError(f"Unsupported run mode: {mode!r}")

    if config.EXPERIMENT_MODE == "sgl" and model_name is None:
        model_name = config.SINGLE_MODEL_CONFIG["model_name"]

    print(f"[runner] Preparing Round 0 market & portfolio files for {mode}...")
    prepare.prepare_round_zero(
        num_llms,
        total_rounds,
        mode=mode,
        io_root=io_root,
        require_reflections=require_reflections,
    )

    for round_num in range(1, total_rounds + 1):
        print(f"\n=== {mode.upper()} ROUND {round_num} ===")

        if battle_manager:
            trading.run_experiment_round(
                io_root,
                round_num,
                num_llms,
                total_rounds,
                mode=mode,
                model_name=model_name,
                battle_manager=battle_manager,
            )
        else:
            trading.run_experiment_round(
                io_root,
                round_num,
                num_llms,
                total_rounds,
                mode=mode,
                model_name=model_name,
            )

        if config.AUTO_JSON_FIX["enabled"]:
            fix_results = repair.post_round_json_fix(
                io_root,
                round_num,
                num_llms,
                create_backup=config.AUTO_JSON_FIX.get("create_backup", True),
            )
            if fix_results.get("fixed_files", 0) > 0:
                print(
                    f"[runner] Fixed {fix_results['fixed_files']} JSON files "
                    f"in round {round_num}"
                )

        orders.prepare_next_round(work_dir, io_root, round_num, num_llms)
        clearing.compute_market_price(io_root, round_num)
        settle.compute_market_and_portfolio_all(
            work_dir, io_root, round_num, num_llms, total_rounds
        )

        if config.API_CONFIG.get("api_mode") == "expected_parrot":
            try:
                collect.collect_ep_html_files(work_dir)
            except Exception as e:
                print(f"[runner] Warning: Failed to collect HTML files: {e}")

    if mode == "prac":
        reflection_round = total_rounds + 1
        reflection_out_dir = os.path.join(exp_run_dir, "input", "r0")
        os.makedirs(reflection_out_dir, exist_ok=True)
        print("\n[runner] Running reflection step after practice rounds...")
        print(f"[runner] Writing reflections to {reflection_out_dir}")
        if battle_manager:
            trading.run_experiment_round(
                io_root,
                reflection_round,
                num_llms,
                total_rounds,
                mode="refl",
                model_name=model_name,
                battle_manager=battle_manager,
                reflection_out_dir=reflection_out_dir,
            )
        else:
            trading.run_experiment_round(
                io_root,
                reflection_round,
                num_llms,
                total_rounds,
                mode="refl",
                model_name=model_name,
                reflection_out_dir=reflection_out_dir,
            )


def start() -> None:
    """CLI entry: one session dir, optional practice under prac/, then formal rounds."""
    from src.runtime.api import ensure_api_ready

    ensure_api_ready()

    work_dir = config.BASE_DIR
    num_llms = paths.get_llm_count()
    experiment_config = setup.get_experiment_config()

    # Read-only prompt templates under prompt/ at repo root.
    setup.PROMPT_DIR = os.path.join(work_dir, "prompt")

    experiment_start_path = paths.get_prompt_file_path(
        "experiment_start", setup.PROMPT_DIR
    )
    order_forecast_end_path = paths.get_prompt_file_path(
        "order_forecast_end", setup.PROMPT_DIR
    )
    mode_str = "BAS" if config.USE_BAS_MODE else "Normal"
    print(f"\n[runner] Prompt Configuration ({mode_str} mode):")
    print(f"[runner] experiment_start: {os.path.basename(experiment_start_path)}")
    print(f"[runner] order_forecast_end: {os.path.basename(order_forecast_end_path)}")
    if config.USE_BAS_MODE:
        print(f"[runner] BAS_BIAS_ID: {config.BAS_BIAS_ID}")

    battle_manager = None
    model_name = None
    if config.EXPERIMENT_MODE == "br":
        print("\n[runner] Initializing Battle Royale mode...")
        if "custom_models" in config.BATTLE_ROYALE_CONFIG:
            print("[runner] Using custom model configuration")
            br_config = battle_mod.create_battle_royale_config(
                total_agents=num_llms,
                models=config.BATTLE_ROYALE_CONFIG["custom_models"],
                assignment_strategy=config.BATTLE_ROYALE_CONFIG["assignment_strategy"],
            )
        else:
            print("[runner] Using default model configuration")
            br_config = battle_mod.create_battle_royale_config(
                total_agents=num_llms,
                assignment_strategy=config.BATTLE_ROYALE_CONFIG["assignment_strategy"],
            )
        battle_manager = battle_mod.BattleRoyaleManager(br_config)
        print(f"[runner] Battle Royale initialized with {num_llms} agents")
    elif config.EXPERIMENT_MODE == "sgl":
        model_name = config.SINGLE_MODEL_CONFIG["model_name"]
        print(f"\n[runner] Single model mode enabled, using model: {model_name}")
    else:
        raise ValueError(
            f"Invalid EXPERIMENT_MODE: {config.EXPERIMENT_MODE}. Must be 'br' or 'sgl'"
        )

    exp_run_dir = setup.initialize_experiment(work_dir)
    print(f"[runner] Session directory: {exp_run_dir}")
    _write_session_config(exp_run_dir, model_name, battle_manager, num_llms)

    practice_rounds = int(experiment_config.get("practice_rounds", 0) or 0)
    try:
        if practice_rounds > 0:
            run_experiment(
                mode="prac",
                model_name=model_name,
                battle_manager=battle_manager,
                num_llms=num_llms,
                exp_run_dir=exp_run_dir,
            )

        run_experiment(
            mode="main",
            model_name=model_name,
            battle_manager=battle_manager,
            num_llms=num_llms,
            exp_run_dir=exp_run_dir,
        )
    finally:
        try:
            status = runconfig.update_status(exp_run_dir)
            print(f"[runner] Session status → {status}")
        except Exception as e:
            print(f"[runner] Warning: failed to update session status: {e}")
