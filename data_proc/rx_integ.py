#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RX整合脚本（r1..rN → rX.csv 合并）
读取 experiment_directory 下所有正式轮 simulation_index 的 r1..rN.csv，
添加元数据列后纵向合并为 rX.csv。
配置采用单一 JSON（包含 br 与 sgl 分支），可用命令行覆盖。
"""

import os
import re
import pandas as pd
from pathlib import Path
import json
from typing import Dict, List

# 配置仅从JSON读取；不在脚本内提供默认常量

class DataIntegrator:
    """RX 数据整合器"""

    def __init__(self, config_file: str = None):
        self.config = self._load_config(config_file)
        self.root_dir = Path(self.config['root_directory'])
        self.exp_dir = self.root_dir / self.config['experiment_directory']
        
    def _load_config(self, config_file: str) -> Dict:
        if config_file and os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                external = json.load(f)
            market_type = external.get('market_type')
            if market_type not in ('br', 'sgl'):
                raise ValueError('配置中缺少或非法的 market_type (需为 "br" 或 "sgl")')
            merged = {
                'market_type': market_type,
                'root_directory': external.get('root_directory'),
                'experiment_directory': external.get('experiment_directory'),
                'output_filename': external.get('output_filename'),
                # total_rounds 可省略，将自动检测
            }
            if market_type == 'sgl':
                merged['sgl_llm_type'] = external.get('sgl_llm_type')

            missing = [k for k in ['root_directory', 'experiment_directory', 'output_filename'] if not merged.get(k)]
            if missing:
                raise ValueError("配置缺少必要字段: " + ", ".join(missing))
            return merged
        else:
            default_cfg = Path(__file__).with_name('rx_integ_config.json')
            if default_cfg.exists():
                return self._load_config(str(default_cfg))
            raise ValueError('未提供配置文件，且默认配置文件不存在: rx_integ_config.json')
    
    def get_available_simulation_indices(self) -> List[str]:
        """
        获取所有可用的simulation_index
        
        Returns:
            simulation_index列表
        """
        if not self.exp_dir.exists():
            print(f"实验目录不存在: {self.exp_dir}")
            return []
            
        def is_formal(sim_dir: Path) -> bool:
            market_dir = sim_dir / 'market'
            if not market_dir.exists():
                return False
            rounds = []
            for p in market_dir.glob('r*.csv'):
                m = re.fullmatch(r"r(\d+)\.csv", p.name)
                if m:
                    try:
                        rounds.append(int(m.group(1)))
                    except Exception:
                        pass
            rounds = sorted(set(rounds))
            # 正式轮：从1开始连续且最大轮 >= 20
            return rounds and (rounds == list(range(1, rounds[-1] + 1))) and rounds[-1] >= 20

        indices: List[str] = []
        for item in self.exp_dir.iterdir():
            if not item.is_dir() or not item.name.startswith('20'):
                continue
            if is_formal(item):
                indices.append(item.name)
        return sorted(indices)
    
    def load_round_data(self, simulation_index: str, round_num: int) -> pd.DataFrame:
        """
        加载指定轮次的数据
        
        Args:
            simulation_index: 实验索引
            round_num: 轮次编号
            
        Returns:
            数据DataFrame
        """
        market_dir = self.exp_dir / simulation_index / 'market'
        csv_file = market_dir / f'r{round_num}.csv'
        
        if not csv_file.exists():
            print(f"警告: 文件不存在 {csv_file}")
            return pd.DataFrame()
        
        try:
            df = pd.read_csv(csv_file)
            return df
        except Exception as e:
            print(f"错误: 读取文件失败 {csv_file}: {e}")
            return pd.DataFrame()
    
    def get_llm_type_mapping(self, simulation_index: str) -> Dict[str, str]:
        """
        根据market_type获取llm_type_mapping
        
        Args:
            simulation_index: 实验索引
            
        Returns:
            llm_type_mapping字典
        """
        market_type = self.config['market_type']
        
        if market_type == 'sgl':
            # SGL：所有 LLM 使用同一个名称（sgl_llm_type）
            sgl_llm_type = self.config.get('sgl_llm_type')
            if not isinstance(sgl_llm_type, str) or not sgl_llm_type:
                raise ValueError('sgl 模式需要在配置中提供 sgl_llm_type')
            return {f'llm_{i:03d}': sgl_llm_type for i in range(1, 21)}
        
        elif market_type == 'br':
            # BR模式：从battle_royale_config.json读取分配
            return self._load_battle_royale_mapping(simulation_index)
        
        else:
            # 其它情况：没有映射
            return {}
    
    def _load_battle_royale_mapping(self, simulation_index: str) -> Dict[str, str]:
        """
        从battle_royale_config.json加载LLM分配
        
        Args:
            simulation_index: 实验索引
            
        Returns:
            llm_type_mapping字典
        """
        config_file = self.exp_dir / simulation_index / 'battle_royale_config.json'
        
        if not config_file.exists():
            print(f"警告: battle_royale_config.json不存在: {config_file}")
            return {}
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                battle_config = json.load(f)
            
            # 从assignments中提取映射
            assignments = battle_config.get('assignments', {})
            return assignments
            
        except Exception as e:
            print(f"错误: 读取battle_royale_config.json失败 {config_file}: {e}")
            return {}
    
    def add_metadata_columns(self, df: pd.DataFrame, simulation_index: str, round_num: int) -> pd.DataFrame:
        """
        为DataFrame添加元数据列
        
        Args:
            df: 原始数据DataFrame
            simulation_index: 实验索引
            round_num: 轮次编号
            
        Returns:
            添加元数据后的DataFrame
        """
        if df.empty:
            return df
        
        # 创建副本避免修改原始数据
        df_copy = df.copy()
        
        # 获取llm_type_mapping
        llm_mapping = self.get_llm_type_mapping(simulation_index)
        
        # 添加llm_type列
        df_copy['llm_type'] = df_copy['llm'].map(llm_mapping)
        
        # 添加market_type列
        df_copy['market_type'] = self.config['market_type']
        
        # 添加round列
        df_copy['round'] = round_num
        
        # 添加simulation_index列
        df_copy['simulation_index'] = simulation_index
        
        return df_copy
    
    def integrate_simulation_data(self, simulation_index: str) -> pd.DataFrame:
        """
        整合指定simulation_index的所有轮次数据
        
        Args:
            simulation_index: 实验索引
            
        Returns:
            整合后的DataFrame
        """
        print(f"开始整合 simulation_index: {simulation_index}")
        
        all_data = []
        
        # 自动探测总轮次：以 market 下 rN.csv 的最大 N 为准
        market_dir = self.exp_dir / simulation_index / 'market'
        rounds = []
        for p in market_dir.glob('r*.csv'):
            m = re.fullmatch(r"r(\d+)\.csv", p.name)
            if m:
                try:
                    rounds.append(int(m.group(1)))
                except Exception:
                    pass
        rounds = sorted(set(rounds))
        if not rounds:
            print(f"错误: 未能检测到轮次 r*.csv 于 {market_dir}")
            return pd.DataFrame()
        total_rounds = rounds[-1]

        for round_num in range(1, total_rounds + 1):
            print(f"  处理轮次 {round_num}...")
            
            # 加载轮次数据
            round_df = self.load_round_data(simulation_index, round_num)
            
            if not round_df.empty:
                # 添加元数据列
                round_df_with_metadata = self.add_metadata_columns(round_df, simulation_index, round_num)
                all_data.append(round_df_with_metadata)
            else:
                print(f"    警告: 轮次 {round_num} 数据为空")
        
        if not all_data:
            print(f"错误: 没有找到任何数据 for {simulation_index}")
            return pd.DataFrame()
        
        # 合并所有数据
        integrated_df = pd.concat(all_data, ignore_index=True)
        
        print(f"整合完成: {len(integrated_df)} 行数据")
        return integrated_df
    
    def save_integrated_data(self, df: pd.DataFrame, simulation_index: str) -> str:
        """
        保存整合后的数据
        
        Args:
            df: 整合后的DataFrame
            simulation_index: 实验索引
            
        Returns:
            保存的文件路径
        """
        if df.empty:
            print("错误: 没有数据需要保存")
            return ""
        
        # 创建输出目录
        market_dir = self.exp_dir / simulation_index / 'market'
        market_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成输出文件路径
        output_file = market_dir / self.config['output_filename']
        
        try:
            # 保存CSV文件
            df.to_csv(output_file, index=False, encoding='utf-8')
            print(f"数据已保存到: {output_file}")
            return str(output_file)
        except Exception as e:
            print(f"错误: 保存文件失败 {output_file}: {e}")
            return ""
    
    # 已移除 summary 功能
    
    def run_integration(self, simulation_index: str = None) -> bool:
        """
        运行数据整合流程
        
        Args:
            simulation_index: 指定的simulation_index，如果为None则使用配置中的默认值
            
        Returns:
            是否成功
        """
        # 若未指定则内部不使用 target_simulation_index，外部批处理统一调度
        
        print(f"开始数据整合流程...")
        print(f"目标simulation_index: {simulation_index}")
        print(f"市场类型: {self.config['market_type']}")
        print("-" * 50)
        
        # 检查simulation_index是否存在
        sim_dir = self.exp_dir / simulation_index
        if not sim_dir.exists():
            print(f"错误: simulation_index目录不存在: {sim_dir}")
            return False
        
        # 整合数据
        integrated_df = self.integrate_simulation_data(simulation_index)
        
        if integrated_df.empty:
            print("错误: 没有成功整合任何数据")
            return False
        
        # 保存整合数据（不再依赖配置开关，始终保存）
        output_file = self.save_integrated_data(integrated_df, simulation_index)
        if not output_file:
            return False
        
        # 不生成汇总报告
        
        print("-" * 50)
        print("数据整合完成!")
        return True
    
    # 取消列出功能（简化）


def main():
    import argparse
    parser = argparse.ArgumentParser(description='RX整合脚本（r1..rN → rX.csv）')
    parser.add_argument('--config', '-c', type=str, default=None, help='配置文件路径（单一 JSON，包含 br 与 sgl 分支）')
    args = parser.parse_args()

    # 默认加载同目录 rx_integ_config.json（若未提供 --config）
    if not args.config:
        default_cfg = Path(__file__).with_name('rx_integ_config.json')
        if default_cfg.exists():
            args.config = str(default_cfg)

    integrator = DataIntegrator(
        config_file=args.config,
    )

    sims = integrator.get_available_simulation_indices()
    if not sims:
        print('未发现正式轮 simulation_index')
        return

    for sim in sims:
        success = integrator.run_integration(sim)
        if success:
            print(f'已处理: {sim}')


if __name__ == "__main__":
    main()
