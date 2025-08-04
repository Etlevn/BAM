"""
JSON extraction utilities for LLM Trading Analysis project.
Extracted from ord.py to improve code organization.
"""

import json
import re
import ast

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
    # First try to find JSON blocks with regex for better string handling
    import re
    
    # Pattern to match JSON objects with proper string handling
    json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(json_pattern, text)
    
    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue
    
    # Fallback to brace counting method
    brace_stack = []
    start = None
    in_string = False
    escape_next = False

    for i, char in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        
            
        if char == '\\':
            escape_next = True
            continue
            
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
            
        if not in_string:
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

def try_get_valid_json(prompt_text, contents, max_attempts=3, model_name="gpt-4o"):
    """
    Tries to get a valid JSON response from the LLM.
    Includes retry logic for structured failure detection.
    Returns response_json or fallback raw_response.
    """
    # Import here to avoid circular import
    from ord import chat_with_llm
    
    for attempt in range(1, max_attempts + 1):
        print(f"[utils.py] Requesting response (attempt {attempt}/3)...")
        response_text = chat_with_llm(prompt_text, model_name)

        response_json = extract_json(response_text)
        if response_json is not None:
            print(f"[utils.py] JSON parsed successfully on attempt {attempt}.")
            return response_json
        else:
            print(f"[utils.py] Attempt {attempt} failed to parse JSON.")

    # All retries failed, return final raw response
    print(f"[utils.py] All attempts failed. Saving raw response.")
    return {"raw_response": response_text}

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
        # Case 2a: Normal detection - only pause if llm_response is explicitly None
        if "llm_response" in response_json and response_json["llm_response"] is None:
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
                if isinstance(inner, dict) and "llm_response" in inner and inner["llm_response"] is None:
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
                if isinstance(literal, dict) and "llm_response" in literal and literal["llm_response"] is None:
                    print(f"\n[CRITICAL] NULL RESPONSE DETECTED (literal)")
                    print(f"Agent: {llm_id} | Round: {round_num}")
                    print("Likely cause: Parrot job failed and returned `None` via literal dict.")
                    input("Press Enter when ready to retry...\n")
                    return True
            except Exception:
                pass

    return False 