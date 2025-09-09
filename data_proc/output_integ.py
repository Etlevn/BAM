#!/usr/bin/env python3
"""
Output Integration Script

Parse JSON files under each simulation_index's output/rX/ directory, extract
obs, plan, insight, and write a unified CSV into the market folder.

Usage:
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
        """Initialize the output integrator"""
        self.config = self._load_config(config_file)
        self.root_dir = Path(self.config['root_directory'])
        self.exp_dir = self.root_dir / self.config['experiment_directory']
        self.output_filename = self.config['output_filename']

    def _load_config(self, config_file: str = None) -> Dict[str, Any]:
        """Load configuration file"""
        if config_file is None:
            config_file = Path(__file__).parent / 'output_integ_config.json'
        
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f'Config file not found: {config_path}')
        
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        
        # Required fields
        required = ['root_directory', 'experiment_directory', 'output_filename']
        missing = [k for k in required if k not in cfg or not cfg.get(k)]
        if missing:
            raise ValueError('Config missing required fields: ' + ', '.join(missing))
        
        return cfg

    def get_llm_type_mapping(self, simulation_index: str) -> Dict[str, str]:
        """Get LLM type mapping"""
        market_type = self.config.get('market_type')
        
        if market_type == 'sgl':
            # SGL: all LLM share the same name (sgl_llm_type)
            sgl_llm_type = self.config.get('sgl_llm_type')
            if not isinstance(sgl_llm_type, str) or not sgl_llm_type:
                raise ValueError('sgl mode requires sgl_llm_type in config')
            return {f'llm_{i:03d}': sgl_llm_type for i in range(1, 21)}
        
        elif market_type == 'br':
            # BR mode: read assignments from battle_royale_config.json
            return self._load_battle_royale_mapping(simulation_index)
        
        else:
            # Fallback: no mapping
            return {}

    def _load_battle_royale_mapping(self, simulation_index: str) -> Dict[str, str]:
        """Load LLM type mapping from battle_royale_config.json"""
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
        """Get all formal (20 rounds) simulation_index names"""
        if not self.exp_dir.exists():
            print(f"Experiment directory not found: {self.exp_dir}")
            return []
        
        formal_indices = []
        for item in self.exp_dir.iterdir():
            if item.is_dir() and self._is_formal_simulation(item.name):
                formal_indices.append(item.name)
        
        return sorted(formal_indices)

    def _is_formal_simulation(self, simulation_index: str) -> bool:
        """Return True if this simulation_index is formal (exactly 20 rounds)"""
        output_dir = self.exp_dir / simulation_index / 'output'
        if not output_dir.exists():
            return False
        
        # Count round directories under output
        round_dirs = [d for d in output_dir.iterdir() if d.is_dir() and d.name.startswith('r')]
        round_count = len(round_dirs)

        # Formal requires 20 rounds
        return round_count == 20

    def get_rounds_in_simulation(self, simulation_index: str) -> List[int]:
        """List all round numbers contained in this simulation_index"""
        output_dir = self.exp_dir / simulation_index / 'output'
        if not output_dir.exists():
            return []
        
        rounds = []
        for item in output_dir.iterdir():
            if item.is_dir() and item.name.startswith('r'):
                try:
                    round_num = int(item.name[1:])  # strip leading 'r'
                    rounds.append(round_num)
                except ValueError:
                    continue
        
        return sorted(rounds)

    def parse_json_file(self, json_file: Path) -> Dict[str, Any]:
        """Parse a single JSON file and extract obs / plan / insight"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Extract fields
            obs = data.get('observations_and_thoughts', '')
            plan = ''
            insight = ''

            # Extract from new_content
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
            print(f"Failed to parse JSON {json_file}: {e}")
            return {
                'obs': '',
                'plan': '',
                'insight': ''
            }

    def integrate_simulation_output(self, simulation_index: str) -> bool:
        """Integrate output data for a single simulation_index"""
        print(f"Processing simulation_index: {simulation_index}")
        
        # 获取LLM类型映射
        llm_type_mapping = self.get_llm_type_mapping(simulation_index)
        market_type = self.config.get('market_type', 'unknown')
        
        # Collect rounds
        rounds = self.get_rounds_in_simulation(simulation_index)
        if not rounds:
            print(f"No round data found: {simulation_index}")
            return False

        print(f"Rounds found: {rounds}")
        
        # 收集所有数据
        all_data = []
        output_dir = self.exp_dir / simulation_index / 'output'
        
        for round_num in rounds:
            round_dir = output_dir / f'r{round_num}'
            if not round_dir.exists():
                continue
            # Iterate all LLM JSON files of the round
            for json_file in round_dir.glob('llm_*.json'):
                # Extract LLM id
                match = re.match(r'llm_(\d+)_r\d+\.json', json_file.name)
                if not match:
                    continue
                
                llm_id = match.group(1)
                llm_name = f'llm_{llm_id.zfill(3)}'
                
                # Parse JSON
                parsed_data = self.parse_json_file(json_file)
                
                # Compose row with metadata
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
            print(f"No data found: {simulation_index}")
            return False
        
        # Save
        df = pd.DataFrame(all_data)
        
        # Save into market folder
        market_dir = self.exp_dir / simulation_index / 'market'
        market_dir.mkdir(exist_ok=True)
        
        output_file = market_dir / self.output_filename
        df.to_csv(output_file, index=False, encoding='utf-8')
        
        print(f"Saved {len(all_data)} rows to: {output_file}")
        return True

    def integrate_all_outputs(self) -> None:
        """Integrate output data for all simulation_index"""
        formal_indices = self.get_formal_simulation_indices()
        
        if not formal_indices:
            print("No formal simulation_index found")
            return

        print(f"Found {len(formal_indices)} formal simulation_index")
        
        success_count = 0
        for simulation_index in formal_indices:
            if self.integrate_simulation_output(simulation_index):
                success_count += 1
        
        print(f"Successfully processed {success_count}/{len(formal_indices)} simulation_index")


def main():
    parser = argparse.ArgumentParser(description='Integrate JSON data under output folders')
    parser.add_argument('--config', help='Path to config file')
    parser.add_argument('--simulation_index', help='Process a single simulation_index only')
    
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
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
