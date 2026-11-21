"""Build obs/plan/insight rows from output/r*/llm_*.json."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from src.integ.columns import order_leading_columns
from src.integ.session import SessionMeta, output_round_dirs

_LLM_JSON_RE = re.compile(r"llm_(\d+)_r\d+\.json")


def _parse_json_file(json_file: Path) -> dict[str, str]:
    try:
        data = json.loads(json_file.read_text(encoding="utf-8"))
    except Exception:
        return {"obs": "", "plan": "", "insight": ""}

    obs = data.get("observations_and_thoughts", "") or ""
    plan = ""
    insight = ""
    new_content = data.get("new_content", {})
    if isinstance(new_content, dict):
        plan = new_content.get("PLANS.txt", "") or ""
        insight = new_content.get("INSIGHTS.txt", "") or ""
    return {"obs": obs, "plan": plan, "insight": insight}


def build_outputs(meta: SessionMeta) -> pd.DataFrame:
    rounds = output_round_dirs(meta.path)
    if not rounds:
        return pd.DataFrame()

    rows: list[dict] = []
    output_dir = meta.path / "output"
    for round_num in rounds:
        round_dir = output_dir / f"r{round_num}"
        if not round_dir.is_dir():
            continue
        for json_file in sorted(round_dir.glob("llm_*.json")):
            match = _LLM_JSON_RE.fullmatch(json_file.name)
            if not match:
                continue
            llm_name = f"llm_{match.group(1).zfill(3)}"
            parsed = _parse_json_file(json_file)
            rows.append(
                {
                    "group": meta.group,
                    "series": meta.series,
                    "session": meta.simulation_index,
                    "bas": meta.bas,
                    "mode": meta.mode,
                    "round": round_num,
                    "llm": llm_name,
                    "llm_type": meta.assignments.get(llm_name, "unknown"),
                    "obs": parsed["obs"],
                    "plan": parsed["plan"],
                    "insight": parsed["insight"],
                }
            )

    if not rows:
        return pd.DataFrame()
    return order_leading_columns(pd.DataFrame(rows))
