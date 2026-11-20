"""Discover, classify, and load per-run session metadata."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from src.runtime.runconfig import load_session_config

_SESSION_RE = re.compile(r"^\d{8}_\d{6}")
_ROUND_CSV_RE = re.compile(r"^r(\d+)\.csv$")
_ROUND_DIR_RE = re.compile(r"^r(\d+)$")


@dataclass(frozen=True)
class SessionMeta:
    path: Path
    group: str
    series: str
    simulation_index: str
    market_type: str
    bas: str
    assignments: dict[str, str]
    total_rounds: int


@dataclass(frozen=True)
class ClassifyResult:
    """Outcome of one group scan: mergeable sessions + relocated non-complete runs."""

    complete: list[SessionMeta]
    moved: list[tuple[Path, Path]]
    skipped_moves: list[tuple[Path, str]]


def should_skip_name(name: str) -> bool:
    return name.startswith("_") or name.startswith(".")


def market_rounds(session_dir: Path) -> list[int]:
    market_dir = session_dir / "market"
    if not market_dir.is_dir():
        return []
    rounds: list[int] = []
    for p in market_dir.iterdir():
        m = _ROUND_CSV_RE.fullmatch(p.name)
        if m:
            rounds.append(int(m.group(1)))
    return sorted(set(rounds))


def is_formal_session(session_dir: Path, min_rounds: int = 20) -> bool:
    rounds = market_rounds(session_dir)
    if not rounds:
        return False
    max_r = rounds[-1]
    if max_r < min_rounds:
        return False
    return rounds == list(range(1, max_r + 1))


def _legacy_assignments(cfg: dict) -> dict[str, str]:
    if "assignments" in cfg and isinstance(cfg["assignments"], dict):
        return {str(k): str(v) for k, v in cfg["assignments"].items()}
    model_name = cfg.get("model_name")
    if model_name:
        num = int(cfg.get("num_llms") or 20)
        return {f"llm_{i:03d}": str(model_name) for i in range(1, num + 1)}
    return {}


def _bas_value(exp: dict) -> str:
    """BAS bias id when enabled; otherwise the literal 'null'."""
    if not bool(exp.get("USE_BAS_MODE")):
        return "null"
    bias = exp.get("BAS_BIAS_ID")
    if bias is None or str(bias).strip() == "":
        return "null"
    return str(bias)


def load_session_meta(session_dir: Path, series: str, group: str) -> SessionMeta | None:
    cfg = load_session_config(session_dir)
    if not cfg:
        return None

    exp = cfg.get("experiment") or {}
    market_type = str(exp.get("EXPERIMENT_MODE") or "").strip().lower()
    if market_type not in ("sgl", "br"):
        if cfg.get("model_name") and not cfg.get("assignments"):
            market_type = "sgl"
        elif cfg.get("assignments"):
            market_type = "br"
        else:
            market_type = "unknown"

    assignments = _legacy_assignments(cfg)
    ec = exp.get("EXPERIMENT_CONFIG") or {}
    total_rounds = int(ec.get("total_rounds") or 20)

    return SessionMeta(
        path=session_dir,
        group=group,
        series=series,
        simulation_index=session_dir.name,
        market_type=market_type,
        bas=_bas_value(exp),
        assignments=assignments,
        total_rounds=total_rounds,
    )


def session_status(session_dir: Path) -> str | None:
    """Return normalized status string, or None if config/status is missing."""
    cfg = load_session_config(session_dir)
    if not cfg:
        return None
    raw = str(cfg.get("status") or "").strip().lower()
    return raw or None


def is_complete_session(session_dir: Path) -> bool:
    """True only when unified/legacy config reports status == complete."""
    return session_status(session_dir) == "complete"


def is_active_session(session_dir: Path) -> bool:
    """
    True for live / in-progress runs that must stay in place.
    Protects status=running; also leaves sessions with no config yet
    (may still be initializing).
    """
    status = session_status(session_dir)
    if status is None:
        return True
    return status == "running"


# Non-complete sessions are relocated under this fixed series-level bin.
_NONCOMPLETE_BIN = "_incomplete"


def _unique_dest(dest: Path) -> Path:
    if not dest.exists():
        return dest
    i = 1
    while True:
        candidate = dest.with_name(f"{dest.name}__dup{i}")
        if not candidate.exists():
            return candidate
        i += 1


def classify_group_sessions(group_dir: Path) -> ClassifyResult:
    """
    Single pass over exp/<GROUP>/<series>/<session>/:

    - status == complete and formal → included for integ merge
    - status == running (or no config yet) → left in place (not merged, not moved)
    - other non-complete → moved under
      exp/<GROUP>/<series>/_incomplete/<session>/

    Folders starting with '_' (result dirs, incomplete bins, etc.) are not scanned
    as series.

    Callable from integ and other callers; bin name is fixed internally.
    """
    complete: list[SessionMeta] = []
    moved: list[tuple[Path, Path]] = []
    skipped_moves: list[tuple[Path, str]] = []

    if not group_dir.is_dir():
        return ClassifyResult(complete, moved, skipped_moves)

    group_name = group_dir.name
    bin_name = _NONCOMPLETE_BIN

    for series_dir in sorted(group_dir.iterdir()):
        if not series_dir.is_dir() or should_skip_name(series_dir.name):
            continue
        series_bin = series_dir / bin_name
        for session_dir in sorted(series_dir.iterdir()):
            if not session_dir.is_dir() or not _SESSION_RE.match(session_dir.name):
                continue

            status = session_status(session_dir)
            if status == "complete":
                meta = load_session_meta(session_dir, series_dir.name, group_name)
                if meta is None:
                    continue
                if is_formal_session(session_dir, min_rounds=meta.total_rounds):
                    complete.append(meta)
                continue

            # Do not touch live runs.
            if is_active_session(session_dir):
                continue

            # Other non-complete: incomplete / failed / interrupted / …
            dest = series_bin / session_dir.name
            try:
                series_bin.mkdir(parents=True, exist_ok=True)
                dest = _unique_dest(dest)
                shutil.move(str(session_dir), str(dest))
                moved.append((session_dir, dest))
            except Exception as exc:
                skipped_moves.append((session_dir, str(exc)))

    return ClassifyResult(complete=complete, moved=moved, skipped_moves=skipped_moves)


def iter_formal_sessions(group_dir: Path) -> Iterator[SessionMeta]:
    """Compatibility wrapper around classify_group_sessions."""
    yield from classify_group_sessions(group_dir).complete


def input_round_dirs(session_dir: Path) -> list[int]:
    input_root = session_dir / "input"
    if not input_root.is_dir():
        return []
    rounds: list[int] = []
    for d in input_root.iterdir():
        if d.is_dir():
            m = _ROUND_DIR_RE.fullmatch(d.name)
            if m:
                rounds.append(int(m.group(1)))
    return sorted(set(rounds))


def output_round_dirs(session_dir: Path) -> list[int]:
    output_root = session_dir / "output"
    if not output_root.is_dir():
        return []
    rounds: list[int] = []
    for d in output_root.iterdir():
        if d.is_dir():
            m = _ROUND_DIR_RE.fullmatch(d.name)
            if m:
                rounds.append(int(m.group(1)))
    return sorted(set(rounds))
