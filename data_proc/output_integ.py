#!/usr/bin/env python3
"""
Output Integration Script

整合每个simulation_index下output文件夹中的JSON文件，提取obs、plan、insight等字段，
并生成统一的CSV文件保存到market文件夹中。

用法:
    python output_integ.py [--config CONFIG_FILE] [--simulation_index SIM_ID]
"""

import json
import argparse
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any
import re


class OutputIntegrator:
    def __init__(self, config_file: str = None):
        """初始化输出整合器"""
        self.config = self._load_config(config_file)
        self.root_dir = Path(self.config['root_directory'])
        self.exp_dir = self.root_dir / self.config['experiment_directory']
        self.output_filename = self.config['output_filename']

    def _load_config(self, config_file: str = None) -> Dict[str, Any]:
        """加载配置文件"""
        if config_file is None:
            config_file = Path(__file__).parent / 'output_integ_config.json'
        
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f'配置文件不存在: {config_path}')
        
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        
        # 必需字段校验
        required = ['root_directory', 'experiment_directory', 'output_filename']
        missing = [k for k in required if k not in cfg or not cfg.get(k)]
        if missing:
            raise ValueError('配置缺少必要字段: ' + ', '.join(missing))
        
        return cfg

    def get_llm_type_mapping(self, simulation_index: str) -> Dict[str, str]:
        """获取LLM类型映射"""
        market_type = self.config.get('market_type')
        
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
        """从battle_royale_config.json加载LLM类型映射"""
        config_file = self.exp_dir / simulation_index / 'battle_royale_config.json'
        if not config_file.exists():
            return {}
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                battle_cfg = json.load(f)
            return battle_cfg.get('assignments', {})
        except Exception:
            return {}

    def get_formal_simulation_indices(self) -> List[str]:
        """获取所有正式轮simulation_index"""
        if not self.exp_dir.exists():
            print(f"实验目录不存在: {self.exp_dir}")
            return []
        
        formal_indices = []
        for item in self.exp_dir.iterdir():
            if item.is_dir() and self._is_formal_simulation(item.name):
                formal_indices.append(item.name)
        
        return sorted(formal_indices)

    def _is_formal_simulation(self, simulation_index: str) -> bool:
        """判断是否为正式轮simulation_index（20轮）"""
        output_dir = self.exp_dir / simulation_index / 'output'
        if not output_dir.exists():
            return False
        
        # 统计output目录下的轮次数量
        round_dirs = [d for d in output_dir.iterdir() if d.is_dir() and d.name.startswith('r')]
        round_count = len(round_dirs)
        
        # 正式轮应该有20轮
        return round_count == 20

    def get_rounds_in_simulation(self, simulation_index: str) -> List[int]:
        """获取simulation_index中的所有轮次"""
        output_dir = self.exp_dir / simulation_index / 'output'
        if not output_dir.exists():
            return []
        
        rounds = []
        for item in output_dir.iterdir():
            if item.is_dir() and item.name.startswith('r'):
                try:
                    round_num = int(item.name[1:])  # 去掉'r'前缀
                    rounds.append(round_num)
                except ValueError:
                    continue
        
        return sorted(rounds)

    def parse_json_file(self, json_file: Path) -> Dict[str, Any]:
        """解析单个JSON文件，提取obs、plan、insight"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 提取字段
            obs = data.get('observations_and_thoughts', '')
            plan = ''
            insight = ''
            
            # 从new_content中提取plan和insight
            new_content = data.get('new_content', {})
            if isinstance(new_content, dict):
                plan = new_content.get('PLANS.txt', '')
                insight = new_content.get('INSIGHTS.txt', '')
            
            return {
                'obs': obs,
                'plan': plan,
                'insight': insight
            }
        except Exception as e:
            print(f"解析JSON文件失败 {json_file}: {e}")
            return {
                'obs': '',
                'plan': '',
                'insight': ''
            }

    def integrate_simulation_output(self, simulation_index: str) -> bool:
        """整合单个simulation_index的output数据"""
        print(f"正在处理simulation_index: {simulation_index}")
        
        # 获取LLM类型映射
        llm_type_mapping = self.get_llm_type_mapping(simulation_index)
        market_type = self.config.get('market_type', 'unknown')
        
        # 获取所有轮次
        rounds = self.get_rounds_in_simulation(simulation_index)
        if not rounds:
            print(f"未找到轮次数据: {simulation_index}")
            return False
        
        print(f"发现轮次: {rounds}")
        
        # 收集所有数据
        all_data = []
        output_dir = self.exp_dir / simulation_index / 'output'
        
        for round_num in rounds:
            round_dir = output_dir / f'r{round_num}'
            if not round_dir.exists():
                continue
            
            # 处理该轮次的所有LLM JSON文件
            for json_file in round_dir.glob('llm_*.json'):
                # 提取LLM编号
                match = re.match(r'llm_(\d+)_r\d+\.json', json_file.name)
                if not match:
                    continue
                
                llm_id = match.group(1)
                llm_name = f'llm_{llm_id.zfill(3)}'
                
                # 解析JSON文件
                parsed_data = self.parse_json_file(json_file)
                
                # 添加元数据
                row_data = {
                    'llm': llm_name,
                    'llm_type': llm_type_mapping.get(llm_name, 'unknown'),
                    'market_type': market_type,
                    'round': round_num,
                    'simulation_index': simulation_index,
                    'obs': parsed_data['obs'],
                    'plan': parsed_data['plan'],
                    'insight': parsed_data['insight']
                }
                
                all_data.append(row_data)
        
        if not all_data:
            print(f"未找到任何数据: {simulation_index}")
            return False
        
        # 创建DataFrame并保存
        df = pd.DataFrame(all_data)
        
        # 保存到market文件夹
        market_dir = self.exp_dir / simulation_index / 'market'
        market_dir.mkdir(exist_ok=True)
        
        output_file = market_dir / self.output_filename
        df.to_csv(output_file, index=False, encoding='utf-8')
        
        print(f"已保存 {len(all_data)} 条记录到: {output_file}")
        return True

    def integrate_all_outputs(self) -> None:
        """整合所有simulation_index的output数据"""
        formal_indices = self.get_formal_simulation_indices()
        
        if not formal_indices:
            print("未发现正式轮simulation_index")
            return
        
        print(f"发现 {len(formal_indices)} 个正式轮simulation_index")
        
        success_count = 0
        for simulation_index in formal_indices:
            if self.integrate_simulation_output(simulation_index):
                success_count += 1
        
        print(f"成功处理 {success_count}/{len(formal_indices)} 个simulation_index")


def main():
    parser = argparse.ArgumentParser(description='整合output文件夹中的JSON数据')
    parser.add_argument('--config', help='配置文件路径')
    parser.add_argument('--simulation_index', help='指定单个simulation_index进行处理')
    
    args = parser.parse_args()
    
    try:
        integrator = OutputIntegrator(args.config)
        
        if args.simulation_index:
            # 处理单个simulation_index
            integrator.integrate_simulation_output(args.simulation_index)
        else:
            # 处理所有simulation_index
            integrator.integrate_all_outputs()
    
    except Exception as e:
        print(f"错误: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
