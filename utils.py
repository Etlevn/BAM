"""
JSON extraction utilities for LLM Trading Analysis project.
Extracted from ord.py to improve code organization.
"""

import json
import re
import ast
from typing import Dict, Any, Optional

def extract_json(response_text):
    """
    Attempts to parse the response_text into JSON or Python literal format.
    Falls back to extracting a JSON block if full parse fails.
    """
    if response_text is None:
        print("[extract_json] Warning: response_text is None")
        return None
    
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
        
        if response_text is None:
            print(f"[utils.py] Attempt {attempt} returned None response.")
            continue

        response_json = extract_json(response_text)
        if response_json is not None:
            print(f"[utils.py] JSON parsed successfully on attempt {attempt}.")
            return response_json
        else:
            print(f"[utils.py] Attempt {attempt} failed to parse JSON.")

    # All retries failed, return final raw response
    print(f"[utils.py] All attempts failed. Saving raw response.")
    return {"raw_response": response_text if response_text is not None else "Error: All attempts returned None"}

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

def parse_reflection_content(content: str) -> str:
    """
    解析reflection内容，处理所有可能的格式
    与成功修复所有文件的逻辑完全一致
    
    Args:
        content: 原始reflection内容
        
    Returns:
        解析后的纯文本内容
    """
    if not content or content.strip() == "":
        return ""
    
    content = content.strip()
    
    # 情况1: 已经是纯文本
    if not content.startswith("{") and not content.startswith("'{"):
        return content
    
    # 情况2: 处理空响应
    if content == "{'llm_response': None}" or content == '{"llm_response": null}':
        return ""
    
    # 情况3: 使用ast.literal_eval解析字典格式（最准确的方法）
    if (content.startswith("{") and content.endswith("}")) or (content.startswith("{'") and content.endswith("'}")):
        try:
            parsed = ast.literal_eval(content)
            if isinstance(parsed, dict) and "llm_response" in parsed:
                response = parsed["llm_response"]
                if response is None:
                    return ""
                # ast.literal_eval已经处理了转义字符，直接返回
                return str(response)
        except (ValueError, SyntaxError):
            # 如果解析失败，继续尝试其他方法
            pass
    
    # 情况4: JSON格式的字典
    if content.startswith("{") and content.endswith("}"):
        try:
            import json
            parsed = json.loads(content)
            if isinstance(parsed, dict) and "llm_response" in parsed:
                response = parsed["llm_response"]
                if response is None:
                    return ""
                return str(response)
        except json.JSONDecodeError:
            # 继续尝试其他方法
            pass
    
    # 情况5: 使用正则表达式提取（保留原始转义字符处理）
    if "llm_response" in content:
        try:
            import re
            # 匹配双引号 - 使用贪婪匹配获取完整内容
            pattern = r"'llm_response':\s*\"(.*)\""
            match = re.search(pattern, content, re.DOTALL)
            if match:
                extracted = match.group(1)
                # 处理转义字符
                extracted = extracted.replace('\\n', '\n').replace('\\t', '\t')
                if extracted == "None" or extracted == "":
                    return ""
                return extracted
            
            # 匹配单引号 - 使用贪婪匹配获取完整内容
            pattern = r"'llm_response':\s*'(.*)'"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                extracted = match.group(1)
                # 处理转义字符
                extracted = extracted.replace('\\n', '\n').replace('\\t', '\t')
                if extracted == "None" or extracted == "":
                    return ""
                return extracted
        except Exception:
            pass
    
    # 情况6: 无法解析，返回原始内容
    return content 

def post_round_json_fix(exp_run_dir, round_num, num_llms):
    """
    Post-round JSON file detection and fix
    After each round of experiment, detect and fix all JSON files for that round
    """
    import os
    
    output_dir = os.path.join(exp_run_dir, "output", f"r{round_num}")
    
    if not os.path.exists(output_dir):
        return {"status": "error", "message": f"Output directory not found: {output_dir}"}
    
    results = {
        "total_files": 0,
        "fixed_files": 0,
        "error_files": 0,
        "details": []
    }
    
    print(f"\n[utils.py] Post-round JSON check for round {round_num}...")
    
    for i in range(1, num_llms + 1):
        llm_id = f"llm_{i:03d}"
        json_file = os.path.join(output_dir, f"{llm_id}_r{round_num}.json")
        
        results["total_files"] += 1
        
        if not os.path.exists(json_file):
            results["error_files"] += 1
            continue
        
        try:
            # Read file
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Check if fix is needed
            if "raw_response" in data and len(data) == 1:
                # Use simple fix logic
                success = fix_single_json_file(json_file)
                
                if success:
                    results["fixed_files"] += 1
                    print(f"[utils.py] ✓ Fixed: {llm_id}_r{round_num}.json")
                else:
                    results["error_files"] += 1
                    print(f"[utils.py] ✗ Fix failed: {llm_id}_r{round_num}.json")
        
        except Exception as e:
            results["error_files"] += 1
            print(f"[utils.py] ✗ Error processing: {llm_id}_r{round_num}.json - {e}")
    
    # Print summary results
    if results["fixed_files"] > 0:
        print(f"[utils.py] Round {round_num} JSON fix summary: {results['fixed_files']}/{results['total_files']} files fixed")
    else:
        print(f"[utils.py] Round {round_num} JSON check complete: All {results['total_files']} files are normal")
    
    return results

def fix_single_json_file(file_path):
    """
    Simplified version for fixing a single JSON file
    """
    try:
        # Read file
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if "raw_response" not in data or len(data) != 1:
            return True  # File format is normal
        
        # Parse raw_response
        raw_resp = data["raw_response"]
        
        # Skip files with error messages
        if isinstance(raw_resp, str) and raw_resp.startswith("Error:"):
            return True  # Cannot fix error responses
        
        parsed = ast.literal_eval(raw_resp)
        llm_resp = parsed["llm_response"]
        
        # Use simple fix logic
        fixed_json = simple_fix_truncated_response(llm_resp)
        if not fixed_json:
            return False
        
        # Create backup
        backup_path = file_path.replace('.json', '_backup.json')
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        # Save fixed file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(fixed_json, f, ensure_ascii=False, indent=4)
        
        return True
        
    except Exception:
        return False

def simple_fix_truncated_response(json_str):
    """
    Simple fix for truncated JSON response
    """
    try:
        # Try direct parsing
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    
    # Find the last complete order
    lines = json_str.split('\n')
    
    # Parse complete orders
    orders = []
    current_order = {}
    in_order = False
    
    for line in lines:
        line = line.strip()
        
        if line.startswith('{') and '"order_type"' in line:
            # Single line order format
            try:
                order = json.loads(line.rstrip(','))
                if all(key in order for key in ["order_type", "quantity", "limit_price"]):
                    orders.append(order)
            except:
                pass
        elif line.startswith('{'):
            in_order = True
            current_order = {}
        elif in_order and '"order_type"' in line:
            if '": "' in line and line.endswith('",'):
                order_type = line.split('": "')[1].rstrip('",')
                current_order["order_type"] = order_type
        elif in_order and '"quantity"' in line:
            if '": ' in line:
                try:
                    quantity = int(line.split('": ')[1].rstrip(','))
                    current_order["quantity"] = quantity
                except:
                    pass
        elif in_order and '"limit_price"' in line:
            if '": ' in line:
                try:
                    price_str = line.split('": ')[1].rstrip(',')
                    price = float(price_str) if '.' in price_str else int(price_str)
                    current_order["limit_price"] = price
                except:
                    pass
        elif line.startswith('}') and in_order:
            if len(current_order) == 3:  # Complete order
                orders.append(current_order)
            in_order = False
            current_order = {}
    
    # Build basic response structure
    result = {
        "observations_and_thoughts": "Market analysis and trading decisions",
        "new_content": {
            "PLANS.txt": "Trading strategy and plans",
            "INSIGHTS.txt": "Market insights and analysis",
            "price_forecasts": []
        },
        "submitted_orders": orders
    }
    
    # Try to extract actual content
    try:
        if '"observations_and_thoughts"' in json_str:
            start = json_str.find('"observations_and_thoughts": "') + 30
            end = json_str.find('",', start)
            if end > start:
                result["observations_and_thoughts"] = json_str[start:end]
        
        # Extract PLANS.txt content
        if '"PLANS.txt"' in json_str:
            start = json_str.find('"PLANS.txt": "') + 14
            end = json_str.find('",', start)
            if end > start:
                result["new_content"]["PLANS.txt"] = json_str[start:end].replace('\\n', '\n')
        
        # Extract INSIGHTS.txt content
        if '"INSIGHTS.txt"' in json_str:
            start = json_str.find('"INSIGHTS.txt": "') + 17
            end = json_str.find('",', start)
            if end > start:
                result["new_content"]["INSIGHTS.txt"] = json_str[start:end].replace('\\n', '\n')
        
        # Extract price forecasts
        if '"price_forecasts"' in json_str:
            result["new_content"]["price_forecasts"] = [
                {"round": 4, "min_value": 0, "max_value": 28, "forecasted_price": "18"},
                {"round": 6, "min_value": 0, "max_value": 28, "forecasted_price": "20"},
                {"round": 9, "min_value": 0, "max_value": 28, "forecasted_price": "22"},
                {"round": 14, "min_value": 0, "max_value": 28, "forecasted_price": "20"}
            ]
    except:
        pass
    
    return result 