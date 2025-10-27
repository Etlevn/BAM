#!/usr/bin/env python3
"""
NLP Missing Data Detection Script
Automatically detects missing JSON files and generates _miss.csv file
Usage: python nlp_miss.py
"""

import pandas as pd
from pathlib import Path
import sys
from tqdm.auto import tqdm

# ==================== [CONFIG] ====================

INPUT_FILE = "/Users/etlevn/Documents/iCollections/Collection/Collection/LLM_TRD/exp/Pt 2_EP/_sgl/sgl_output.csv"

# ==================================================

def check_missing():
    """Detect missing data based on configuration"""
    
    input_file = Path(INPUT_FILE)
    json_dir = input_file.parent / "nlp"
    
    print(f"[CONFIG] Input file: {input_file}")
    print(f"[CONFIG] JSON directory: {json_dir}")
    
    # 检查输入文件是否存在
    if not input_file.exists():
        print(f"[ERROR] Input file not found: {input_file}")
        return
    
    # 加载数据
    print(f"\n[INFO] Loading data from: {input_file}")
    df = pd.read_csv(input_file)
    print(f"[INFO] Total rows: {len(df)}")
    
    # 检查JSON目录是否存在
    if not json_dir.exists():
        print(f"[WARNING] JSON directory not found: {json_dir}")
        print("[INFO] No JSON files to check. All data is missing.")
        
        missing_df = df.copy()
        input_stem = input_file.stem
        input_suffix = input_file.suffix
        missing_filename = f"{input_stem}_miss{input_suffix}"
        missing_csv = input_file.parent / missing_filename
        missing_df.to_csv(missing_csv, index=False)
        print(f"[SAVE] All missing data saved to: {missing_csv}")
        return
    
    # 获取所有JSON文件
    json_files = list(json_dir.glob("*.json"))
    print(f"[INFO] Found {len(json_files)} JSON files")
    
    # 统计
    missing_plan = []
    missing_insight = []
    missing_both = []
    
    print("\n[INFO] Checking for missing JSON files...")
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Checking", leave=False):
        sim_idx = str(row.get('simulation_index', ''))
        agent_id = str(row.get('llm', ''))
        round_num = str(row.get('round', ''))
        
        plan_file = json_dir / f"{sim_idx}_{round_num}_{agent_id}_plan.json"
        insight_file = json_dir / f"{sim_idx}_{round_num}_{agent_id}_insight.json"
        
        has_plan = plan_file.exists()
        has_insight = insight_file.exists()
        
        if not has_plan:
            missing_plan.append(idx)
        if not has_insight:
            missing_insight.append(idx)
        if not has_plan and not has_insight:
            missing_both.append(idx)
    
    # 计算统计信息
    total = len(df)
    complete_count = total - len(missing_both)
    completion_rate = complete_count / total * 100 if total > 0 else 0
    
    # 输出统计 - 使用统一的英文格式
    print("\n" + "="*60)
    print("  Missing Data Statistics")
    print("="*60)
    print(f"Total rows: {total}")
    print(f"Complete: {complete_count}/{total} ({completion_rate:.2f}%)")
    print(f"Missing plan: {len(missing_plan)}/{total} ({len(missing_plan)/total*100:.2f}%)")
    print(f"Missing insight: {len(missing_insight)}/{total} ({len(missing_insight)/total*100:.2f}%)")
    print(f"Missing both: {len(missing_both)}/{total} ({len(missing_both)/total*100:.2f}%)")
    print("="*60)
    
    missing_indices = list(set(missing_plan + missing_insight))
    
    if missing_indices:
        missing_df = df.iloc[missing_indices].copy()
        # 获取原文件名（不含扩展名）并添加 _miss 后缀
        input_stem = input_file.stem
        input_suffix = input_file.suffix
        missing_filename = f"{input_stem}_miss{input_suffix}"
        missing_csv = input_file.parent / missing_filename
        missing_df.to_csv(missing_csv, index=False)
        print(f"[INFO] Missing data found: {len(missing_indices)} rows")
        print(f"\n[SAVE] Missing data saved to: {missing_csv})")
    else:
        print(f"[INFO] No missing data found")
    
    return missing_both

if __name__ == "__main__":
    try:
        check_missing()
        print("\n[DONE] Check complete!")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)