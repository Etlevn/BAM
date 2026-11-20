"""Detect rows missing plan/insight JSON under nlp/."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.nlp.utils import session_id
from src.support.progress import track


def check_missing(input_csv: Path, nlp_dir: Path, output_csv: Path) -> Path | None:
    if not input_csv.is_file():
        raise FileNotFoundError(f"Input file not found: {input_csv}")

    # keep_default_na=False: preserve integ's literal "null" in bas (and similar).
    df = pd.read_csv(input_csv, dtype=str, keep_default_na=False)
    if not nlp_dir.is_dir():
        print(f"[miss] NLP dir missing ({nlp_dir}); treating all rows as missing")
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_csv, index=False, encoding="utf-8")
        print(f"[miss] Saved {len(df)} rows → {output_csv}")
        return output_csv

    missing_plan: list[int] = []
    missing_insight: list[int] = []
    missing_both: list[int] = []

    for idx, row in track(list(df.iterrows()), label="nlp miss"):
        sim = session_id(row)
        agent_id = str(row.get("llm", ""))
        round_num = str(row.get("round", ""))
        has_plan = (nlp_dir / f"{sim}_{round_num}_{agent_id}_plan.json").is_file()
        has_insight = (nlp_dir / f"{sim}_{round_num}_{agent_id}_insight.json").is_file()
        if not has_plan:
            missing_plan.append(idx)
        if not has_insight:
            missing_insight.append(idx)
        if not has_plan and not has_insight:
            missing_both.append(idx)

    total = len(df)
    complete = total - len(missing_both)
    print(
        f"[miss] complete {complete}/{total}; "
        f"missing plan {len(missing_plan)}; insight {len(missing_insight)}; "
        f"both {len(missing_both)}"
    )

    missing_indices = sorted(set(missing_plan + missing_insight))
    if not missing_indices:
        print("[miss] No missing data")
        return None

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.iloc[missing_indices].to_csv(output_csv, index=False, encoding="utf-8")
    print(f"[miss] Saved {len(missing_indices)} rows → {output_csv}")
    return output_csv
