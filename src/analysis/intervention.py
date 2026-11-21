"""Amp / Sup vs in-group base mean prices (Welch diffs by mechanism, by mode)."""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from src.analysis.mechanism import MECHANISM_ORDER

# amp_01 /amp_1 / Amp_01 → mechanism index 1..20
_BIAS_RE = re.compile(r"^(amp|sup)[_-]?0*([1-9]|1\d|20)$", re.IGNORECASE)
_SERIES_RE = re.compile(r"^(?:[as]\d{2}|b)_(.+)$", re.IGNORECASE)


def bias_to_mechanism(bas_id: str | None) -> tuple[str | None, str | None]:
    """
    Return (arm, mechanism_id).

    ``base`` → arm ``base``, mechanism None.
    ``amp_XX`` / ``sup_XX`` → arm + mapped mechanism_id.
    ``nan`` / empty → (None, None) — excluded from intervention.
    """
    if bas_id is None or (isinstance(bas_id, float) and np.isnan(bas_id)):
        return None, None
    text = str(bas_id).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None, None
    if text.lower() == "base":
        return "base", None
    m = _BIAS_RE.match(text.replace(" ", ""))
    if not m:
        return None, None
    arm = m.group(1).lower()
    idx = int(m.group(2))
    if idx < 1 or idx > len(MECHANISM_ORDER):
        return None, None
    return arm, MECHANISM_ORDER[idx - 1]


def model_from_series(series: str | None) -> str | None:
    if series is None or (isinstance(series, float) and np.isnan(series)):
        return None
    m = _SERIES_RE.match(str(series).strip())
    if m:
        return m.group(1)
    return str(series).strip() or None


def _formal_session_prices(
    mkt: pd.DataFrame, *, total_rounds: int
) -> pd.DataFrame:
    """One row per (group, mode, series, session, bas): mean formal-round price."""
    df = mkt.copy()
    df["round"] = pd.to_numeric(df["round"], errors="coerce")
    df["mkt_prc"] = pd.to_numeric(df["mkt_prc"], errors="coerce")
    df = df.dropna(subset=["round", "session", "mkt_prc"])
    df["round"] = df["round"].astype(int)
    formal = set(range(1, int(total_rounds) + 1))
    df = df[df["round"].isin(formal)]

    keys = [
        c
        for c in ("group", "mode", "series", "session", "bas")
        if c in df.columns
    ]
    round_keys = keys + ["round"]
    prices = (
        df.groupby(round_keys, dropna=False, sort=False)["mkt_prc"]
        .mean()
        .reset_index()
    )
    sess = (
        prices.groupby(keys, dropna=False, sort=False)
        .agg(mean_price=("mkt_prc", "mean"), n_rounds=("mkt_prc", "count"))
        .reset_index()
    )
    return sess


def build_intervention_panel(
    bas_mkt: pd.DataFrame,
    *,
    bas_market: pd.DataFrame | None = None,
    total_rounds: int = 20,
) -> pd.DataFrame:
    """
    Session-level BAS helper used to build the intervention summary.

    Primary outcome ``mean_price`` = average formal-round market price.
    Benchmark is **in-group, same-mode** ``bas=base`` sessions (``b_`` series),
    not an external group and not pooled across ``sgl``/``br``.
    Rows with ``bas=nan`` (non-BAS) are dropped.
    Not written by ``anal``; only ``summarize_intervention_by_mechanism`` is.
    """
    sess = _formal_session_prices(bas_mkt, total_rounds=total_rounds)
    if sess.empty:
        return sess

    arms: list[str | None] = []
    mechs: list[str | None] = []
    models: list[str | None] = []
    for _, row in sess.iterrows():
        arm, mech = bias_to_mechanism(row.get("bas"))
        arms.append(arm)
        mechs.append(mech)
        models.append(model_from_series(row.get("series")))
    sess["arm"] = arms
    sess["mechanism_id"] = mechs
    sess["model"] = models

    # Keep only parsed BAS arms (drops bas=nan / unknown).
    sess = sess[sess["arm"].notna()].copy()
    if sess.empty:
        return sess

    # Bench stratified by mode when present; else whole-group (legacy).
    has_mode = "mode" in sess.columns
    bench_mean_col: list[float] = []
    n_bench_col: list[int] = []
    if has_mode:
        base_by_mode: dict[object, np.ndarray] = {}
        for mode, part in sess.loc[sess["arm"] == "base"].groupby(
            "mode", dropna=False, sort=False
        ):
            vals = pd.to_numeric(part["mean_price"], errors="coerce").to_numpy(
                dtype=float
            )
            vals = vals[np.isfinite(vals)]
            base_by_mode[mode] = vals
        for mode in sess["mode"]:
            vals = base_by_mode.get(mode, np.array([], dtype=float))
            bench_mean_col.append(
                float(vals.mean()) if len(vals) else float("nan")
            )
            n_bench_col.append(int(len(vals)))
    else:
        base_prices = pd.to_numeric(
            sess.loc[sess["arm"] == "base", "mean_price"], errors="coerce"
        ).to_numpy(dtype=float)
        base_prices = base_prices[np.isfinite(base_prices)]
        bench_mean = float(base_prices.mean()) if len(base_prices) else float("nan")
        n_bench = int(len(base_prices))
        bench_mean_col = [bench_mean] * len(sess)
        n_bench_col = [n_bench] * len(sess)

    sess["bench_mean_price"] = bench_mean_col
    sess["bench_source"] = "base"
    sess["n_bench"] = n_bench_col

    if bas_market is not None and not bas_market.empty:
        m = bas_market.copy()
        for c in ("mse", "amplitude", "pv_variance", "rounds"):
            if c in m.columns:
                m[c] = pd.to_numeric(m[c], errors="coerce")
        merge_keys = [
            c for c in ("group", "mode", "series", "session") if c in m.columns
        ]
        if not merge_keys:
            merge_keys = [c for c in ("group", "series", "session") if c in m.columns]
        keep = merge_keys + [
            c for c in ("mse", "amplitude", "pv_variance", "rounds") if c in m.columns
        ]
        m = m.loc[:, keep].drop_duplicates(subset=merge_keys, keep="first")
        sess = sess.merge(m, on=merge_keys, how="left")

    front = [
        "group",
        "mode",
        "bas",
        "series",
        "session",
        "arm",
        "mechanism_id",
        "model",
        "mean_price",
        "n_rounds",
        "mse",
        "amplitude",
        "pv_variance",
        "bench_mean_price",
        "bench_source",
        "n_bench",
    ]
    cols = [c for c in front if c in sess.columns] + [
        c for c in sess.columns if c not in front
    ]
    return sess.loc[:, cols]


def _stars(p: float) -> str:
    if p is None or (isinstance(p, float) and (math.isnan(p) or math.isinf(p))):
        return ""
    if pd.isna(p):
        return ""
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.1:
        return "*"
    return ""


def _welch_diff_t(
    a: np.ndarray, b: np.ndarray
) -> tuple[float, float, float]:
    """Return (diff = mean(a)-mean(b), t, p); NaN t/p if too few points."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if len(a) == 0 or len(b) == 0:
        return float("nan"), float("nan"), float("nan")
    diff = float(a.mean() - b.mean())
    if len(a) < 2 or len(b) < 2:
        return diff, float("nan"), float("nan")
    t_res = stats.ttest_ind(a, b, equal_var=False, nan_policy="omit")
    return diff, float(t_res.statistic), float(t_res.pvalue)


def summarize_intervention_by_mechanism(
    panel: pd.DataFrame,
    *,
    outcome: str = "mean_price",
) -> pd.DataFrame:
    """
    Final Amp/Sup vs base rows, stratified by ``mode`` when present.

    Columns match Amp / Sup / Bench levels plus Amp−Bench, Sup−Bench, Amp−Sup
    differences with Welch ``t`` / ``p`` / ``star``. Bench = same-mode
    ``arm==base`` session outcomes (default outcome ``mean_price``).
    """
    if panel is None or panel.empty:
        return pd.DataFrame()

    modes: list[object]
    if "mode" in panel.columns:
        modes = list(panel["mode"].drop_duplicates(keep="first"))
    else:
        modes = [None]

    rows: list[dict] = []
    for mode in modes:
        if mode is None:
            part = panel
        else:
            part = panel.loc[panel["mode"] == mode]
        base = pd.to_numeric(
            part.loc[part["arm"] == "base", outcome], errors="coerce"
        ).to_numpy(dtype=float)
        base = base[np.isfinite(base)]
        bench_mean = float(base.mean()) if len(base) else float("nan")

        group_val: object | None = None
        if "group" in part.columns:
            gvals = part["group"].dropna().unique()
            group_val = gvals[0] if len(gvals) else None

        for mid in MECHANISM_ORDER:
            sub = part[part["mechanism_id"] == mid]
            amp = pd.to_numeric(
                sub.loc[sub["arm"] == "amp", outcome], errors="coerce"
            ).to_numpy(dtype=float)
            sup = pd.to_numeric(
                sub.loc[sub["arm"] == "sup", outcome], errors="coerce"
            ).to_numpy(dtype=float)
            amp = amp[np.isfinite(amp)]
            sup = sup[np.isfinite(sup)]

            amp_mean = float(amp.mean()) if len(amp) else float("nan")
            sup_mean = float(sup.mean()) if len(sup) else float("nan")
            diff_ab, t_ab, p_ab = _welch_diff_t(amp, base)
            diff_sb, t_sb, p_sb = _welch_diff_t(sup, base)
            diff_as, t_as, p_as = _welch_diff_t(amp, sup)

            row: dict = {
                "mechanism_id": mid,
                "mean_amp": amp_mean,
                "mean_sup": sup_mean,
                "mean_bench": bench_mean,
                "bench_source": "base",
                "diff_amp_bench": diff_ab,
                "t_amp_bench": t_ab,
                "p_amp_bench": p_ab,
                "star_amp_bench": _stars(p_ab),
                "diff_sup_bench": diff_sb,
                "t_sup_bench": t_sb,
                "p_sup_bench": p_sb,
                "star_sup_bench": _stars(p_sb),
                "diff_amp_sup": diff_as,
                "t_amp_sup": t_as,
                "p_amp_sup": p_as,
                "star_amp_sup": _stars(p_as),
                "n_amp": int(len(amp)),
                "n_sup": int(len(sup)),
                "n_bench": int(len(base)),
                "outcome": outcome,
            }
            if group_val is not None:
                row = {"group": group_val, **row}
            if mode is not None:
                row = {"mode": mode, **row}
            rows.append(row)

    out = pd.DataFrame(rows)
    front = [
        c
        for c in (
            "group",
            "mode",
            "mechanism_id",
            "mean_amp",
            "mean_sup",
            "mean_bench",
            "diff_amp_bench",
            "t_amp_bench",
            "p_amp_bench",
            "star_amp_bench",
            "diff_sup_bench",
            "t_sup_bench",
            "p_sup_bench",
            "star_sup_bench",
            "diff_amp_sup",
            "t_amp_sup",
            "p_amp_sup",
            "star_amp_sup",
            "n_amp",
            "n_sup",
            "n_bench",
            "bench_source",
            "outcome",
        )
        if c in out.columns
    ]
    cols = front + [c for c in out.columns if c not in front]
    return out.loc[:, cols]


def build_intervention_table(
    bas_mkt: pd.DataFrame,
    *,
    bas_market: pd.DataFrame | None = None,
    total_rounds: int = 20,
    outcome: str = "mean_price",
) -> pd.DataFrame:
    """Build the intervention summary CSV content written by ``anal``."""
    panel = build_intervention_panel(
        bas_mkt, bas_market=bas_market, total_rounds=total_rounds
    )
    if panel.empty:
        return panel
    return summarize_intervention_by_mechanism(panel, outcome=outcome)


def has_bas_sessions(mkt: pd.DataFrame) -> bool:
    """True if ``bas`` has any parseable BAS arm (base / amp_* / sup_*), not only ``nan``."""
    if mkt is None or mkt.empty or "bas" not in mkt.columns:
        return False
    for val in mkt["bas"].drop_duplicates():
        arm, _ = bias_to_mechanism(val)
        if arm is not None:
            return True
    return False


def load_intervention_inputs(
    out_dir: Path, group_name: str
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    from src.integ.paths import integ_csv, metrics_csv, read_table_csv

    mkt_path = integ_csv(out_dir, group_name, "mkt")
    market_path = metrics_csv(out_dir, group_name, "market")
    if not mkt_path.is_file():
        raise FileNotFoundError(
            f"RUN_INTERVENTION requires {mkt_path}; run integ first (no fallback)."
        )
    market_df = read_table_csv(market_path) if market_path.is_file() else None
    return read_table_csv(mkt_path), market_df
