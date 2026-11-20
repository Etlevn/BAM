"""Shared readers for market/mkt.csv and portfolio text."""

from __future__ import annotations

from pathlib import Path


def read_market_prices_and_volumes(
    mkt_csv: Path,
) -> tuple[list[float], list[float]]:
    prices: list[float] = []
    volumes: list[float] = []
    with open(mkt_csv, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.lower().startswith("round"):
                continue
            parts = s.split(",")
            if len(parts) < 2:
                continue
            try:
                prices.append(float(parts[1]))
                volumes.append(float(parts[2]) if len(parts) >= 3 else 0.0)
            except Exception:
                continue
    return prices, volumes


def read_market_prices(mkt_csv: Path) -> list[float]:
    prices, _ = read_market_prices_and_volumes(mkt_csv)
    return prices


def read_market_prices_by_round(mkt_csv: Path) -> dict[int, float]:
    prices_by_round: dict[int, float] = {}
    with open(mkt_csv, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.lower().startswith("round"):
                continue
            parts = s.split(",")
            if len(parts) < 2:
                continue
            try:
                round_num = int(float(parts[0]))
                prices_by_round[round_num] = float(parts[1])
            except Exception:
                continue
    return prices_by_round


def portfolio_values_in_round(round_input_dir: Path) -> list[float]:
    pv_list: list[float] = []
    if not round_input_dir.is_dir():
        return pv_list
    for file in round_input_dir.iterdir():
        if not file.name.endswith("_portfolio.txt") or not file.is_file():
            continue
        try:
            cash, redemp = None, None
            with open(file, "r", encoding="utf-8") as f:
                for line in f:
                    if "Current cash" in line:
                        cash = float(line.strip().split(":")[1])
                    elif "Expected redemption value" in line:
                        redemp = float(line.strip().split(":")[1])
            if cash is not None and redemp is not None:
                pv_list.append(cash + redemp)
        except Exception:
            continue
    return pv_list
