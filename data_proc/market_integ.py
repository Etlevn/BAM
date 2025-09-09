#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
市场文本整合脚本
读取 experiment_directory 下所有正式轮 simulation_index 的 r20 市场文本
并整合为结构化 CSV。
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pandas as pd


# 配置仅从JSON读取；不在脚本内提供默认常量


class MarketTxtIntegrator:
    """将 r20 的 llm_xxx_r20_market.txt 转为结构化 CSV 的整合器。"""

    def __init__(self, config_file: Optional[str] = None):
        self.config = self._load_config(config_file)
        self.root_dir = Path(self.config['root_directory'])
        self.exp_dir = self.root_dir / self.config['experiment_directory']

    def _load_config(self, config_file: Optional[str]) -> Dict:
        """
        支持单一 JSON 中包含 br 与 sgl 两个分支的配置：
        {
          "market_type": "br",
          "br": { "root_directory": "...", "experiment_directory": "...", "output_filename": "..." },
          "sgl": { "root_directory": "...", "experiment_directory": "...", "sgl_llm_type": "..." }
        }
        """
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
                # target_round 可省略，将自动检测
            }
            if market_type == 'sgl':
                merged['sgl_llm_type'] = external.get('sgl_llm_type')
            missing = [k for k in ['root_directory', 'experiment_directory', 'output_filename'] if not merged.get(k)]
            if missing:
                raise ValueError("配置缺少必要字段: " + ", ".join(missing))
            return merged
        else:
            # 未提供配置文件则尝试同目录默认文件
            default_cfg = Path(__file__).with_name('market_integ_config.json')
            if default_cfg.exists():
                return self._load_config(str(default_cfg))
            raise ValueError('未提供配置文件，且默认配置文件不存在: market_integ_config.json')

    # ---------------------------------------------------------------------
    # 发现 simulation_index（以 20 开头的目录）并筛选正式轮（market 下 r1..r20）
    # ---------------------------------------------------------------------
    def discover_formal_simulation_indices(self) -> List[str]:
        if not self.exp_dir.exists():
            return []

        indices: List[str] = []
        for item in self.exp_dir.iterdir():
            if not item.is_dir() or not item.name.startswith('20'):
                continue
            market_dir = item / 'market'
            if not market_dir.exists():
                continue
            # 统计严格形如 r{数字}.csv 的文件，例如 r1.csv ... rN.csv
            rounds = []
            for p in market_dir.glob('r*.csv'):
                m = re.fullmatch(r"r(\d+)\.csv", p.name)
                if m:
                    try:
                        rounds.append(int(m.group(1)))
                    except Exception:
                        pass
            rounds = sorted(set(rounds))
            # 认为“正式轮”：从1开始连续，且最大轮 >= 20
            if rounds and rounds == list(range(1, rounds[-1] + 1)) and rounds[-1] >= 20:
                indices.append(item.name)

        return sorted(indices)

    # ---------------------------------------------------------------------
    # 读取 battle_royale_config.json 获取 llm->type 映射（BR 模式）
    # 或从配置获取（SGL 模式）
    # ---------------------------------------------------------------------
    def get_llm_type_mapping(self, simulation_index: str) -> Dict[str, str]:
        market_type = self.config.get('market_type', 'br')
        if market_type == 'sgl':
            # SGL：所有 LLM 使用同一个名称（sgl_llm_type）
            sgl_llm_type = self.config.get('sgl_llm_type')
            if not isinstance(sgl_llm_type, str) or not sgl_llm_type:
                raise ValueError('sgl 模式需要在配置中提供 sgl_llm_type')
            return {f'llm_{i:03d}': sgl_llm_type for i in range(1, 21)}

        # BR：从 battle_royale_config.json 读取 assignments
        config_file = self.exp_dir / simulation_index / 'battle_royale_config.json'
        if not config_file.exists():
            return {}
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                battle_cfg = json.load(f)
            return battle_cfg.get('assignments', {})
        except Exception:
            return {}

    # ---------------------------------------------------------------------
    # 解析单个 market.txt 文本为结构化字典
    # ---------------------------------------------------------------------
    MARKET_BLOCK_HEADER = re.compile(r'^Round\s+(\d+):\s*$')

    def parse_market_txt(self, text: str) -> List[Dict]:
        """
        解析整个 market.txt 文件，返回每个 Round 的结构化记录。

        返回列表的元素包含：
        - round: int
        - mkt_prc, mkt_vol, stk_num, stk_val, cash, div, int: float
        - forecasts: List[Tuple[int, float]] 最多 4 组（若不足填 None）
        """
        lines = text.splitlines()

        # 聚合为各个 Round 块
        blocks: List[Tuple[int, List[str]]] = []
        curr_round: Optional[int] = None
        curr_lines: List[str] = []

        def flush_block():
            nonlocal curr_round, curr_lines
            if curr_round is not None:
                blocks.append((curr_round, curr_lines))
            curr_round = None
            curr_lines = []

        for raw in lines:
            m = self.MARKET_BLOCK_HEADER.match(raw.strip())
            if m:
                flush_block()
                curr_round = int(m.group(1))
                continue
            if curr_round is not None:
                curr_lines.append(raw)
        flush_block()

        records: List[Dict] = []

        # 提取字段
        def extract_float(pattern: str, block_text: str) -> Optional[float]:
            mm = re.search(pattern, block_text, flags=re.IGNORECASE)
            if not mm:
                return None
            try:
                return float(mm.group(1))
            except Exception:
                return None

        def extract_int(pattern: str, block_text: str) -> Optional[int]:
            mm = re.search(pattern, block_text, flags=re.IGNORECASE)
            if not mm:
                return None
            try:
                return int(float(mm.group(1)))
            except Exception:
                return None

        for rnd, blk_lines in blocks:
            blk = "\n".join(blk_lines)

            # Market + Portfolio Data 段：不同文件中字段命名有小差异，这里做鲁棒匹配
            mkt_prc = extract_float(r"Market\s+price:\s*([\d\.]+)", blk)
            mkt_vol = extract_int(r"Market\s+volume:\s*([\d\.]+)", blk)
            stk_num = extract_int(r"#\s*of\s*shares\s*owned:\s*([-\d\.]+)", blk)
            cash    = extract_float(r"Current\s+cash:\s*([-\d\.]+)", blk)
            stk_val = extract_float(r"Stock\s+value:\s*([-\d\.]+)", blk)
            div     = extract_float(r"Dividend\s+earned:\s*([-\d\.]+)", blk)
            intr    = extract_float(r"Interest\s+earned:\s*([-\d\.]+)", blk)

            # Forecasts 段：匹配行 "- Round X price forecast: Y"
            fcst_pairs: List[Tuple[Optional[int], Optional[float]]] = []
            for line in blk.splitlines():
                line_stripped = line.strip()
                m = re.match(r"-\s*Round\s*(\d+)\s*price\s*forecast:\s*([-\d\.]+)", line_stripped, flags=re.IGNORECASE)
                if m:
                    try:
                        r_val = int(m.group(1))
                    except Exception:
                        r_val = None
                    try:
                        p_val = float(m.group(2))
                    except Exception:
                        p_val = None
                    fcst_pairs.append((r_val, p_val))

            # 仅保留前 4 组，若不足 4 组用 None 填充
            fcst_pairs = fcst_pairs[:4]
            while len(fcst_pairs) < 4:
                fcst_pairs.append((None, None))

            records.append({
                'round': rnd,
                'mkt_prc': mkt_prc,
                'mkt_vol': mkt_vol,
                'stk_num': stk_num,
                'stk_val': stk_val,
                'cash': cash,
                'div': div,
                'int': intr,
                'fcst_1_rnd': fcst_pairs[0][0],
                'fcst_1_prc': fcst_pairs[0][1],
                'fcst_2_rnd': fcst_pairs[1][0],
                'fcst_2_prc': fcst_pairs[1][1],
                'fcst_3_rnd': fcst_pairs[2][0],
                'fcst_3_prc': fcst_pairs[2][1],
                'fcst_4_rnd': fcst_pairs[3][0],
                'fcst_4_prc': fcst_pairs[3][1],
            })

        return records

    # ---------------------------------------------------------------------
    # 处理单个 simulation_index：读取 r20 下所有 llm_*_r20_market.txt 并整合
    # ---------------------------------------------------------------------
    def integrate_single_simulation(self, simulation_index: str) -> pd.DataFrame:
        # 自动检测最大轮次：扫描 input 下的 r{N} 目录，取最大 N
        input_root = self.exp_dir / simulation_index / 'input'
        max_round = 0
        if input_root.exists():
            for d in input_root.iterdir():
                if d.is_dir():
                    m = re.fullmatch(r"r(\d+)", d.name)
                    if m:
                        try:
                            max_round = max(max_round, int(m.group(1)))
                        except Exception:
                            pass
        if max_round <= 0:
            return pd.DataFrame()
        target_round = max_round
        input_dir = input_root / f'r{target_round}'
        if not input_dir.exists():
            return pd.DataFrame()

        # 读取 LLM 类型映射
        llm_type_map = self.get_llm_type_mapping(simulation_index)
        market_type = self.config.get('market_type', 'br')

        records: List[Dict] = []

        for txt_path in sorted(input_dir.glob(f'llm_*_r{target_round}_market.txt')):
            llm_name = txt_path.name.split('_r')[0]

            try:
                text = txt_path.read_text(encoding='utf-8')
            except Exception:
                continue

            per_round = self.parse_market_txt(text)

            # 展开所有历史轮（不含 Round 0），上限为 target_round
            for rr in per_round:
                rnum = rr.get('round')
                if not isinstance(rnum, int):
                    continue
                if rnum < 1 or rnum > target_round:
                    continue

                row = {
                    'llm': llm_name,
                    'mkt_prc': rr.get('mkt_prc'),
                    'mkt_vol': rr.get('mkt_vol'),
                    'stk_num': rr.get('stk_num'),
                    'stk_val': rr.get('stk_val'),
                    'cash': rr.get('cash'),
                    'div': rr.get('div'),
                    'int': rr.get('int'),
                    'fcst_1_rnd': rr.get('fcst_1_rnd'),
                    'fcst_1_prc': rr.get('fcst_1_prc'),
                    'fcst_2_rnd': rr.get('fcst_2_rnd'),
                    'fcst_2_prc': rr.get('fcst_2_prc'),
                    'fcst_3_rnd': rr.get('fcst_3_rnd'),
                    'fcst_3_prc': rr.get('fcst_3_prc'),
                    'fcst_4_rnd': rr.get('fcst_4_rnd'),
                    'fcst_4_prc': rr.get('fcst_4_prc'),
                    'llm_type': llm_type_map.get(llm_name),
                    'market_type': market_type,
                    'round': rnum,
                    'simulation_index': simulation_index,
                }

                records.append(row)

        if not records:
            return pd.DataFrame()

        # 按用户指定列顺序构建 DataFrame
        columns = [
            'llm',
            'mkt_prc', 'mkt_vol', 'stk_num', 'stk_val', 'cash', 'div', 'int',
            'fcst_1_rnd', 'fcst_1_prc', 'fcst_2_rnd', 'fcst_2_prc',
            'fcst_3_rnd', 'fcst_3_prc', 'fcst_4_rnd', 'fcst_4_prc',
            'llm_type', 'market_type', 'round', 'simulation_index'
        ]

        df = pd.DataFrame.from_records(records, columns=columns)
        return df

    # ---------------------------------------------------------------------
    # 扫描所有正式轮 simulation_index 并输出 CSV
    # ---------------------------------------------------------------------
    def run(self) -> None:
        sims = self.discover_formal_simulation_indices()
        if not sims:
            print('未发现正式轮 simulation_index')
            return

        for sim in sims:
            df = self.integrate_single_simulation(sim)
            if df.empty:
                print(f'跳过 {sim}: r20 市场文本未能整合')
                continue

            out_file = self.exp_dir / sim / 'market' / self.config['output_filename']
            out_file.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(out_file, index=False, encoding='utf-8')
            print(f'已保存: {out_file}')


def main():
    import argparse
    parser = argparse.ArgumentParser(description='整合 r20 市场文本为 CSV')
    parser.add_argument('--config', '-c', type=str, default=None, help='配置文件路径（单一 JSON，包含 br 与 sgl 分支）')
    # 所有配置仅从JSON中读取，不提供覆盖参数
    args = parser.parse_args()

    # 若未提供 --config，则默认使用脚本同目录下的 market_txt_integration_config.json
    # 从而支持直接运行：python market_txt_integration.py
    if not args.config:
        from pathlib import Path as _P
        default_cfg = _P(__file__).with_name('market_integ_config.json')
        if default_cfg.exists():
            args.config = str(default_cfg)

    integrator = MarketTxtIntegrator(
        config_file=args.config,
    )
    integrator.run()


if __name__ == '__main__':
    main()


