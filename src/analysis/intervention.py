"""BAS intervention panels for Table 10 (Amp / Sup vs in-group base)."""

from __future__ import annotations

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
    """One row per (group, series, session, bas): mean formal-round price."""
    df = mkt.copy()
    df["round"] = pd.to_numeric(df["round"], errors="coerce")
    df["mkt_prc"] = pd.to_numeric(df["mkt_prc"], errors="coerce")
    df = df.dropna(subset=["round", "session", "mkt_prc"])
    df["round"] = df["round"].astype(int)
    formal = set(range(1, int(total_rounds) + 1))
    df = df[df["round"].isin(formal)]

    keys = [c for c in ("group", "series", "session", "bas") if c in df.columns]
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
    Session-level BAS panel for Table 10.

    Primary outcome ``mean_price`` = average formal-round market price.
    Benchmark is **in-group** ``bas=base`` sessions (series prefix ``b_``),
    not an external group.
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

    base_prices = pd.to_numeric(
        sess.loc[sess["arm"] == "base", "mean_price"], errors="coerce"
    ).to_numpy(dtype=float)
    base_prices = base_prices[np.isfinite(base_prices)]
    bench_mean = float(base_prices.mean()) if len(base_prices) else float("nan")
    sess["bench_mean_price"] = bench_mean
    sess["bench_source"] = "base"
    sess["n_bench"] = int(len(base_prices))

    if bas_market is not None and not bas_market.empty:
        m = bas_market.copy()
        for c in ("mse", "amplitude", "pv_variance", "rounds"):
            if c in m.columns:
                m[c] = pd.to_numeric(m[c], errors="coerce")
        merge_keys = [c for c in ("group", "series", "session") if c in m.columns]
        keep = merge_keys + [
            c for c in ("mse", "amplitude", "pv_variance", "rounds") if c in m.columns
        ]
        m = m.loc[:, keep].drop_duplicates(subset=merge_keys, keep="first")
        sess = sess.merge(m, on=merge_keys, how="left")

    front = [
        "group",
        "series",
        "session",
        "bas",
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


def _welch_diff_t(
    a: np.ndarray, b: np.ndarray
) -> tuple[float, float]:
    """Return (diff_mean = mean(a)-mean(b), t_stat); NaN if too few points."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if len(a) == 0 or len(b) == 0:
        return float("nan"), float("nan")
    diff = float(a.mean() - b.mean())
    if len(a) < 2 or len(b) < 2:
        return diff, float("nan")
    t_res = stats.ttest_ind(a, b, equal_var=False, nan_policy="omit")
    return diff, float(t_res.statistic)


def summarize_intervention_by_mechanism(
    panel: pd.DataFrame,
    *,
    outcome: str = "mean_price",
) -> pd.DataFrame:
    """
    Mechanism-level Table 10 skeleton.

    Bench = in-group ``arm==base`` session outcomes. Amp/Sup vs Bench and
    Amp vs Sup use Welch two-sample t on session ``mean_price``.
    """
    if panel is None or panel.empty:
        return pd.DataFrame()

    base = pd.to_numeric(
        panel.loc[panel["arm"] == "base", outcome], errors="coerce"
    ).to_numpy(dtype=float)
    base = base[np.isfinite(base)]
    bench_mean = float(base.mean()) if len(base) else float("nan")

    rows: list[dict] = []
    for mid in MECHANISM_ORDER:
        sub = panel[panel["mechanism_id"] == mid]
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
        diff_ab, t_ab = _welch_diff_t(amp, base)
        diff_sb, t_sb = _welch_diff_t(sup, base)
        diff_as, t_as = _welch_diff_t(amp, sup)

        rows.append(
            {
                "mechanism_id": mid,
                "mean_amp": amp_mean,
                "mean_sup": sup_mean,
                "mean_bench": bench_mean,
                "bench_source": "base",
                "diff_amp_bench": diff_ab,
                "t_amp_bench": t_ab,
                "diff_sup_bench": diff_sb,
                "t_sup_bench": t_sb,
                "diff_amp_sup": diff_as,
                "t_amp_sup": t_as,
                "n_amp": int(len(amp)),
                "n_sup": int(len(sup)),
                "n_bench": int(len(base)),
                "outcome": outcome,
            }
        )
    return pd.DataFrame(rows)


def load_intervention_inputs(
    out_dir: Path, group_name: str
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    mkt_path = out_dir / f"{group_name}_mkt.csv"
    market_path = out_dir / f"{group_name}_market.csv"
    if not mkt_path.is_file():
        raise FileNotFoundError(
            f"RUN_INTERVENTION requires {mkt_path}; run integ first (no fallback)."
        )
    market_df = pd.read_csv(market_path) if market_path.is_file() else None
    return pd.read_csv(mkt_path), market_df
