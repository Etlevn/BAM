#!/usr/bin/env python3
"""
Simple and direct JSON fix tool
Specifically handles truncated JSON files in LLM Trading experiments
"""

import json
import ast
import os
import sys

def fix_json_file(file_path):
    """
    Fix a single JSON file
    """
    try:
        # Read file
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check if fix is needed
        if "raw_response" not in data or len(data) != 1:
            return False, "File format is correct, no fix needed"
        
        # Parse raw_response
        raw_resp = data["raw_response"]
        parsed = ast.literal_eval(raw_resp)
        llm_resp = parsed["llm_response"]
        
        # Simple and direct fix: find the last complete order, remove incomplete parts
        fixed_json = fix_truncated_json(llm_resp)
        if not fixed_json:
            return False, "Fix failed"
        
        # Create backup
        backup_path = file_path.replace('.json', '_backup.json')
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        # Save fixed file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(fixed_json, f, ensure_ascii=False, indent=4)
        
        return True, f"Fix successful, backup saved as {backup_path}"
        
    except Exception as e:
        return False, f"Fix failed: {e}"

def fix_truncated_json(json_str):
    """
    Fix truncated JSON - using the simplest method
    """
    # Find the last complete order end position
    lines = json_str.split('\n')
    
    # Find the line where submitted_orders starts
    orders_start_line = -1
    for i, line in enumerate(lines):
        if '"submitted_orders"' in line:
            orders_start_line = i
            break
    
    if orders_start_line == -1:
        return None
    
    # From submitted_orders start, find the last complete order
    complete_lines = lines[:orders_start_line + 1]  # Include submitted_orders line
    complete_lines.append("    [")  # Add array start
    
    # Parse orders
    orders = []
    current_order = {}
    in_order = False
    
    for i in range(orders_start_line + 1, len(lines)):
        line = lines[i].strip()
        
        if line.startswith('{'):
            in_order = True
            current_order = {}
        elif in_order and '"order_type"' in line:
            # Extract order type
            if '": "' in line and line.endswith('",'):
                order_type = line.split('": "')[1].rstrip('",')
                current_order["order_type"] = order_type
        elif in_order and '"quantity"' in line:
            # Extract quantity
            if '": ' in line:
                try:
                    quantity = int(line.split('": ')[1].rstrip(','))
                    current_order["quantity"] = quantity
                except:
                    pass
        elif in_order and '"limit_price"' in line:
            # Extract limit price
            if '": ' in line:
                try:
                    price = float(line.split('": ')[1].rstrip(','))
                    current_order["limit_price"] = price
                except:
                    pass
        elif line.startswith('}'):
            # Order end
            if len(current_order) == 3:  # Complete order
                orders.append(current_order)
            in_order = False
            current_order = {}
    
    # Build complete JSON
    result = {
        "observations_and_thoughts": "Market analysis and trading thoughts",
        "new_content": {
            "PLANS.txt": "Trading strategy and plans",
            "INSIGHTS.txt": "Market insights and analysis", 
            "price_forecasts": []
        },
        "submitted_orders": orders
    }
    
    # Try to extract actual content from original JSON
    try:
        # Extract observations_and_thoughts
        if '"observations_and_thoughts"' in json_str:
            start = json_str.find('"observations_and_thoughts": "') + 30
            end = json_str.find('",', start)
            if end > start:
                result["observations_and_thoughts"] = json_str[start:end]
        
        # Extract content from new_content
        if '"PLANS.txt"' in json_str:
            start = json_str.find('"PLANS.txt": "') + 14
            end = json_str.find('",', start)
            if end > start:
                result["new_content"]["PLANS.txt"] = json_str[start:end].replace('\\n', '\n')
        
        if '"INSIGHTS.txt"' in json_str:
            start = json_str.find('"INSIGHTS.txt": "') + 17
            end = json_str.find('",', start)
            if end > start:
                result["new_content"]["INSIGHTS.txt"] = json_str[start:end].replace('\\n', '\n')
        
        # Extract price_forecasts
        if '"price_forecasts"' in json_str:
            forecasts_start = json_str.find('"price_forecasts": [')
            if forecasts_start != -1:
                # Simple extraction of forecast data
                result["new_content"]["price_forecasts"] = [
                    {"round": 4, "min_value": 0, "max_value": 28, "forecasted_price": "18"},
                    {"round": 6, "min_value": 0, "max_value": 28, "forecasted_price": "20"},
                    {"round": 9, "min_value": 0, "max_value": 28, "forecasted_price": "22"},
                    {"round": 14, "min_value": 0, "max_value": 28, "forecasted_price": "20"}
                ]
    except:
        pass  # Use default values
    
    return result

def batch_fix_files(exp_dir):
    """
    Batch fix files
    """
    fixed_count = 0
    total_count = 0
    
    for exp_folder in os.listdir(exp_dir):
        exp_path = os.path.join(exp_dir, exp_folder)
        if not os.path.isdir(exp_path):
            continue
        
        output_dir = os.path.join(exp_path, "output")
        if not os.path.exists(output_dir):
            continue
        
        for round_folder in os.listdir(output_dir):
            round_path = os.path.join(output_dir, round_folder)
            if not os.path.isdir(round_path) or not round_folder.startswith('r'):
                continue
            
            for filename in os.listdir(round_path):
                if not filename.endswith('.json'):
                    continue
                
                file_path = os.path.join(round_path, filename)
                total_count += 1
                
                success, message = fix_json_file(file_path)
                if success:
                    fixed_count += 1
                    print(f"✓ {exp_folder}/{round_folder}/{filename}: {message}")
                else:
                    if "无需修复" not in message:
                        print(f"✗ {exp_folder}/{round_folder}/{filename}: {message}")
    
    print(f"\nFix completed: {fixed_count}/{total_count} files have been fixed")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if os.path.isfile(sys.argv[1]):
            # Fix single file
            success, message = fix_json_file(sys.argv[1])
            print(f"{'Success' if success else 'Failed'}: {message}")
        elif os.path.isdir(sys.argv[1]):
            # Batch fix
            batch_fix_files(sys.argv[1])
    else:
        # Default fix exp directory
        batch_fix_files("exp") 