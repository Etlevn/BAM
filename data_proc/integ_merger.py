#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch CSV merge script (config-driven)
Config fields:
- root_directory: root path
- expected_filename: target filename to merge (e.g., _rX.csv, _mkt.csv, _output.csv)
- merged_output: merged CSV filename (e.g., merged.csv)

No defaults inside script; if --config omitted, tries integ_merger_config.json in the same dir.
No summary saving; formal runs auto-detected by r1..rN continuity, max round >= 20.
"""

import os
import re
import pandas as pd
from pathlib import Path
import json
from typing import Dict, List, Tuple
import argparse

class BatchMerger:
    """Batch CSV merger (single JSON config)"""

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
                raise ValueError('No config provided and default integ_merger_config.json not found')
            with open(default_cfg, 'r', encoding='utf-8') as f:
                cfg = json.load(f)

        # Required fields (market_type not needed)
        required = ['root_directory', 'expected_filename', 'merged_output']
        missing = [k for k in required if k not in cfg or not cfg.get(k)]
        if missing:
            raise ValueError('Config missing required fields: ' + ', '.join(missing))
        # use expected_filename directly
        return cfg
    
    def discover_experiment_directories(self) -> List[str]:
        """
        Read first-level subdirectories under root_directory as experiment_directory,
        keep those that contain at least one simulation_index.
        """
        if not self.root_dir.exists():
            print(f"Root directory not found: {self.root_dir}")
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
        """Get all simulation_index under the given experiment directory"""
        simulation_indices = []
        
        if not exp_dir.exists():
            return simulation_indices
        
        for item in exp_dir.iterdir():
            if item.is_dir() and item.name.startswith('20'):  # assume simulation_index starts with '20'
                simulation_indices.append(item.name)
        
        return sorted(simulation_indices)
    
    def find_target_files(self, exp_dir_name: str) -> List[Tuple[str, str, Path]]:
        """Find all target files (expected_filename) in the given experiment_directory."""
        rx_files = []
        expected_filename = self.config['expected_filename']
        # Two-level layout: experiment_directory / simulation_index / market
        exp_dir = self.root_dir / exp_dir_name
        
        if not exp_dir.exists():
            print(f"Warning: experiment_directory not found: {exp_dir}")
            return rx_files
        
        # Get all simulation_index
        simulation_indices = self._get_simulation_indices_in_dir(exp_dir)
        
        for sim_idx in simulation_indices:
            # Check formal run
            market_dir = exp_dir / sim_idx / 'market'
            if not market_dir.exists():
                continue
            # Formal: r1..rN continuous from 1, and max round >= 20
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
                    print(f"Warning: target file not found: {target_file}")
            else:
                print(f"Skip {exp_dir_name}/{sim_idx}: non-formal (rounds: {len(rounds)})")
        
        return rx_files
    
    def load_csv(self, file_path: Path) -> pd.DataFrame:
        """Load CSV file and return DataFrame"""
        try:
            df = pd.read_csv(file_path)
            
            if df.empty:
                print(f"Warning: empty file: {file_path}")
                return df
            
            return df
            
        except Exception as e:
            print(f"Error: failed to read {file_path}: {e}")
            return pd.DataFrame()
    
    def merge_all_target_files(self) -> pd.DataFrame:
        """Merge all found target CSV files"""
        print("Start searching for target CSV files...")
        
        # Discover all experiment_directory
        exp_dirs = self.discover_experiment_directories()
        
        if not exp_dirs:
            print("❌ No experiment_directory found")
            return pd.DataFrame()
        
        print(f"Found {len(exp_dirs)} experiment_directory:")
        for exp_dir in exp_dirs:
            print(f"  - {exp_dir}")
        
        # Collect all target CSV files
        all_rx_files = []
        for exp_dir in exp_dirs:
            rx_files = self.find_target_files(exp_dir)
            all_rx_files.extend(rx_files)
            print(f"  {exp_dir}: {len(rx_files)} target files")
        
        if not all_rx_files:
            print("❌ No target CSV found")
            return pd.DataFrame()
        
        print(f"\nTotal {len(all_rx_files)} target files")
        
        # Load and concat all files
        all_dataframes = []
        
        for exp_dir_name, sim_idx, file_path in all_rx_files:
            prefix = (exp_dir_name + "/") if exp_dir_name else ""
            print(f"  Load: {prefix}{sim_idx}/market/{self.config['expected_filename']}")
            
            df = self.load_csv(file_path)
            
            if not df.empty:
                all_dataframes.append(df)
            else:
                print(f"    Warning: skip empty file")
        
        if not all_dataframes:
            print("❌ Failed to load any data")
            return pd.DataFrame()
        
        # Concat DataFrames
        print(f"\nMerging {len(all_dataframes)} files...")
        merged_df = pd.concat(all_dataframes, ignore_index=True)
        print(f"Merged: {len(merged_df)} rows")
        return merged_df
    
    def save_merged_data(self, df: pd.DataFrame) -> str:
        """Save merged data"""
        if df.empty:
            print("Error: no data to save")
            return ""
        
        # Build output file path
        output_file = self.root_dir / self.config['merged_output']
        
        try:
            # Save CSV
            df.to_csv(output_file, index=False, encoding='utf-8')
            print(f"Saved merged CSV to: {output_file}")
            return str(output_file)
        except Exception as e:
            print(f"Error: failed to save {output_file}: {e}")
            return ""
    
    # Summary function removed
    
    def run_batch_merge(self) -> bool:
        """Run batch merge; returns whether succeeded"""
        print("=" * 60)
        print("Batch CSV Merger")
        print("=" * 60)
        print(f"Root: {self.root_dir}")
        print(f"Expected input: {self.config['expected_filename']}")
        print(f"Output: {self.config['merged_output']}")
        print("-" * 50)
        
        # Merge all CSV
        merged_df = self.merge_all_target_files()
        
        if merged_df.empty:
            print("❌ Merge produced no data")
            return False
        
        # Save merged data
        output_file = self.save_merged_data(merged_df)
        if not output_file:
            return False
        
        print("-" * 50)
        print("Batch merge done!")
        return True
    
    # Skip list methods to avoid duplicate logic


def main():
    """Main"""
    parser = argparse.ArgumentParser(description='Batch merge generated CSV files (config-driven)')
    parser.add_argument('--config', '-c', type=str, default=None, help='Path to config (default: integ_merger_config.json)')
    args = parser.parse_args()

    merger = BatchMerger(args.config)
    success = merger.run_batch_merge()
    print("\n🎉 Batch merge completed successfully!" if success else "\n❌ Batch merge failed!")


if __name__ == "__main__":
    main()
