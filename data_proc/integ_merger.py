#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量数据合并脚本（统一配置）
从单一 JSON 配置中读取：
- market_type: 'br' | 'sgl'
- merge_source: 'market' | 'rx'  （合并 market_integ 或 rx_integ 生成的CSV）
- root_directory: 根目录
- expected_filename: 要合并的文件名（如 _rX.csv 或 _mkt.csv）
- merged_output: 合并输出文件名（如 merged.csv）

不在脚本内设置任何默认配置，若未传 --config 则尝试同目录 merger_config.json。
不保存任何summary；不依赖total_rounds配置，自动依据r1..rN连续性识别正式轮。
"""

import os
import re
import pandas as pd
from pathlib import Path
import json
from typing import Dict, List, Tuple
import argparse

class BatchMerger:
    """批量数据合并器（基于统一JSON配置）"""

    def __init__(self, config_file: str = None):
        self.config = self._load_config(config_file)
        self.root_dir = Path(self.config['root_directory'])
        
    def _load_config(self, config_file: str = None) -> Dict:
        if config_file and os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        else:
            default_cfg = Path(__file__).with_name('integ_merger_config.json')
            if not default_cfg.exists():
                raise ValueError('未提供配置文件，且默认配置文件不存在: integ_merger_config.json')
            with open(default_cfg, 'r', encoding='utf-8') as f:
                cfg = json.load(f)

        # 必需字段校验（不再需要 market_type）
        required = ['root_directory', 'expected_filename', 'merged_output']
        missing = [k for k in required if k not in cfg or not cfg.get(k)]
        if missing:
            raise ValueError('配置缺少必要字段: ' + ', '.join(missing))
        # 直接读取 expected_filename
        return cfg
    
    def discover_experiment_directories(self) -> List[str]:
        """
        读取 root_directory 下的所有一级子目录作为 experiment_directory，
        仅保留那些内部包含至少一个 simulation_index 的目录。
        """
        if not self.root_dir.exists():
            print(f"根目录不存在: {self.root_dir}")
            return []
        experiment_dirs: List[str] = []
        for item in self.root_dir.iterdir():
            if not item.is_dir():
                continue
            sim_indices = self._get_simulation_indices_in_dir(item)
            if sim_indices:
                experiment_dirs.append(item.name)
        return sorted(experiment_dirs)
    
    def _get_simulation_indices_in_dir(self, exp_dir: Path) -> List[str]:
        """
        获取指定目录下的所有simulation_index
        
        Args:
            exp_dir: 实验目录路径
            
        Returns:
            simulation_index列表
        """
        simulation_indices = []
        
        if not exp_dir.exists():
            return simulation_indices
        
        for item in exp_dir.iterdir():
            if item.is_dir() and item.name.startswith('20'):  # 假设simulation_index以20开头
                simulation_indices.append(item.name)
        
        return sorted(simulation_indices)
    
    def find_target_files(self, exp_dir_name: str) -> List[Tuple[str, str, Path]]:
        """在指定 experiment_directory 中查找所有需要合并的目标文件（expected_filename）。"""
        rx_files = []
        expected_filename = self.config['expected_filename']
        # 双层结构：experiment_directory / simulation_index / market
        exp_dir = self.root_dir / exp_dir_name
        
        if not exp_dir.exists():
            print(f"警告: experiment_directory不存在: {exp_dir}")
            return rx_files
        
        # 获取所有simulation_index
        simulation_indices = self._get_simulation_indices_in_dir(exp_dir)
        
        for sim_idx in simulation_indices:
            # 检查是否为正式轮实验
            market_dir = exp_dir / sim_idx / 'market'
            if not market_dir.exists():
                continue
            # 只处理正式轮：r1..rN 从1开始连续，且最大轮 >= 20（自动判定，不依赖配置）
            rounds = []
            for p in market_dir.glob('r*.csv'):
                m = re.fullmatch(r"r(\d+)\.csv", p.name)
                if m:
                    try:
                        rounds.append(int(m.group(1)))
                    except Exception:
                        pass
            rounds = sorted(set(rounds))
            if rounds and rounds == list(range(1, rounds[-1] + 1)) and rounds[-1] >= 20:
                target_file = market_dir / expected_filename
                if target_file.exists():
                    rx_files.append((exp_dir_name, sim_idx, target_file))
                else:
                    print(f"警告: 目标文件不存在: {target_file}")
            else:
                print(f"跳过 {exp_dir_name}/{sim_idx}: 非正式轮实验 (轮次数: {len(rounds)})")
        
        return rx_files
    
    def load_csv(self, file_path: Path) -> pd.DataFrame:
        """
        加载CSV文件
        
        Args:
            file_path: CSV文件路径
            
        Returns:
            DataFrame
        """
        try:
            df = pd.read_csv(file_path)
            
            if df.empty:
                print(f"警告: 文件为空: {file_path}")
                return df
            
            return df
            
        except Exception as e:
            print(f"错误: 读取文件失败 {file_path}: {e}")
            return pd.DataFrame()
    
    def merge_all_target_files(self) -> pd.DataFrame:
        """合并所有找到的目标CSV文件。"""
        print("开始搜索所有rX.csv文件...")
        
        # 发现所有experiment_directory
        exp_dirs = self.discover_experiment_directories()
        
        if not exp_dirs:
            print("❌ 没有找到任何experiment_directory")
            return pd.DataFrame()
        
        print(f"发现 {len(exp_dirs)} 个experiment_directory:")
        for exp_dir in exp_dirs:
            print(f"  - {exp_dir}")
        
        # 收集所有rX.csv文件
        all_rx_files = []
        for exp_dir in exp_dirs:
            rx_files = self.find_target_files(exp_dir)
            all_rx_files.extend(rx_files)
            print(f"  {exp_dir}: 找到 {len(rx_files)} 个目标文件")
        
        if not all_rx_files:
            print("❌ 没有找到任何rX.csv文件")
            return pd.DataFrame()
        
        print(f"\n总共找到 {len(all_rx_files)} 个目标文件")
        
        # 加载并合并所有文件
        all_dataframes = []
        
        for exp_dir_name, sim_idx, file_path in all_rx_files:
            prefix = (exp_dir_name + "/") if exp_dir_name else ""
            print(f"  加载: {prefix}{sim_idx}/market/{self.config['expected_filename']}")
            
            df = self.load_csv(file_path)
            
            if not df.empty:
                all_dataframes.append(df)
            else:
                print(f"    警告: 跳过空文件")
        
        if not all_dataframes:
            print("❌ 没有成功加载任何数据")
            return pd.DataFrame()
        
        # 合并所有DataFrame
        print(f"\n合并 {len(all_dataframes)} 个数据文件...")
        merged_df = pd.concat(all_dataframes, ignore_index=True)
        
        print(f"合并完成: {len(merged_df)} 行数据")
        return merged_df
    
    def save_merged_data(self, df: pd.DataFrame) -> str:
        """保存合并后的数据。"""
        if df.empty:
            print("错误: 没有数据需要保存")
            return ""
        
        # 生成输出文件路径
        output_file = self.root_dir / self.config['merged_output']
        
        try:
            # 保存CSV文件
            df.to_csv(output_file, index=False, encoding='utf-8')
            print(f"合并数据已保存到: {output_file}")
            return str(output_file)
        except Exception as e:
            print(f"错误: 保存文件失败 {output_file}: {e}")
            return ""
    
    # 已移除 summary 相关功能
    
    def run_batch_merge(self) -> bool:
        """
        运行批量合并流程
        
        Returns:
            是否成功
        """
        print("=" * 60)
        print("批量数据合并脚本")
        print("=" * 60)
        print(f"根目录: {self.root_dir}")
        print(f"预计输入文件: {self.config['expected_filename']}")
        print(f"输出文件名: {self.config['merged_output']}")
        print("-" * 50)
        
        # 合并所有rX.csv文件
        merged_df = self.merge_all_target_files()
        
        if merged_df.empty:
            print("❌ 没有成功合并任何数据")
            return False
        
        # 保存合并数据
        output_file = self.save_merged_data(merged_df)
        if not output_file:
            return False
        
        print("-" * 50)
        print("批量合并完成!")
        return True
    
    # 省略列出方法，避免维护重复逻辑


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='批量合并多个experiment_directory中的生成CSV文件（基于统一JSON配置）')
    parser.add_argument('--config', '-c', type=str, default=None, help='配置文件路径（若省略，则读取同目录 merger_config.json）')
    args = parser.parse_args()

    merger = BatchMerger(args.config)
    success = merger.run_batch_merge()
    print("\n🎉 批量合并成功完成!" if success else "\n❌ 批量合并失败!")


if __name__ == "__main__":
    main()
