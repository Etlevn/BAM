#!/usr/bin/env python3
"""
Temporary one-shot migrator for historical exp/ layouts.

Default: dry-run. Pass --apply to move/rename on disk.
Report: scripts/migrate_exp_report.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "exp"
REPORT_PATH = ROOT / "scripts" / "migrate_exp_report.json"

GROUPS = ("SGL", "BR", "BAS")
SKIP_GROUP = {"TEST"}
TS_RE = re.compile(r"^\d{8}_\d{6}$")
BIAS_RE = re.compile(r"^([ASasBb])[_-]?(\d+)$")


@dataclass
class RunInfo:
    path: Path
    ts: datetime
    rounds: int
    kind: str  # prac | main | other
    cfg_name: str | None
    cfg_key: str | None


def parse_ts(name: str) -> datetime:
    return datetime.strptime(name, "%Y%m%d_%H%M%S")


def round_count(run: Path) -> int:
    out = run / "output"
    if not out.is_dir():
        return -1
    n = 0
    for p in out.iterdir():
        if p.is_dir() and p.name.startswith("r") and p.name[1:].isdigit():
            n += 1
    return n


def load_cfg(run: Path) -> tuple[str | None, dict[str, Any] | None]:
    for name in ("sgl_config.json", "br_config.json"):
        p = run / name
        if p.is_file():
            try:
                return name, json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return name, None
    return None, None


def cfg_key(cfg: dict[str, Any] | None) -> str | None:
    if cfg is None:
        return None
    # Drop description noise if present
    cleaned = {k: v for k, v in cfg.items() if k != "description"}
    return json.dumps(cleaned, sort_keys=True, ensure_ascii=False)


def classify_rounds(n: int) -> str:
    if n < 0:
        return "other"
    if n <= 5:
        return "prac"
    if n >= 15:
        return "main"
    return "other"


def list_timestamp_runs(leaf: Path) -> list[RunInfo]:
    runs: list[RunInfo] = []
    if not leaf.is_dir():
        return runs
    for p in sorted(leaf.iterdir()):
        if not p.is_dir() or not TS_RE.match(p.name):
            continue
        # Already migrated?
        if (p / "prac").is_dir():
            # Treat as main session already unified
            rc = round_count(p)
            name, cfg = load_cfg(p)
            runs.append(
                RunInfo(
                    path=p,
                    ts=parse_ts(p.name),
                    rounds=rc,
                    kind="main" if rc >= 15 or rc < 0 else classify_rounds(rc),
                    cfg_name=name,
                    cfg_key=cfg_key(cfg),
                )
            )
            continue
        rc = round_count(p)
        name, cfg = load_cfg(p)
        runs.append(
            RunInfo(
                path=p,
                ts=parse_ts(p.name),
                rounds=rc,
                kind=classify_rounds(rc),
                cfg_name=name,
                cfg_key=cfg_key(cfg),
            )
        )
    return runs


def pair_runs(runs: list[RunInfo]) -> tuple[list[tuple[RunInfo, RunInfo]], list[RunInfo]]:
    """Return (pairs, orphans). Prefer order-preserving zip within cfg groups."""
    orphans: list[RunInfo] = [r for r in runs if r.kind == "other"]
    pracs = [r for r in runs if r.kind == "prac"]
    mains = [r for r in runs if r.kind == "main"]

    # Skip mains that already have prac/
    pending_mains = [m for m in mains if not (m.path / "prac").is_dir()]
    already = [m for m in mains if (m.path / "prac").is_dir()]

    pairs: list[tuple[RunInfo, RunInfo]] = []
    used_prac: set[Path] = set()

    # Group by cfg_key (None bucket separate)
    cfg_groups: dict[str | None, list[RunInfo]] = {}
    for m in pending_mains:
        cfg_groups.setdefault(m.cfg_key, []).append(m)

    for key, group_mains in cfg_groups.items():
        group_pracs = [
            p for p in pracs if p.cfg_key == key and p.path not in used_prac
        ]
        # Also allow pairing when one side missing cfg but both None
        group_mains = sorted(group_mains, key=lambda r: r.ts)
        group_pracs = sorted(group_pracs, key=lambda r: r.ts)

        zipped = False
        n = min(len(group_pracs), len(group_mains))
        if n > 0 and all(group_pracs[i].ts < group_mains[i].ts for i in range(n)):
            # If counts equal or we take first n of each — require equal for zip purity
            if len(group_pracs) == len(group_mains):
                for i in range(n):
                    pairs.append((group_pracs[i], group_mains[i]))
                    used_prac.add(group_pracs[i].path)
                zipped = True

        if not zipped:
            for m in group_mains:
                best: tuple[float, RunInfo] | None = None
                for p in group_pracs:
                    if p.path in used_prac:
                        continue
                    if p.cfg_key != m.cfg_key:
                        continue
                    if p.ts >= m.ts:
                        continue
                    gap = (m.ts - p.ts).total_seconds()
                    if best is None or gap < best[0]:
                        best = (gap, p)
                if best is None:
                    orphans.append(m)
                else:
                    pairs.append((best[1], m))
                    used_prac.add(best[1].path)

    for p in pracs:
        if p.path not in used_prac:
            orphans.append(p)
    # already-unified mains are fine (not orphans)
    _ = already
    return pairs, orphans


def parse_bias_token(token: str) -> str | None:
    """A1 / A-1 / S2 / S-2 / a01 → a01 / s02. Bare A_name → None."""
    t = token.strip()
    m = BIAS_RE.match(t)
    if not m:
        # A_claude... or A_gpt-4o VS ...
        m2 = re.match(r"^([ASasBb])_(.+)$", t)
        if m2:
            return None
        return None
    letter = m.group(1).lower()
    num = int(m.group(2))
    if letter == "a":
        return f"a{num:02d}"
    if letter == "s":
        return f"s{num:02d}"
    # B_ unknown → None
    return None


def br_series_name(name: str) -> str:
    return re.sub(r"\s+VS\s+", " & ", name, flags=re.IGNORECASE)


def is_skipped_series(name: str) -> bool:
    if name.startswith("_") or name.startswith("."):
        return True
    if name in {"+", "BAS"}:  # nested BAS container handled separately
        return True
    if name.endswith(".csv") or name.endswith(".json"):
        return True
    return False


def discover_leaves() -> list[dict[str, Any]]:
    """
    Each leaf: {
      group, leaf_path, target_series_name | None, rename_note
    }
    """
    leaves: list[dict[str, Any]] = []

    # --- SGL ---
    sgl = EXP / "SGL"
    if sgl.is_dir():
        for series in sorted(sgl.iterdir()):
            if not series.is_dir() or is_skipped_series(series.name):
                continue
            # has timestamps?
            if any(TS_RE.match(c.name) for c in series.iterdir() if c.is_dir()):
                leaves.append(
                    {
                        "group": "SGL",
                        "leaf": series,
                        "target_series": series.name,
                        "note": "sgl_keep",
                    }
                )

    # --- BR ---
    br = EXP / "BR"
    if br.is_dir():
        for series in sorted(br.iterdir()):
            if not series.is_dir() or is_skipped_series(series.name):
                continue
            if not any(TS_RE.match(c.name) for c in series.iterdir() if c.is_dir()):
                # maybe nested like "+"/subseries
                continue
            leaves.append(
                {
                    "group": "BR",
                    "leaf": series,
                    "target_series": br_series_name(series.name),
                    "note": "br_vs_to_amp",
                }
            )

    # --- BAS model/bias ---
    bas = EXP / "BAS"
    if bas.is_dir():
        for model in sorted(bas.iterdir()):
            if not model.is_dir() or model.name.startswith("_") or model.name.startswith("."):
                continue
            if model.name == "BAS":
                # nested BAS/BAS/{A_xxx|S_xxx} — usually no numeric bias id
                for sub in sorted(model.iterdir()):
                    if not sub.is_dir() or sub.name.startswith("_"):
                        continue
                    if not any(
                        TS_RE.match(c.name) for c in sub.iterdir() if c.is_dir()
                    ):
                        continue
                    bias = parse_bias_token(sub.name)
                    if bias is not None:
                        # rare: A_01_model style
                        rest = sub.name
                        m = re.match(r"^[ASas][_-]?\d+_(.+)$", sub.name)
                        rest = m.group(1) if m else sub.name
                        leaves.append(
                            {
                                "group": "BAS",
                                "leaf": sub,
                                "target_series": f"{bias}_{br_series_name(rest)}",
                                "note": "bas_nested_with_id",
                            }
                        )
                    else:
                        leaves.append(
                            {
                                "group": "BAS",
                                "leaf": sub,
                                "target_series": None,
                                "note": f"bas_nested_no_id:{sub.name}",
                                "orphan_reason": "bas_prefix_without_numeric_id",
                            }
                        )
                continue

            # model / A1 / timestamps
            if any(TS_RE.match(c.name) for c in model.iterdir() if c.is_dir()):
                # timestamps directly under model — treat as non-BAS-prefixed series
                leaves.append(
                    {
                        "group": "BAS",
                        "leaf": model,
                        "target_series": model.name,
                        "note": "bas_model_flat",
                    }
                )
                continue

            for bias_dir in sorted(model.iterdir()):
                if not bias_dir.is_dir() or bias_dir.name.startswith("_"):
                    continue
                if bias_dir.name == "plots":
                    continue
                if not any(TS_RE.match(c.name) for c in bias_dir.iterdir() if c.is_dir()):
                    continue
                bias = parse_bias_token(bias_dir.name)
                if bias is None:
                    leaves.append(
                        {
                            "group": "BAS",
                            "leaf": bias_dir,
                            "target_series": None,
                            "note": f"bas_bad_bias:{bias_dir.name}",
                            "orphan_reason": f"unparsed_bias:{bias_dir.name}",
                        }
                    )
                else:
                    leaves.append(
                        {
                            "group": "BAS",
                            "leaf": bias_dir,
                            "target_series": f"{bias}_{model.name}",
                            "note": "bas_flatten",
                        }
                    )

    return leaves


def ensure_dir(path: Path, apply: bool) -> None:
    if apply:
        path.mkdir(parents=True, exist_ok=True)


def move_path(src: Path, dst: Path, apply: bool, actions: list[dict[str, str]]) -> None:
    if src.resolve() == dst.resolve():
        actions.append({"op": "keep", "src": str(src), "dst": str(dst)})
        return
    if dst.exists():
        # Idempotent / collision: skip leaving source for manual review
        actions.append(
            {
                "op": "skip",
                "src": str(src),
                "dst": str(dst),
                "reason": "destination_exists",
            }
        )
        return
    actions.append({"op": "move", "src": str(src), "dst": str(dst)})
    if not apply:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))


def merge_pair(prac: RunInfo, main: RunInfo, apply: bool, actions: list[dict[str, str]]) -> None:
    dest = main.path / "prac"
    if dest.exists():
        actions.append(
            {
                "op": "skip",
                "src": str(prac.path),
                "dst": str(dest),
                "reason": "main_already_has_prac",
            }
        )
        return
    move_path(prac.path, dest, apply, actions)


def relocate_session(
    session: Path,
    group: str,
    target_series: str | None,
    apply: bool,
    actions: list[dict[str, str]],
    orphan_reason: str | None = None,
    orphan_leaf_name: str | None = None,
) -> Path:
    """Move session timestamp dir into target series (or _orphan)."""
    if target_series:
        dest_parent = EXP / group / target_series
    else:
        # keep relative hint under orphan
        parts = [EXP / group / "_orphan", orphan_reason or "unknown"]
        if orphan_leaf_name:
            parts.append(Path(orphan_leaf_name))
        dest_parent = parts[0]
        for part in parts[1:]:
            dest_parent = dest_parent / part
    dest = dest_parent / session.name
    if session.resolve() == dest.resolve():
        actions.append({"op": "keep", "src": str(session), "dst": str(dest)})
        return session
    # same parent rename only
    if session.parent.resolve() == dest_parent.resolve() and session.name == dest.name:
        return session
    move_path(session, dest, apply, actions)
    return dest


def cleanup_empty(path: Path, apply: bool, actions: list[dict[str, str]], stop_at: Path) -> None:
    """Remove empty dirs up toward stop_at (exclusive)."""
    cur = path
    while cur != stop_at and cur.is_relative_to(stop_at):
        if not cur.exists():
            cur = cur.parent
            continue
        try:
            remaining = [p for p in cur.iterdir() if p.name != ".DS_Store"]
        except FileNotFoundError:
            break
        # remove .DS_Store if only junk left
        ds = cur / ".DS_Store"
        if ds.exists() and apply:
            try:
                ds.unlink()
            except OSError:
                pass
            remaining = [p for p in cur.iterdir()]
        if remaining:
            break
        actions.append({"op": "rmdir", "src": str(cur), "dst": ""})
        if apply:
            try:
                cur.rmdir()
            except OSError:
                break
        cur = cur.parent


def process_leaf(leaf_info: dict[str, Any], apply: bool) -> dict[str, Any]:
    leaf: Path = leaf_info["leaf"]
    group: str = leaf_info["group"]
    target_series: str | None = leaf_info.get("target_series")
    actions: list[dict[str, str]] = []
    runs = list_timestamp_runs(leaf)

    # If every main already has prac and no bare prac left, just relocate
    pairs, orphans = pair_runs(runs)

    report = {
        "leaf": str(leaf),
        "group": group,
        "target_series": target_series,
        "note": leaf_info.get("note"),
        "n_runs": len(runs),
        "n_pairs": len(pairs),
        "n_orphans": len(orphans),
        "pairs": [],
        "orphans": [],
        "actions": actions,
    }

    for prac, main in pairs:
        report["pairs"].append(
            {
                "prac": prac.path.name,
                "main": main.path.name,
                "prac_rounds": prac.rounds,
                "main_rounds": main.rounds,
                "cfg_match": prac.cfg_key == main.cfg_key,
            }
        )
        merge_pair(prac, main, apply, actions)
        # relocate unified main
        new_main = relocate_session(
            main.path,
            group,
            target_series,
            apply,
            actions,
            orphan_reason=leaf_info.get("orphan_reason"),
            orphan_leaf_name=leaf.name if target_series is None else None,
        )
        # if leaf empty later
        _ = new_main

    for o in orphans:
        report["orphans"].append(
            {
                "name": o.path.name,
                "kind": o.kind,
                "rounds": o.rounds,
            }
        )
        # If orphan is a main without prac, still relocate to target/orphan
        if o.kind == "main" and target_series:
            relocate_session(o.path, group, target_series, apply, actions)
        else:
            relocate_session(
                o.path,
                group,
                None,
                apply,
                actions,
                orphan_reason=leaf_info.get("orphan_reason")
                or f"unpaired_{o.kind}",
                orphan_leaf_name=leaf.name,
            )

    # Non-timestamp leftovers (e.g. plots): move beside target series if flattening BAS
    if apply or True:
        for child in list(leaf.iterdir()) if leaf.exists() else []:
            if child.name.startswith("."):
                continue
            if TS_RE.match(child.name):
                continue
            if child.name == "prac":
                continue
            # plots etc.
            if target_series:
                dest = EXP / group / target_series / child.name
            else:
                dest = (
                    EXP
                    / group
                    / "_orphan"
                    / (leaf_info.get("orphan_reason") or "misc")
                    / leaf.name
                    / child.name
                )
            if child.resolve() != dest.resolve() and child.exists():
                # only move if leaf is being vacated (BAS flatten / BR rename)
                if leaf.name != target_series or leaf.parent.name != group:
                    move_path(child, dest, apply, actions)

    cleanup_empty(leaf, apply, actions, stop_at=EXP / group)
    # also cleanup model dir for BAS
    if group == "BAS" and leaf.parent != EXP / "BAS":
        cleanup_empty(leaf.parent, apply, actions, stop_at=EXP / "BAS")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually move/rename files (default is dry-run)",
    )
    parser.add_argument(
        "--group",
        choices=["SGL", "BR", "BAS", "all"],
        default="all",
        help="Limit to one EXP_GROUP",
    )
    args = parser.parse_args()
    apply = bool(args.apply)

    if not EXP.is_dir():
        print(f"Missing {EXP}")
        return 1

    leaves = discover_leaves()
    if args.group != "all":
        leaves = [x for x in leaves if x["group"] == args.group]

    print(
        f"[migrate] mode={'APPLY' if apply else 'DRY-RUN'} "
        f"leaves={len(leaves)} groups={[args.group]}"
    )

    reports = []
    total_pairs = 0
    total_orphans = 0
    for leaf_info in leaves:
        rep = process_leaf(leaf_info, apply=apply)
        reports.append(rep)
        total_pairs += rep["n_pairs"]
        total_orphans += rep["n_orphans"]
        print(
            f"  {rep['group']:3} {rep['leaf']} → {rep['target_series']!r} "
            f"pairs={rep['n_pairs']} orphans={rep['n_orphans']}"
        )

    payload = {
        "mode": "apply" if apply else "dry-run",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_leaves": len(leaves),
        "total_pairs": total_pairs,
        "total_orphans": total_orphans,
        "leaves": reports,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Make JSON serializable (Path already str in reports)
    REPORT_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"[migrate] report → {REPORT_PATH}")
    print(f"[migrate] totals pairs={total_pairs} orphans={total_orphans}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
