import json
import os
import re
import ast

import init
import prompt

from dotenv import load_dotenv
load_dotenv()
from edsl import Model, QuestionFreeText, Survey

def chat_with_parrot(prompt, model_name="gpt-4o"):
    """
    Sends a prompt to Expected Parrot via EDSL Model interface.
    """
    try:
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

def run_experiment_round(exp_run_dir, round_num, num_llms, total_rounds, mode, model_name="gpt-4o"):
    """
    Runs a single round of the experiment:
    - Reads input files from `exp/[timestamp]/input/rX/` (or `init/r0/` for round 1)
    - Loads experiment prompt and conditions from `init/prompt/`
    - Calls the LLM API to simulate agent trading
    - Saves results to `exp/[timestamp]/output/rX/`
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
            response_text = chat_with_parrot(prompt_text, model_name).strip()
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
            response_json = try_get_valid_json(prompt_text, contents, model_name=model_name)
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
                    response_json = try_get_valid_json(prompt_text, contents, model_name=model_name)
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
        response_json = ensure_valid_orders(response_json, prompt_text, limit_price_min, limit_price_max, max_quantity, model_name=model_name)

        # Save result JSON file
        exp_output_dir = os.path.join(exp_run_dir, "output", f"r{round_num}")
        os.makedirs(exp_output_dir, exist_ok=True)
        output_filename = os.path.join(exp_output_dir, f"{llm_id}_r{round_num}.json")

        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(response_json, f, indent=4)

        print(f"[{mode}] Response for {llm_id} in round {round_num} saved to {output_filename}")

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
        return file.read()

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

def validate_orders(submitted_orders, limit_price_min, limit_price_max, max_quantity):
    """
    Validates submitted orders. Returns True if all orders are valid.
    Valid orders must:
      - Be a list
      - Each order must have quantity > 0 and <= max_quantity
      - Each order's limit_price must lie within [limit_price_min, limit_price_max]
    """
    if not isinstance(submitted_orders, list):
        return False

    for order in submitted_orders:
        quantity = order.get("quantity", 0)
        price = order.get("limit_price", 0)

        if not isinstance(quantity, int) or not isinstance(price, (int, float)):
            return False
        if quantity <= 0 or quantity > max_quantity:
            return False
        if not (limit_price_min <= price <= limit_price_max):
            return False

    return True

def attempt_valid_orders(prompt_text, limit_price_min, limit_price_max, max_quantity=5, max_retries=3, model_name="gpt-4o"):
    """
    Tries up to `max_retries` times to get a valid order JSON using the given prompt.
    Returns response_json (parsed or clipped if necessary), and whether it was clipped.
    """
    response_json = None
    for attempt in range(1, max_retries + 1):
        print(f"[ord.py] Retrying for valid orders (attempt {attempt})...")
        response_text = chat_with_parrot(prompt_text, model_name)
        try:
            cleaned_text = re.sub(r"```json\s*|\s*```", "", response_text.strip(), flags=re.IGNORECASE)
            response_json = json.loads(cleaned_text)
            if validate_orders(response_json.get("submitted_orders", []), limit_price_min, limit_price_max, max_quantity):
                print(f"[ord.py] Valid orders received on retry attempt {attempt}.")
                return response_json, False
            else:
                print(f"[ord.py] Retry {attempt} returned invalid orders.")
        except json.JSONDecodeError:
            print(f"[ord.py] Retry {attempt} failed to parse JSON.")
    # After retries, clip
    print(f"[ord.py] Orders remain invalid after retries. Clipping to boundary.")
    if not isinstance(response_json, dict):
        return {"raw_response": response_text}, False

    fixed_orders = []
    for order in response_json.get("submitted_orders", []):
        order_type = order.get("order_type", "")
        quantity = order.get("quantity", 0)
        price = order.get("limit_price", 0)
        valid_quantity = min(max(1, int(quantity)), max_quantity)
        valid_price = min(max(limit_price_min, int(price)), limit_price_max)
        fixed_orders.append({
            "order_type": order_type,
            "quantity": valid_quantity,
            "limit_price": valid_price
        })
    response_json["submitted_orders"] = fixed_orders
    return response_json, True

def try_get_valid_json(prompt_text, contents, max_attempts=3, model_name="gpt-4o"):
    """
    Tries to get a valid JSON response from the LLM.
    Includes retry logic for structured failure detection.
    Returns response_json or fallback raw_response.
    """
    for attempt in range(1, max_attempts + 1):
        print(f"[ord.py] Requesting response (attempt {attempt}/3)...")
        response_text = chat_with_parrot(prompt_text, model_name)

        response_json = extract_json(response_text)
        if response_json is not None:
            print(f"[ord.py] JSON parsed successfully on attempt {attempt}.")
            return response_json
        else:
            print(f"[ord.py] Attempt {attempt} failed to parse JSON.")

    # All retries failed, return final raw response
    print(f"[ord.py] All attempts failed. Saving raw response.")
    return {"raw_response": response_text}

def ensure_valid_orders(response_json, prompt_text, limit_price_min, limit_price_max, max_quantity=5, model_name="gpt-4o"):
    """
    Ensures that the submitted_orders field contains valid orders.
    If invalid, retry LLM response; if still invalid, clip to boundary.
    Returns a corrected response_json.
    """
    if "raw_response" in response_json:
        return response_json  # Do not process raw_response fallback

    if validate_orders(response_json.get("submitted_orders", []), limit_price_min, limit_price_max, max_quantity):
        return response_json  # Already valid

    print(f"[ord.py] Orders invalid. Retrying to get valid orders...")
    response_json, was_clipped = attempt_valid_orders(prompt_text, limit_price_min, limit_price_max, max_quantity, model_name=model_name)
    return response_json

def extract_json(response_text):
    """
    Attempts to parse the response_text into JSON or Python literal format.
    Falls back to extracting a JSON block if full parse fails.
    """
    cleaned_text = re.sub(r"```json\s*|\s*```", "", response_text.strip(), flags=re.IGNORECASE)
    # Try standard JSON
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError:
        # Try Python literal (single-quoted dict)
        try:
            literal = ast.literal_eval(cleaned_text)
            if isinstance(literal, dict):
                return literal
        except Exception:
            pass
        print(f"[extract_json] Failed to parse full JSON or literal. Trying block fallback...")
        return extract_json_block(response_text)

def extract_json_block(text):
    """
    Attempts to extract the first valid JSON object from a larger text block.
    Useful when LLM returns explanation before or after the JSON.
    """
    brace_stack = []
    start = None

    for i, char in enumerate(text):
        if char == '{':
            if not brace_stack:
                start = i
            brace_stack.append('{')
        elif char == '}':
            if brace_stack:
                brace_stack.pop()
                if not brace_stack and start is not None:
                    json_candidate = text[start:i+1]
                    try:
                        return json.loads(json_candidate)
                    except json.JSONDecodeError as e:
                        print(f"[extract_json_block] Skipping invalid block: {e}")
                        continue

    print("[extract_json_block] No valid JSON block found.")
    return None

def pause_on_null_response(llm_id, round_num, response_json):
    """
    Detects if the response is a null response, even if it appears inside a stringified JSON in 'raw_response'.
    Pauses execution for user intervention.
    """
    # Case 1: Direct string match (already handled)
    if isinstance(response_json, str):
        if response_json.strip() in ('"{\\"llm_response\\": null}"', '\'{"llm_response": null}\''):
            pass  # handled below by JSON parse

    # Case 2: Standard dictionary with llm_response: None
    if isinstance(response_json, dict):
        # Case 2a: Normal detection
        if response_json.get("llm_response") is None:
            print(f"\n[CRITICAL] NULL RESPONSE DETECTED")
            print(f"Agent: {llm_id} | Round: {round_num}")
            print("Likely cause: Parrot job failed and returned `null` response.")
            input("Press Enter when ready to retry...\n")
            return True

        # Case 2b: Embedded stringified JSON inside raw_response
        if "raw_response" in response_json and isinstance(response_json["raw_response"], str):
            try:
                # Try parsing the embedded string
                inner = json.loads(response_json["raw_response"])
                if isinstance(inner, dict) and inner.get("llm_response") is None:
                    print(f"\n[CRITICAL] NULL RESPONSE DETECTED (stringified)")
                    print(f"Agent: {llm_id} | Round: {round_num}")
                    print("Likely cause: Parrot job failed and returned `null` inside stringified JSON.")
                    input("Press Enter when ready to retry...\n")
                    return True
            except Exception:
                pass  # If string is not valid JSON, skip

        # Case 2c: raw_response string is literal Python dict with None
        if "raw_response" in response_json and isinstance(response_json["raw_response"], str):
            raw_str = response_json["raw_response"]
            try:
                literal = ast.literal_eval(raw_str)
                if isinstance(literal, dict) and literal.get("llm_response") is None:
                    print(f"\n[CRITICAL] NULL RESPONSE DETECTED (literal)")
                    print(f"Agent: {llm_id} | Round: {round_num}")
                    print("Likely cause: Parrot job failed and returned `None` via literal dict.")
                    input("Press Enter when ready to retry...\n")
                    return True
            except Exception:
                pass

    return False

