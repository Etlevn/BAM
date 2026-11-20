"""Dual-axis price–volume plots (same style as legacy anal/anal.py)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from src.analysis.market_io import read_market_prices_and_volumes
from src.integ.runner import ensure_cased_path
from src.integ.session import SessionMeta


def plot_session(
    *,
    mkt_path: Path,
    save_path: Path,
    fundamental_value: float,
    session: str,
    rounds: int,
    mse: Any,
    amplitude: Any,
    pv_variance: Any,
    min_rounds: int = 20,
) -> bool:
    """Write one dual-axis PNG. Returns True if saved."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    try:
        prices, volumes = read_market_prices_and_volumes(mkt_path)
    except Exception as exc:
        print(f"[plots] Failed to read {mkt_path}: {exc}")
        return False

    actual_rounds = len(prices) - 1
    if actual_rounds < min_rounds or not prices:
        return False

    rounds_x = list(range(len(prices)))

    fig, ax1 = plt.subplots(figsize=(6, 4))
    ax1.plot(rounds_x, prices, color="tab:red", marker="o", label="Market Price")
    ax1.axhline(
        y=fundamental_value,
        linestyle="--",
        color="gray",
        label="Fundamental Value",
    )
    ax1.set_ylabel("Price", color="tab:red")
    ax1.set_ylim(0, max(30, max(prices) + 2))
    ax1.tick_params(axis="y", labelcolor="tab:red")

    ax2 = ax1.twinx()
    ax2.bar(rounds_x, volumes, alpha=0.3, color="tab:blue", label="Volume")
    ax2.set_ylabel("Volume", color="tab:blue")
    ax2.tick_params(axis="y", labelcolor="tab:blue")

    title = (
        f"{session} (Rounds={int(rounds)})\n"
        f"MSE={mse} | Amp={amplitude} | PVVar={pv_variance}"
    )
    plt.title(title)
    ax1.set_xlabel("Round")
    ax1.grid(True, linestyle=":")
    fig.tight_layout()

    save_path = ensure_cased_path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(save_path)
    plt.close()
    return True


def plot_group(
    sessions: Sequence[SessionMeta],
    market_rows: Sequence[dict[str, Any]],
    *,
    plots_root: Path,
    fundamental_value: float,
    min_rounds: int = 20,
) -> Path:
    """
    Save plots under plots_root/<series>/<session>.png.
    Metrics for the title come from market_rows (session-level market table).
    """
    by_key = {
        (r["group"], r["series"], r["session"]): r for r in market_rows
    }
    plots_root = ensure_cased_path(plots_root)
    plots_root.mkdir(parents=True, exist_ok=True)

    saved = 0
    for meta in sessions:
        row = by_key.get((meta.group, meta.series, meta.simulation_index))
        if row is None:
            continue
        mkt_path = meta.path / "market" / "mkt.csv"
        if not mkt_path.is_file():
            continue
        save_path = plots_root / meta.series / f"{meta.simulation_index}.png"
        ok = plot_session(
            mkt_path=mkt_path,
            save_path=save_path,
            fundamental_value=fundamental_value,
            session=meta.simulation_index,
            rounds=int(row.get("rounds") or 0),
            mse=row.get("mse"),
            amplitude=row.get("amplitude"),
            pv_variance=row.get("pv_variance"),
            min_rounds=min_rounds,
        )
        if ok:
            saved += 1

    print(f"Saved {saved} plots → {plots_root}/<series>/<session>.png")
    return plots_root


def plot_mkt_agg(
    mkt_agg_df,
    *,
    save_path: Path,
    group: str = "",
) -> Path:
    """
    Paper Figure 2 style: mean price + 95% CI band, volume bars, FV dashed line.
    Expects columns from build_mkt_agg_table / <GROUP>_mkt_agg.csv.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd

    df = mkt_agg_df.copy()
    df["round"] = pd.to_numeric(df["round"], errors="coerce")
    df = df.dropna(subset=["round"]).sort_values("round")
    rounds = df["round"].astype(int).tolist()
    mean_p = pd.to_numeric(df["mean_price"], errors="coerce")
    ci_lo = pd.to_numeric(df["ci_low"], errors="coerce")
    ci_hi = pd.to_numeric(df["ci_up"], errors="coerce")
    mean_v = pd.to_numeric(df["mean_volume"], errors="coerce").fillna(0.0)
    fv = float(pd.to_numeric(df["fundamental_value"], errors="coerce").dropna().iloc[0])

    fig, ax1 = plt.subplots(figsize=(8, 4.5))
    ax1.fill_between(
        rounds, ci_lo, ci_hi, color="tab:red", alpha=0.2, label="95% CI"
    )
    ax1.plot(
        rounds,
        mean_p,
        color="tab:red",
        marker="o",
        markersize=3,
        linewidth=1.5,
        label="Mean Market Price",
    )
    ax1.axhline(
        y=fv,
        linestyle="--",
        color="gray",
        linewidth=1.2,
        label=f"Fundamental Value ({fv:g})",
    )
    ax1.set_xlabel("Round")
    ax1.set_ylabel("Price", color="tab:red")
    ax1.tick_params(axis="y", labelcolor="tab:red")
    y_max = max(
        fv + 2,
        float(mean_p.max()) if mean_p.notna().any() else 0,
        float(ci_hi.max()) if ci_hi.notna().any() else 0,
        30,
    )
    ax1.set_ylim(0, y_max + 2)

    ax2 = ax1.twinx()
    ax2.bar(rounds, mean_v, alpha=0.3, color="tab:blue", label="Mean Volume")
    ax2.set_ylabel("Volume", color="tab:blue")
    ax2.tick_params(axis="y", labelcolor="tab:blue")

    title = "Aggregate Market Price Dynamics"
    if group:
        title = f"{title} ({group})"
    ax1.set_title(title)
    ax1.grid(True, linestyle=":")

    # Combined legend
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8)

    fig.tight_layout()
    save_path = ensure_cased_path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"Saved mkt_agg plot → {save_path}")
    return save_path
