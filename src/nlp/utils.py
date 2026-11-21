"""Helpers for NLP evaluation: prompt, API call, validation, filenames."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from string import Template
from typing import Any

import config
from src.agents import trading as ord


def session_id(row: dict[str, Any] | Any) -> str:
    """Prefer integ `session`; accept legacy `simulation_index`."""
    if hasattr(row, "get"):
        val = row.get("session", None)
        if val is None or (isinstance(val, float) and str(val) == "nan"):
            val = row.get("simulation_index", "Unknown")
    else:
        val = getattr(row, "session", None) or getattr(
            row, "simulation_index", "Unknown"
        )
    return str(val)


def load_prompt_template(prompt_path: Path) -> str:
    if not prompt_path.is_file():
        raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def build_evaluation_prompt(
    system_prompt: str,
    evaluation_target: str,
    target_text: str,
    agent_info: dict[str, Any],
) -> str:
    lm_id = agent_info.get("llm", "N/A")
    round_num = agent_info.get("round", "N/A")
    mode = agent_info.get("mode", "N/A")

    template_str = system_prompt.replace("{LM_id}", "${LM_id}")
    template_str = template_str.replace("{round}", "${round}")
    template_str = template_str.replace("{mode}", "${mode}")
    template_str = template_str.replace("{price_info}", "${price_info}")
    template_str = template_str.replace("{recent_returns}", "${recent_returns}")
    template_str = template_str.replace("{plan_text}", "${plan_text}")
    template_str = template_str.replace("{insights_text}", "${insights_text}")

    template = Template(template_str)
    return template.safe_substitute(
        LM_id=lm_id,
        round=round_num,
        mode=mode,
        price_info="N/A",
        recent_returns="N/A",
        plan_text=target_text if evaluation_target == "plan" else "N/A",
        insights_text=target_text if evaluation_target == "insight" else "N/A",
    )


def extract_json_from_response(response_text: str) -> dict[str, Any]:
    if not response_text:
        return {"error": "Empty response"}
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    patterns = [
        r"```json\s*(.*?)\s*```",
        r"```\s*(.*?)\s*```",
        r"\{.*\}",
    ]
    for pattern in patterns:
        try:
            match = re.search(pattern, response_text, re.DOTALL)
            if match:
                json_str = match.group(1) if pattern.startswith("```") else match.group()
                return json.loads(json_str)
        except (json.JSONDecodeError, AttributeError):
            continue

    return {
        "error": "Failed to extract valid JSON",
        "raw_response": response_text[:500],
    }


def pause_on_api_error(response: Any) -> bool:
    error_detected = False
    error_details = ""
    if isinstance(response, str):
        if "Error:" in response and any(
            keyword in response
            for keyword in [
                "timeout",
                "connection",
                "network",
                "server",
                "HTTPSConnectionPool",
                "Read timed out",
                "API key",
                "rate limit",
                "quota",
                "unauthorized",
            ]
        ):
            error_detected = True
            error_details = response[:500]

    if error_detected:
        print("\n[CRITICAL] API/NETWORK ERROR DETECTED")
        print(f"Error Details: {error_details}")
        print("Program is now PAUSED due to API/network error.")
        input("Press Enter when the issue is resolved to retry...\n")
        return True
    return False


def call_llm_for_evaluation(
    prompt: str,
    model_name: str = "deepseek-chat",
    api_mode: str = "deepseek",
) -> dict[str, Any]:
    original_mode = config.API_CONFIG["api_mode"]
    config.API_CONFIG["api_mode"] = api_mode
    try:
        response = ord.chat_with_llm(prompt, model_name)
        if pause_on_api_error(response):
            print("[nlp] Retrying after API error...")
            response = ord.chat_with_llm(prompt, model_name)
        return extract_json_from_response(response)
    finally:
        config.API_CONFIG["api_mode"] = original_mode


def validate_evaluation_result(
    result: dict[str, Any], expected_mechanisms: list[str]
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if "error" in result:
        errors.append(f"API error: {result.get('error')}")
        return False, errors

    for field in ("mechanism_assessments", "behavioral_bias_summary", "summary"):
        if field not in result:
            errors.append(f"Missing required field: {field}")

    if "mechanism_assessments" in result:
        assessments = result["mechanism_assessments"]
        if not isinstance(assessments, list):
            errors.append("mechanism_assessments should be a list")
        elif len(assessments) != len(expected_mechanisms):
            errors.append(
                f"Expected {len(expected_mechanisms)} mechanisms, got {len(assessments)}"
            )
        else:
            for i, assessment in enumerate(assessments):
                if not isinstance(assessment, dict):
                    errors.append(f"Assessment {i} is not a dictionary")
                    continue
                for field in (
                    "mechanism_id",
                    "mechanism_category",
                    "label",
                    "confidence",
                    "numeric_score",
                    "evidence_sentences",
                ):
                    if field not in assessment:
                        errors.append(f"Assessment {i} missing field: {field}")

    return len(errors) == 0, errors


def generate_output_filename(
    session: str, round_num: str, agent_id: str, evaluation_target: str
) -> str:
    return f"{session}_{round_num}_{agent_id}_{evaluation_target}.json"


def save_json_result(result: dict[str, Any], output_path: Path) -> bool:
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return True
    except Exception as exc:
        print(f"  [ERROR] Failed to save JSON: {exc}")
        return False


def get_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def required_columns(df_columns: list[str] | Any) -> list[str]:
    cols = set(df_columns)
    missing: list[str] = []
    if "session" not in cols and "simulation_index" not in cols:
        missing.append("session|simulation_index")
    for col in ("round", "llm", "plan", "insight"):
        if col not in cols:
            missing.append(col)
    return missing


def filter_sgl_rows(df: Any, *, label: str = "nlp") -> Any:
    """
    Keep single-model non-BAS NLP scope: ``mode == sgl`` and ``bas == nan``.

    Legacy ``market_type`` accepted for mode. Missing ``bas`` treated as ``nan``.
    Empty / ``null`` / ``none`` bas normalized to literal ``nan``.
    """
    import pandas as pd

    if not isinstance(df, pd.DataFrame):
        raise TypeError("filter_sgl_rows expects a DataFrame")
    out = df.copy()
    mode_col = (
        "mode"
        if "mode" in out.columns
        else ("market_type" if "market_type" in out.columns else None)
    )
    if mode_col is None:
        raise ValueError(
            f"{label}: need mode or market_type to restrict NLP to sgl rows"
        )
    before = len(out)
    mode_ok = out[mode_col].astype(str).str.strip().str.lower().eq("sgl")
    if "bas" in out.columns:
        bas = out["bas"].astype(str).str.strip()
        bas_norm = bas.where(~bas.str.lower().isin({"", "null", "none", "nan"}), "nan")
        out["bas"] = bas_norm
        bas_ok = bas_norm.eq("nan")
    else:
        out["bas"] = "nan"
        bas_ok = pd.Series(True, index=out.index)
    out = out.loc[mode_ok & bas_ok].copy()
    dropped = before - len(out)
    print(
        f"[{label}] keep mode=sgl & bas=nan: {len(out)}/{before} rows "
        f"(dropped {dropped})"
    )
    if out.empty:
        raise ValueError(f"{label}: no mode=sgl & bas=nan rows after filter")
    return out.reset_index(drop=True)
