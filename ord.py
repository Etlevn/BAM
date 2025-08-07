import json
import os
import re
import ast

import init
import prompt
import utils
import valid
import config

from dotenv import load_dotenv
load_dotenv()
from edsl import Model, QuestionFreeText, Survey

def chat_with_llm(prompt, model_name="gpt-4o"):
    """
    Unified function to call LLM API based on configuration.
    Supports both Expected Parrot and OpenAI APIs.
    """
    api_mode = config.API_CONFIG["api_mode"]
    
    if api_mode == "expected_parrot":
        return chat_with_parrot(prompt, model_name)
    elif api_mode == "openai":
        return chat_with_openai(prompt, model_name)
    else:
        raise ValueError(f"Unknown API mode: {api_mode}")

def chat_with_parrot(prompt, model_name="gpt-4o"):
    """
    Sends a prompt to Expected Parrot via EDSL Model interface.
    """
    try:
        # Set Expected Parrot API key from config
        import os
        ep_api_key = config.API_CONFIG["expected_parrot_api_key"]
        if ep_api_key:
            os.environ["EXPECTED_PARROT_API_KEY"] = ep_api_key
        
        model = Model(model_name)
        question = QuestionFreeText(
            question_name="llm_response",
            question_text=prompt
        )
        survey = Survey(questions=[question])
        results = survey.by(model).run()
        return str(results[0].answer)
    except Exception as e:
        return f"Error: {e}"

def chat_with_openai(prompt, model_name="gpt-4o"):
    """
    Sends a request to OpenAI's model and returns the response.
    """
    try:
        import openai
        api_key = config.API_CONFIG["openai_api_key"]
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {e}"

def run_experiment_round(exp_run_dir, round_num, num_llms, total_rounds, mode, model_name="gpt-4o", battle_manager=None):
    """
    Runs a single round of the experiment:
    - Reads input files from `exp/[timestamp]/input/rX/` (or `init/r0/` for round 1)
    - Loads experiment prompt and conditions from `init/prompt/`
    - Calls the LLM API to simulate agent trading
    - Saves results to `exp/[timestamp]/output/rX/`
    
    Args:
        exp_run_dir: Experiment directory
        round_num: Current round number
        num_llms: Number of LLM agents
        total_rounds: Total number of rounds
        mode: Experiment mode ("main", "prac", "refl")
        model_name: Default model name (used when battle_manager is None)
        battle_manager: Battle Royale manager instance (optional)
    """

    # Load shared experiment prompts from the prompt directory
    experiment_start_content = read_file(os.path.join(init.INIT_PROMPT_DIR, "experiment_start.txt"))
    experiment_conditions_content = read_file(os.path.join(init.INIT_PROMPT_DIR, "experiment_conditions.json"))
    order_forecast_start_content = read_file(os.path.join(init.INIT_PROMPT_DIR, "order_forecast_start.txt"))
    order_forecast_end_content = read_file(os.path.join(init.INIT_PROMPT_DIR, "order_forecast_end.txt"))
    order_forecast_template_content = read_file(os.path.join(init.INIT_PROMPT_DIR, "order_forecast_template.json"))

    for i in range(1, num_llms + 1):
        llm_id = f"llm_{i:03d}"
        file_paths = generate_filenames(exp_run_dir, llm_id, round_num)

        # Get model for this agent (Battle Royale or default)
        if battle_manager:
            agent_model = battle_manager.get_model_for_agent(llm_id)
        else:
            agent_model = model_name
        
        # Print which model this agent is using
        print(f"[{mode}] Processing {llm_id} using model: {agent_model}")

        # Load prior-round input files
        plans_content = read_file(file_paths["plans"])
        insights_content = read_file(file_paths["insights"])
        reflection_content = read_file(file_paths["reflection"])
        market_content = read_file(file_paths["market"])
        portfolio_content = read_file(file_paths["portfolio"])

        # Extract last round's market price from mkt.csv for dynamic price range
        try:
            mkt_path = os.path.join(exp_run_dir, "output", f"r{round_num - 1}", "mkt.csv")
            with open(mkt_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                last_price_line = lines[-1]  # Assumes last line has latest price
                last_price = float(last_price_line.strip().split(",")[1])  # Assuming format: round,price
        except Exception:
            last_price = 14.0  # fallback for round 1 or missing file

        limit_price_min = max(1, int(last_price * 0.5))
        limit_price_max = int(last_price * 2.0)

        contents = {
            "experiment_start": experiment_start_content,
            "experiment_conditions": experiment_conditions_content,
            "order_forecast_start": order_forecast_start_content,
            "order_forecast_end": order_forecast_end_content,
            "order_forecast_template": order_forecast_template_content,
            "plans": plans_content,
            "insights": insights_content,
            "reflection": reflection_content,
            "market": market_content,
            "portfolio": portfolio_content
        }

        # Construct LLM prompt based on mode
        if mode == "main":
            prompt_text = prompt.build_prompt_main(file_paths, contents, round_num, total_rounds, limit_price_min, limit_price_max)
        elif mode == "prac":
            prompt_text = prompt.build_prompt_prac(file_paths, contents, round_num, total_rounds, limit_price_min, limit_price_max)
        elif mode == "refl":
            prompt_text = prompt.build_prompt_refl(file_paths, contents)
        else:
            raise ValueError(f"Unknown mode: {mode}")

        # Handle reflection separately (text only)
        if mode == "refl":
            response = chat_with_llm(prompt_text, agent_model)
            
            # Extract text content from response (handle both dict and string formats)
            if isinstance(response, dict) and "llm_response" in response:
                response_text = response["llm_response"]
            elif isinstance(response, str):
                response_text = response
            else:
                response_text = str(response)
            
            response_text = response_text.strip()
            
            reflection_dir = os.path.join(init.INIT_DIR, "prac")
            os.makedirs(reflection_dir, exist_ok=True)
            reflection_filename = os.path.join(reflection_dir, f"{llm_id}_r0_reflection.txt")
            with open(reflection_filename, "w", encoding="utf-8") as f:
                f.write(response_text)
            print(f"[refl] Saved {llm_id}'s reflection to {reflection_filename}")
            continue

        # === Main/prac mode: LLM returns JSON ===
        max_attempts = 3
        attempt = 1
        while attempt <= max_attempts:
            response_json = utils.try_get_valid_json(prompt_text, contents, model_name=agent_model)
            try:
                # Custom unwrapping logic for llm_response
                if isinstance(response_json, dict) and "llm_response" in response_json:
                    raw_response = response_json["llm_response"]
                    if isinstance(raw_response, str):
                        try:
                            inner = json.loads(raw_response)
                            if isinstance(inner, dict):
                                response_json = inner
                            else:
                                raise ValueError("llm_response is not a JSON object")
                        except Exception:
                            raise ValueError("Invalid JSON string in llm_response")
                    elif isinstance(raw_response, dict):
                        response_json = raw_response
                    else:
                        raise ValueError("llm_response is neither string nor dict")
                # Check for connection error pause
                while pause_on_connection_error(llm_id, round_num, response_json):
                    print(f"[ord.py] Retrying {llm_id} in round {round_num} after connection error...")
                    response_json = utils.try_get_valid_json(prompt_text, contents, model_name=agent_model)
                    # Re-apply unwrapping after retry
                    if isinstance(response_json, dict) and "llm_response" in response_json:
                        raw_response = response_json["llm_response"]
                        if isinstance(raw_response, str):
                            try:
                                inner = json.loads(raw_response)
                                if isinstance(inner, dict):
                                    response_json = inner
                                else:
                                    raise ValueError("llm_response is not a JSON object")
                            except Exception:
                                raise ValueError("Invalid JSON string in llm_response")
                        elif isinstance(raw_response, dict):
                            response_json = raw_response
                        else:
                            raise ValueError("llm_response is neither string nor dict")
                break  # Success, exit retry loop
            except ValueError as ve:
                print(f"\n[RETRY] Attempt {attempt}/3: Detected invalid JSON in 'llm_response' for {llm_id} in round {round_num}")
                if attempt < max_attempts:
                    print(f"[ord.py] Retrying {llm_id} (attempt {attempt + 1}/3) in round {round_num} after invalid response...")
                    attempt += 1
                    continue
                else:
                    # Save as raw_response if all attempts fail
                    response_json = {"raw_response": str(response_json)}
                    break
        max_quantity = 5
        response_json = valid.ensure_valid_orders(response_json, prompt_text, limit_price_min, limit_price_max, max_quantity, model_name=agent_model)

        # Save result JSON file
        exp_output_dir = os.path.join(exp_run_dir, "output", f"r{round_num}")
        os.makedirs(exp_output_dir, exist_ok=True)
        output_filename = os.path.join(exp_output_dir, f"{llm_id}_r{round_num}.json")

        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(response_json, f, indent=4)

        print(f"[{mode}] Response for {llm_id} in round {round_num} saved to {output_filename}")
        print()

def pause_on_job_failed(llm_id, round_num, response_text):
    """
    Detects if Expected Parrot job failed based on response text and pauses for manual retry.
    """
    if isinstance(response_text, str) and "Job failed." in response_text:
        print(f"\n[CRITICAL] PARROT JOB FAILURE DETECTED")
        print(f"Agent: {llm_id} | Round: {round_num}")
        print("Raw Response:", response_text[:500])  # preview only
        print("Program is now PAUSED due to Parrot job failure.")
        input("Press Enter when the issue is resolved to retry this agent...\n")
        return True
    return False

def pause_on_connection_error(llm_id, round_num, raw_response):
    """
    If a connection error is detected, pause and return True to indicate retry is needed.
    Otherwise, return False.
    """
    if "raw_response" in raw_response and "Error: Connection error." in raw_response["raw_response"]:
        print(f"\n[CRITICAL] LLM CONNECTION ERROR DETECTED")
        print(f"Agent: {llm_id} | Round: {round_num}")
        print("Raw Response:", raw_response["raw_response"])
        print("Program is now PAUSED. Please resolve the issue and press Enter to retry this agent...")
        input("Press Enter when ready to retry...\n")
        return True  # signal that we should retry
    return False

def read_file(file_path):
    """Reads a file and returns its content. If the file is missing, returns an empty string."""
    if not os.path.exists(file_path):
        print(f"Warning: {file_path} not found. Using empty content.")
        return ""
    
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()
    
    # 如果是reflection文件，自动解析格式
    if "reflection" in file_path:
        from utils import parse_reflection_content
        return parse_reflection_content(content)
    
    return content

def generate_filenames(exp_run_dir,llm_id, current_round):
    """
    Generates file paths for a given LLM.
    - If `current_round == 1`, read from `init/r0/`
    - If `current_round > 1`, read from `exp/[timestamp]/input/rX/`
    """
    previous_round = current_round - 1
    if current_round == 1:
        data_dir = init.INIT_R0_DIR  # Read from `init/r0/` in the first round
    else:
        data_dir = os.path.join(exp_run_dir, "input", f"r{previous_round}")  # Read from `exp/[timestamp]/input/rX/` in subsequent rounds

    return {
        "plans": os.path.join(data_dir, f"{llm_id}_r{previous_round}_plans.txt"),
        "insights": os.path.join(data_dir, f"{llm_id}_r{previous_round}_insights.txt"),
        "reflection": os.path.join(data_dir, f"{llm_id}_r{previous_round}_reflection.txt"),
        "market": os.path.join(data_dir, f"{llm_id}_r{previous_round}_market.txt"),
        "portfolio": os.path.join(data_dir, f"{llm_id}_r{previous_round}_portfolio.txt")
    }





