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
