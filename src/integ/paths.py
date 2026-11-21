"""Paths for group integ outputs under exp/<GROUP>/_<GROUP>/."""

from __future__ import annotations

import uuid
from pathlib import Path

import pandas as pd

_INTEG_STEMS = frozenset({"rx", "mkt", "output"})
_METRICS_STEMS = frozenset(
    {
        "market",
        "market_robust_sgl",
        "market_robust_br",
        "rational",
        "rational_robust_sgl",
        "rational_robust_br",
    }
)
_NLP_STEMS = frozenset({"output_nlp", "output_miss"})
_PANEL_STEMS = frozenset(
    {"behavior", "cognition", "equilibrium", "mechanism"}
)
_RESEARCH_STEMS = frozenset(
    {
        "disposition",
        "extrapolation",
        "belief_action",
        "bid_offer",
        "disagreement",
        "stated_belief",
        "stated_action",
        "mechanism_bubble",
    }
)


def ensure_cased_path(path: Path) -> Path:
    """
    Ensure path's final component uses exactly path.name casing.
    On case-insensitive volumes, an existing `_sgl` must be two-step-renamed
    to `_SGL` (and likewise for CSV filenames).
    """
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    target_name = path.name

    existing: Path | None = None
    for child in parent.iterdir():
        if child.name.casefold() == target_name.casefold():
            existing = child
            break

    if existing is None:
        return parent / target_name

    if existing.name == target_name:
        return existing

    tmp = parent / f".{target_name}.{uuid.uuid4().hex}.tmp"
    existing.rename(tmp)
    tmp.rename(parent / target_name)
    return parent / target_name


def integ_dir(out_dir: Path) -> Path:
    """Directory for the three integ CSVs: ``_<GROUP>/integrate/``."""
    return ensure_cased_path(Path(out_dir) / "integrate")


def integ_csv(out_dir: Path, group_name: str, stem: str) -> Path:
    """
    Path to ``_<GROUP>/integrate/<GROUP>_{stem}.csv``.

    ``stem`` must be ``rx``, ``mkt``, or ``output``.
    """
    key = str(stem).strip().lower()
    if key not in _INTEG_STEMS:
        raise ValueError(f"integ stem must be one of {sorted(_INTEG_STEMS)}, got {stem!r}")
    return integ_dir(out_dir) / f"{group_name}_{key}.csv"


def metrics_dir(out_dir: Path) -> Path:
    """Directory for market/rational metric CSVs: ``_<GROUP>/metrics/``."""
    return ensure_cased_path(Path(out_dir) / "metrics")


def metrics_csv(out_dir: Path, group_name: str, stem: str) -> Path:
    """
    Path to ``_<GROUP>/metrics/<GROUP>_{stem}.csv``.

    ``stem`` examples: ``market``, ``market_robust_sgl``, ``rational``.
    Does not include ``mkt_agg`` (stays under ``_<GROUP>/``).
    """
    key = str(stem).strip().lower()
    if key not in _METRICS_STEMS:
        raise ValueError(
            f"metrics stem must be one of {sorted(_METRICS_STEMS)}, got {stem!r}"
        )
    return metrics_dir(out_dir) / f"{group_name}_{key}.csv"


def nlp_dir(out_dir: Path) -> Path:
    """Directory for NLP JSON + merge/miss CSVs: ``_<GROUP>/nlp/``."""
    return ensure_cased_path(Path(out_dir) / "nlp")


def nlp_csv(out_dir: Path, group_name: str, stem: str) -> Path:
    """
    Path to ``_<GROUP>/nlp/<GROUP>_{stem}.csv``.

    ``stem`` must be ``output_nlp`` or ``output_miss``.
    """
    key = str(stem).strip().lower()
    if key not in _NLP_STEMS:
        raise ValueError(f"nlp stem must be one of {sorted(_NLP_STEMS)}, got {stem!r}")
    return nlp_dir(out_dir) / f"{group_name}_{key}.csv"


def panels_dir(out_dir: Path) -> Path:
    """Directory for intermediate anal panels: ``_<GROUP>/panels/``."""
    return ensure_cased_path(Path(out_dir) / "panels")


def panel_csv(out_dir: Path, group_name: str, stem: str) -> Path:
    """
    Path to ``_<GROUP>/panels/<GROUP>_{stem}.csv``.

    ``stem`` must be ``behavior``, ``cognition``, ``equilibrium``, or ``mechanism``.
    """
    key = str(stem).strip().lower()
    if key not in _PANEL_STEMS:
        raise ValueError(
            f"panel stem must be one of {sorted(_PANEL_STEMS)}, got {stem!r}"
        )
    return panels_dir(out_dir) / f"{group_name}_{key}.csv"


def research_csv(out_dir: Path, group_name: str, stem: str) -> Path:
    """
    Path to ``_<GROUP>/<GROUP>_{stem}.csv`` (paper tables at group-root).

    ``stem`` must be one of: disposition, extrapolation, belief_action,
    bid_offer, disagreement, stated_belief, stated_action, mechanism_bubble.
    """
    key = str(stem).strip().lower()
    if key not in _RESEARCH_STEMS:
        raise ValueError(
            f"research stem must be one of {sorted(_RESEARCH_STEMS)}, got {stem!r}"
        )
    return ensure_cased_path(Path(out_dir) / f"{group_name}_{key}.csv")


def read_table_csv(path: Path) -> pd.DataFrame:
    """
    Read a group CSV without coercing the literal ``nan`` in ``bas`` to missing.
    """
    return pd.read_csv(path, keep_default_na=False)


def round_table_numeric(df: pd.DataFrame, ndigits: int = 4) -> pd.DataFrame:
    """Round floating columns to at most ``ndigits`` decimals (integers unchanged)."""
    if df is None or df.empty:
        return df
    out = df.copy()
    for col in out.select_dtypes(include=["floating"]).columns:
        out[col] = out[col].round(ndigits)
    return out


def write_table_csv(df: pd.DataFrame, path: Path, *, ndigits: int = 4) -> Path:
    """Write a group CSV with floats rounded to at most ``ndigits`` decimals."""
    path = ensure_cased_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    round_table_numeric(df, ndigits=ndigits).to_csv(
        path, index=False, encoding="utf-8"
    )
    return path
