#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch add sgl_config.json to all simulation_index under a given experiment_directory.

Usage examples:
  python batch_add_sgl_config.py --exp_dir \
    "/Users/etlevn/Documents/iCollections/Collection/LLM_TRD/exp/20250922_012133" \
    --template ./data_proc/sgl_config_template.json

  python batch_add_sgl_config.py --exp_dir <exp_dir> \
    --content '{"model_name": "gpt-4o", "service_name": "openai", "num_llms": 20, "mode": "single"}'

Flags:
  --overwrite  overwrite existing sgl_config.json if present (default: False)
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any
import argparse


# ===== Global configuration =====
# 如果未提供 CLI 参数，将使用以下全局配置。
# 将 EXPERIMENT_DIRECTORY 设置为包含 simulation_index 子目录的目标实验目录。
# 直接在此处定义要写入的 sgl_config JSON 内容（Python 字典）。
EXPERIMENT_DIRECTORY = "/Users/etlevn/Documents/iCollections/Collection/LLM_TRD/exp/Pt 2_EP/Qwen_Qwen3-235B-A22B-Instruct-2507"
SGL_CONFIG: Dict[str, Any] = {
    "model_name": "Qwen/Qwen3-235B-A22B-Instruct-2507",
    "num_llms": 20,
    "description": "Qwen 3",
    "service_name": "deep_infra",
    "mode": "single"
}


def load_content(args: argparse.Namespace) -> Dict[str, Any]:
    # 优先级：CLI --content > 全局 SGL_CONFIG
    if args.content:
        try:
            return json.loads(args.content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in --content: {e}")
    return dict(SGL_CONFIG)


def is_simulation_index(dir_path: Path) -> bool:
    """
    Treat any immediate subdirectory as simulation_index, including test rounds.
    Skip hidden/underscore directories like _cache or .DS_Store.
    """
    return dir_path.is_dir() and not dir_path.name.startswith('_') and not dir_path.name.startswith('.')


def write_sgl_config(sim_dir: Path, content: Dict[str, Any], overwrite: bool) -> bool:
    target = sim_dir / 'sgl_config.json'
    if target.exists() and not overwrite:
        print(f"Skip (exists): {target}")
        return False
    try:
        with target.open('w', encoding='utf-8') as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        print(f"Wrote: {target}")
        return True
    except Exception as e:
        print(f"Error writing {target}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Batch add sgl_config.json to simulation_index folders')
    parser.add_argument('--exp_dir', help='Path to experiment directory (contains simulation_index subfolders)')
    parser.add_argument('--content', help='Inline JSON string for sgl_config.json content (optional)')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing sgl_config.json files')
    args = parser.parse_args()

    exp_path_str = args.exp_dir if args.exp_dir else EXPERIMENT_DIRECTORY
    if not exp_path_str:
        print('Please specify --exp_dir or set EXPERIMENT_DIRECTORY at top of script')
        return 1
    exp_dir = Path(exp_path_str)
    if not exp_dir.exists() or not exp_dir.is_dir():
        print(f"Invalid experiment directory: {exp_dir}")
        return 1

    try:
        content = load_content(args)
    except Exception as e:
        print(f"Failed to load content: {e}")
        return 1

    # Iterate all simulation_index under exp_dir
    sim_dirs = [p for p in sorted(exp_dir.iterdir()) if is_simulation_index(p)]
    if not sim_dirs:
        print(f"No simulation_index folders found under: {exp_dir}")
        return 0

    print(f"Found {len(sim_dirs)} simulation_index under {exp_dir}")
    total = 0
    written = 0
    skipped = 0
    for sim in sim_dirs:
        total += 1
        if write_sgl_config(sim, content, args.overwrite):
            written += 1
        else:
            skipped += 1

    print(f"Done. Written: {written}, Skipped: {skipped}, Total: {total}")
    return 0


if __name__ == '__main__':
    sys.exit(main())


