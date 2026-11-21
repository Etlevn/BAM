"""Merge per-row NLP JSON files into <stem>_nlp.csv."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.nlp.utils import filter_sgl_rows, session_id
from src.support.progress import track


def merge_nlp_results(input_csv: Path, nlp_dir: Path, output_csv: Path) -> Path:
    if not input_csv.is_file():
        raise FileNotFoundError(f"Input file not found: {input_csv}")

    # keep_default_na=False: preserve integ's literal "nan" in bas (and similar).
    df = pd.read_csv(input_csv, dtype=str, keep_default_na=False)
    df = filter_sgl_rows(df, label="nlp merge")
    df["plan_nlp"] = None
    df["insight_nlp"] = None

    if not nlp_dir.is_dir():
        print(f"[merge] NLP dir missing ({nlp_dir}); writing empty plan_nlp/insight_nlp")
    else:
        json_names = {p.name for p in nlp_dir.glob("*.json")}
        for idx, row in track(list(df.iterrows()), label="nlp merge"):
            sim = session_id(row)
            agent_id = str(row.get("llm", ""))
            round_num = str(row.get("round", ""))
            plan_name = f"{sim}_{round_num}_{agent_id}_plan.json"
            insight_name = f"{sim}_{round_num}_{agent_id}_insight.json"

            if plan_name in json_names:
                try:
                    df.at[idx, "plan_nlp"] = (nlp_dir / plan_name).read_text(
                        encoding="utf-8"
                    )
                except Exception:
                    pass
            if insight_name in json_names:
                try:
                    df.at[idx, "insight_nlp"] = (nlp_dir / insight_name).read_text(
                        encoding="utf-8"
                    )
                except Exception:
                    pass

    from src.integ.paths import write_table_csv

    write_table_csv(df, output_csv)

    total = len(df)
    plan_filled = int(df["plan_nlp"].notna().sum())
    insight_filled = int(df["insight_nlp"].notna().sum())
    both = int((df["plan_nlp"].notna() & df["insight_nlp"].notna()).sum())
    print(
        f"[merge] {output_csv.name}: plan {plan_filled}/{total}, "
        f"insight {insight_filled}/{total}, both {both}/{total}"
    )
    return output_csv
