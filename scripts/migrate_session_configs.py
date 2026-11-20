#!/usr/bin/env python3
"""
Temporary: migrate historical session configs under exp/{SGL,BR,BAS}
(skip TEST) to unified config.json, then remove legacy sgl_/br_config.json.

Default: dry-run. Pass --apply to write/delete.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from src.runtime import runconfig

EXP = ROOT / "exp"
GROUPS = ("SGL", "BR", "BAS")
TS_RE = re.compile(r"^\d{8}_\d{6}$")
BIAS_SERIES_RE = re.compile(r"^([as])(\d{2})_")
OBSOLETE = (
    "mode",
    "expected",
    "observed",
    "checked_at",
    "model_name",
    "service_name",
    "statistics",
    "description",
)


def find_sessions() -> list[Path]:
    sessions: list[Path] = []
    for group in GROUPS:
        g = EXP / group
        if not g.is_dir():
            continue
        for p in g.rglob("*"):
            if not (p.is_dir() and TS_RE.match(p.name)):
                continue
            if (
                (p / "config.json").is_file()
                or (p / "sgl_config.json").is_file()
                or (p / "br_config.json").is_file()
            ):
                sessions.append(p)
    return sorted(sessions)


def group_of(session: Path) -> str:
    try:
        return session.relative_to(EXP).parts[0]
    except ValueError:
        return "unknown"


def series_name_of(session: Path) -> str:
    parts = session.relative_to(EXP).parts
    return parts[1] if len(parts) >= 3 else ""


def infer_bas_bias(series: str) -> tuple[bool, str | None]:
    m = BIAS_SERIES_RE.match(series)
    if not m:
        return False, None
    family, num = m.group(1), m.group(2)
    return True, ("amp_" if family == "a" else "sup_") + num


def load_raw(session: Path) -> tuple[dict[str, Any] | None, str | None]:
    for name in ("config.json", "sgl_config.json", "br_config.json"):
        p = session / name
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8")), name
    return None, None


def legacy_to_unified(raw: dict[str, Any], session: Path) -> dict[str, Any]:
    group = group_of(session)
    series = series_name_of(session)

    if isinstance(raw.get("models"), list) and isinstance(raw.get("assignments"), dict):
        out: dict[str, Any] = {
            "num_llms": int(raw.get("num_llms") or len(raw["assignments"])),
            "models": [
                {
                    "name": str(m["name"]),
                    "count": int(m["count"]),
                    "service_name": str(m.get("service_name") or ""),
                }
                for m in raw["models"]
                if isinstance(m, dict) and "name" in m
            ],
            "assignment_strategy": raw.get("assignment_strategy"),
            "assignments": {str(k): str(v) for k, v in raw["assignments"].items()},
        }
    elif "model_name" in raw:
        num = int(raw.get("num_llms") or 0)
        name = str(raw["model_name"])
        service = str(raw.get("service_name") or "")
        out = {
            "num_llms": num,
            "models": [{"name": name, "count": num, "service_name": service}],
            "assignment_strategy": None,
            "assignments": {f"llm_{i:03d}": name for i in range(1, num + 1)},
        }
    elif "config" in raw and "assignments" in raw:
        cfg = raw["config"] or {}
        models = []
        for m in cfg.get("models") or []:
            models.append(
                {
                    "name": str(m["name"]),
                    "count": int(m["count"]),
                    "service_name": str(m.get("service_name") or ""),
                }
            )
        assignments = {str(k): str(v) for k, v in (raw.get("assignments") or {}).items()}
        out = {
            "num_llms": int(cfg.get("total_agents") or len(assignments)),
            "models": models,
            "assignment_strategy": cfg.get("assignment_strategy"),
            "assignments": assignments,
        }
    else:
        out = dict(raw)

    if isinstance(raw.get("experiment"), dict) and raw["experiment"].get(
        "EXPERIMENT_CONFIG"
    ):
        out["experiment"] = copy.deepcopy(raw["experiment"])
    else:
        use_bas, bias_id = infer_bas_bias(series)
        if group == "BAS" and not use_bas:
            use_bas = True
            bias_id = None
        mode = (
            "br"
            if (
                len(out.get("models") or []) > 1
                or ("config" in raw and "assignments" in raw)
                or group == "BR"
            )
            else "sgl"
        )
        # Historical runs did not store market params; attach paper defaults.
        out["experiment"] = {
            "EXP_GROUP": group,
            "EXPERIMENT_MODE": mode,
            "USE_BAS_MODE": use_bas,
            "BAS_BIAS_ID": bias_id if use_bas else None,
            "EXPERIMENT_CONFIG": copy.deepcopy(config.EXPERIMENT_CONFIG),
        }

    for k in OBSOLETE:
        out.pop(k, None)
    out.pop("config", None)
    out.pop("statistics", None)
    return out


def compute_status(session: Path, unified: dict[str, Any]) -> str:
    ec = (unified.get("experiment") or {}).get("EXPERIMENT_CONFIG") or {}
    if ec.get("total_rounds") is not None:
        return runconfig.evaluate_completeness(
            session,
            practice_rounds=int(ec.get("practice_rounds", 0) or 0),
            total_rounds=int(ec.get("total_rounds", 0) or 0),
        )
    main_n = runconfig.count_output_rounds(session)
    prac = session / "prac"
    if prac.is_dir():
        prac_n = runconfig.count_output_rounds(prac)
        return "complete" if main_n >= 15 and prac_n >= 3 else "incomplete"
    return "complete" if main_n >= 15 else "incomplete"


def process_session(session: Path, apply: bool) -> dict[str, Any]:
    raw, source = load_raw(session)
    if raw is None:
        return {
            "session": str(session.relative_to(ROOT)),
            "op": "skip",
            "reason": "no_config",
        }

    unified = legacy_to_unified(raw, session)
    unified["status"] = compute_status(session, unified)

    info: dict[str, Any] = {
        "session": str(session.relative_to(ROOT)),
        "source": source,
        "status": unified["status"],
        "num_llms": unified.get("num_llms"),
        "n_models": len(unified.get("models") or []),
    }

    legacy = [session / "sgl_config.json", session / "br_config.json"]
    # Nested leftovers from merged practice timestamp folders
    prac = session / "prac"
    if prac.is_dir():
        for name in ("sgl_config.json", "br_config.json", "config.json"):
            nested = prac / name
            if nested.is_file():
                legacy.append(nested)
    if apply:
        runconfig.write_session_config(session, unified)
        removed = []
        for p in legacy:
            if p.is_file():
                rel = str(p.relative_to(session))
                p.unlink()
                removed.append(rel)
        info["op"] = "migrated"
        info["removed"] = removed
    else:
        info["op"] = "dry-run"
        info["would_remove"] = [
            str(p.relative_to(session)) for p in legacy if p.is_file()
        ]
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write config.json and delete legacy sgl_/br_config.json",
    )
    args = parser.parse_args()

    sessions = find_sessions()
    print(
        f"[migrate-config] mode={'APPLY' if args.apply else 'DRY-RUN'} "
        f"sessions={len(sessions)}"
    )
    reports = [process_session(s, args.apply) for s in sessions]
    processed = sum(1 for r in reports if r.get("op") in {"migrated", "dry-run"})
    complete = sum(1 for r in reports if r.get("status") == "complete")
    incomplete = sum(1 for r in reports if r.get("status") == "incomplete")
    print(
        f"[migrate-config] processed={processed} "
        f"complete={complete} incomplete={incomplete}"
    )
    out = ROOT / "scripts" / "migrate_session_configs_report.json"
    out.write_text(
        json.dumps(reports, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"[migrate-config] report → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
