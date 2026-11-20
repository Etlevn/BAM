"""Build market-history / portfolio / forecast rows (mkt) from market.txt."""

from __future__ import annotations

import re
from typing import Optional

import pandas as pd

from src.integ.columns import LEADING_COLS, order_leading_columns
from src.integ.session import SessionMeta, input_round_dirs

_MARKET_BLOCK_HEADER = re.compile(r"^Round\s+(\d+):\s*$")

_BODY_COLS = [
    "mkt_prc",
    "mkt_vol",
    "stk_num",
    "stk_val",
    "cash",
    "div",
    "int",
    "fcst_1_rnd",
    "fcst_1_prc",
    "fcst_2_rnd",
    "fcst_2_prc",
    "fcst_3_rnd",
    "fcst_3_prc",
    "fcst_4_rnd",
    "fcst_4_prc",
]
_COLUMNS = list(LEADING_COLS) + _BODY_COLS


def parse_market_txt(text: str) -> list[dict]:
    lines = text.splitlines()
    blocks: list[tuple[int, list[str]]] = []
    curr_round: Optional[int] = None
    curr_lines: list[str] = []

    def flush() -> None:
        nonlocal curr_round, curr_lines
        if curr_round is not None:
            blocks.append((curr_round, curr_lines))
        curr_round = None
        curr_lines = []

    for raw in lines:
        m = _MARKET_BLOCK_HEADER.match(raw.strip())
        if m:
            flush()
            curr_round = int(m.group(1))
            continue
        if curr_round is not None:
            curr_lines.append(raw)
    flush()

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

    records: list[dict] = []
    for rnd, blk_lines in blocks:
        blk = "\n".join(blk_lines)
        fcst_pairs: list[tuple[Optional[int], Optional[float]]] = []
        for line in blk.splitlines():
            m = re.match(
                r"-\s*Round\s*(\d+)\s*price\s*forecast:\s*([-\d\.]+)",
                line.strip(),
                flags=re.IGNORECASE,
            )
            if not m:
                continue
            try:
                r_val = int(m.group(1))
            except Exception:
                r_val = None
            try:
                p_val = float(m.group(2))
            except Exception:
                p_val = None
            fcst_pairs.append((r_val, p_val))

        fcst_pairs = fcst_pairs[:4]
        while len(fcst_pairs) < 4:
            fcst_pairs.append((None, None))

        records.append(
            {
                "round": rnd,
                "mkt_prc": extract_float(r"Market\s+price:\s*([\d\.]+)", blk),
                "mkt_vol": extract_int(r"Market\s+volume:\s*([\d\.]+)", blk),
                "stk_num": extract_int(r"#\s*of\s*shares\s*owned:\s*([-\d\.]+)", blk),
                "cash": extract_float(r"Current\s+cash:\s*([-\d\.]+)", blk),
                "stk_val": extract_float(r"Stock\s+value:\s*([-\d\.]+)", blk),
                "div": extract_float(r"Dividend\s+earned:\s*([-\d\.]+)", blk),
                "int": extract_float(r"Interest\s+earned:\s*([-\d\.]+)", blk),
                "fcst_1_rnd": fcst_pairs[0][0],
                "fcst_1_prc": fcst_pairs[0][1],
                "fcst_2_rnd": fcst_pairs[1][0],
                "fcst_2_prc": fcst_pairs[1][1],
                "fcst_3_rnd": fcst_pairs[2][0],
                "fcst_3_prc": fcst_pairs[2][1],
                "fcst_4_rnd": fcst_pairs[3][0],
                "fcst_4_prc": fcst_pairs[3][1],
            }
        )
    return records


def build_snapshots(meta: SessionMeta) -> pd.DataFrame:
    rounds = input_round_dirs(meta.path)
    if not rounds:
        return pd.DataFrame(columns=_COLUMNS)
    target_round = rounds[-1]
    input_dir = meta.path / "input" / f"r{target_round}"
    if not input_dir.is_dir():
        return pd.DataFrame(columns=_COLUMNS)

    records: list[dict] = []
    for txt_path in sorted(input_dir.glob(f"llm_*_r{target_round}_market.txt")):
        llm_name = txt_path.name.split("_r")[0]
        try:
            text = txt_path.read_text(encoding="utf-8")
        except Exception:
            continue
        for rr in parse_market_txt(text):
            rnum = rr.get("round")
            if not isinstance(rnum, int) or rnum < 1 or rnum > target_round:
                continue
            records.append(
                {
                    "group": meta.group,
                    "simulation_index": meta.simulation_index,
                    "bas": meta.bas,
                    "market_type": meta.market_type,
                    "round": rnum,
                    "llm": llm_name,
                    "llm_type": meta.assignments.get(llm_name),
                    "mkt_prc": rr.get("mkt_prc"),
                    "mkt_vol": rr.get("mkt_vol"),
                    "stk_num": rr.get("stk_num"),
                    "stk_val": rr.get("stk_val"),
                    "cash": rr.get("cash"),
                    "div": rr.get("div"),
                    "int": rr.get("int"),
                    "fcst_1_rnd": rr.get("fcst_1_rnd"),
                    "fcst_1_prc": rr.get("fcst_1_prc"),
                    "fcst_2_rnd": rr.get("fcst_2_rnd"),
                    "fcst_2_prc": rr.get("fcst_2_prc"),
                    "fcst_3_rnd": rr.get("fcst_3_rnd"),
                    "fcst_3_prc": rr.get("fcst_3_prc"),
                    "fcst_4_rnd": rr.get("fcst_4_rnd"),
                    "fcst_4_prc": rr.get("fcst_4_prc"),
                }
            )

    if not records:
        return pd.DataFrame(columns=_COLUMNS)
    return order_leading_columns(pd.DataFrame.from_records(records, columns=_COLUMNS))
