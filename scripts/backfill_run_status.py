#!/usr/bin/env python3
"""
Backfill unified config.json status (and best-effort schema) for historical runs.

Default: dry-run. Pass --apply to write.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime import runconfig

EXP = ROOT / "exp"
GROUPS = ("SGL", "BR", "BAS")
TS_RE = re.compile(r"^\d{8}_\d{6}$")


def find_sessions() -> list[Path]:
    sessions: list[Path] = []
    for group in GROUPS:
        g = EXP / group
        if not g.is_dir():
            continue
        for series in sorted(g.iterdir()):
            if not series.is_dir() or series.name.startswith("_"):
                continue
            for p in series.rglob("*"):
                if p.is_dir() and TS_RE.match(p.name):
                    if (
                        (p / runconfig.CONFIG_FILENAME).is_file()
                        or (p / "sgl_config.json").is_file()
                        or (p / "br_config.json").is_file()
                    ):
                        sessions.append(p)
    return sessions


def legacy_to_unified(raw: dict, session: Path) -> dict:
    """Best-effort convert legacy sgl/br config into unified shape."""
    if "assignments" in raw and "models" in raw and "experiment" in raw:
        out = dict(raw)
        out.setdefault("status", "running")
        for k in ("mode", "expected", "observed", "checked_at", "model_name", "service_name"):
            out.pop(k, None)
        return out

    # Legacy sgl
    if "model_name" in raw and "assignments" not in raw:
        num = int(raw.get("num_llms") or 0)
        name = str(raw["model_name"])
        service = str(raw.get("service_name") or "")
        out = {
            "num_llms": num,
            "models": [{"name": name, "count": num, "service_name": service}],
            "assignment_strategy": None,
            "assignments": {f"llm_{i:03d}": name for i in range(1, num + 1)},
            "status": raw.get("status", "running"),
        }
        if "experiment" in raw:
            out["experiment"] = raw["experiment"]
        return out

    # Legacy br
    if "config" in raw and "assignments" in raw:
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
        out = {
            "num_llms": int(cfg.get("total_agents") or len(raw.get("assignments") or {})),
            "models": models,
            "assignment_strategy": cfg.get("assignment_strategy"),
            "assignments": {str(k): str(v) for k, v in (raw.get("assignments") or {}).items()},
            "status": raw.get("status", "running"),
        }
        if "experiment" in raw:
            out["experiment"] = raw["experiment"]
        return out

    return dict(raw)


def heuristic_status(session: Path) -> str:
    main_n = runconfig.count_output_rounds(session)
    prac = session / "prac"
    if prac.is_dir():
        prac_n = runconfig.count_output_rounds(prac)
        if main_n >= 15 and prac_n >= 3:
            return "complete"
        return "incomplete"
    if main_n >= 15:
        return "complete"
    return "incomplete"


def process_session(session: Path, apply: bool) -> dict:
    raw = runconfig.load_session_config(session)
    if raw is None:
        return {"session": str(session), "op": "skip", "reason": "no_config"}

    unified = legacy_to_unified(raw, session)
    if "experiment" in unified and (unified["experiment"] or {}).get("EXPERIMENT_CONFIG"):
        # Temporarily write so evaluate can read expected rounds
        if apply:
            runconfig.write_session_config(session, unified)
        status = runconfig.evaluate_completeness(session)
    else:
        status = heuristic_status(session)

    unified["status"] = status
    for k in ("mode", "expected", "observed", "checked_at", "model_name", "service_name"):
        unified.pop(k, None)

    info = {
        "session": str(session.relative_to(ROOT)),
        "status": status,
        "had_experiment": "experiment" in unified,
    }
    if apply:
        runconfig.write_session_config(session, unified)
        info["op"] = "wrote"
    else:
        info["op"] = "dry-run"
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    sessions = find_sessions()
    print(f"[backfill] mode={'APPLY' if args.apply else 'DRY-RUN'} sessions={len(sessions)}")
    reports = [process_session(s, args.apply) for s in sessions]
    complete = sum(1 for r in reports if r.get("status") == "complete")
    incomplete = sum(1 for r in reports if r.get("status") == "incomplete")
    print(f"[backfill] complete={complete} incomplete={incomplete}")
    out = ROOT / "scripts" / "backfill_run_status_report.json"
    out.write_text(json.dumps(reports, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[backfill] report → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
