# BAM Metrics Tables

This document describes session-level **market quality** and **forecast rationality** tables under `exp/<GROUP>/_<GROUP>/metrics/`. For integ/panel construction see [pipeline.md](pipeline.md). For NLP coding see [nlp.md](nlp.md). For paper Figure 2 / Tables 2–10 end products at the group root see [research.md](research.md).

**Entry:** `anal.py` with `RUN_MARKET`, `RUN_MARKET_ROBUST`, `RUN_RATIONAL`, `RUN_RATIONAL_ROBUST`.

**Defaults:** formal rounds \(T=20\), fundamental value \(\mathrm{FV}=14\) (`config.EXPERIMENT_CONFIG`). Identity keys `group`, `mode`, `bas`, `series`, `session` follow [pipeline.md](pipeline.md) §1.

---

## 1. Market quality

### 1.1 `metrics/<GROUP>_market.csv`

| | |
|--|--|
| **Grain** | one row per session |
| **Flag** | `RUN_MARKET` |
| **Paper role** | Session-level inputs to Table 1 (aggregated further in robust files) |

For formal rounds \(t=1,\ldots,T\):

\[
\mathrm{MSE}(\mathrm{FV})=\frac{1}{T}\sum_{t=1}^{T}(P_t-\mathrm{FV})^2
\]

\[
\mathrm{Amplitude}=\max_{t\in\{1,\ldots,T\}} P_t-\mathrm{FV}
\]

\[
\mathrm{PV\ Variance}=\frac{1}{T}\sum_{t=1}^{T}\mathrm{Var}_i\!\left(\mathrm{PV}_{i,t}\right)
\]

where \(\mathrm{PV}_{i,t}=\) cash + expected redemption (`Expected redemption`, \(\mathrm{FV}\times\) shares), and \(\mathrm{Var}_i\) is the cross-sectional variance across agents in the round (NumPy population variance).

| Column | Definition |
|--------|------------|
| `group` / `mode` / `bas` / `series` / `session` | Identity keys |
| `rounds` | Number of formal rounds included |
| `mse` | \(\mathrm{MSE}(\mathrm{FV})\) |
| `amplitude` | Amplitude as above |
| `pv_variance` | PV Variance as above |

### 1.2 `metrics/<GROUP>_market_robust_sgl.csv` and `…_market_robust_br.csv`

| | |
|--|--|
| **Grain** | long table keyed by `(group, mode, bas, series, Metric)` |
| **Flag** | `RUN_MARKET_ROBUST` (writes both files when rows exist; skips empty mode) |
| **Paper role** | Table 1 Single (`_sgl`) and Mixed (`_br`) |

The two files do **not** overlap:

| File | Construction |
|------|----------------|
| `_market_robust_sgl` | Keep `mode=sgl` → equal-weight summary over sessions at `group × mode × bas × series` |
| `_market_robust_br` | Keep `mode=br` → expand pair `series` (`A & B`) into single-model rows → same summary (Mixed / agg convention) |

| Column | Definition |
|--------|------------|
| `Metric` | `mse` / `amplitude` / `pv_variance` |
| `Mean` | Arithmetic mean across sessions (Table 1 primary cell) |
| `StdDev` | Sample standard deviation (\(n-1\)) |
| `CV` | \(\mathrm{StdDev}/\mathrm{Mean}\) |
| `95% CI Lower` / `Upper` | 95% \(t\) CI for the mean (SEM + `t.interval`) |
| `CI Width / Mean` | Interval width divided by Mean |
| `n` | Session count (after pair→model expansion for `br`) |

**How to read Table 1 from these files:** pick `Metric=mse` (or amplitude / pv_variance), read `Mean` (and optionally dispersion columns) by `series` within the appropriate mode file.

---

## 2. Forecast rationality

### 2.1 `metrics/<GROUP>_rational.csv`

| | |
|--|--|
| **Grain** | one row per session |
| **Flag** | `RUN_RATIONAL` |
| **Role** | Methods / auxiliary diagnostics (not a main paper display table) |

Align each agent’s `price_forecasts` with realized clearing prices. Forecast error:

\[
e=\hat{P}-P_{\mathrm{true}}
\]

| Column | Definition |
|--------|------------|
| `mse` | Mean squared forecast error \(\overline{(\hat{P}-P)^2}\) |
| `mean_error` / `std_error` | Mean / SD of \(e\) |
| `skewness` / `kurtosis` | Skewness / kurtosis of the error distribution |
| `t_stat_error` / `p_val_error` | One-sample \(t\)-test that mean error is zero |
| `ar1_coef` / `ar1_pval` | AR(1) of errors on own lag |
| `dw_stat` | Durbin–Watson statistic (serial correlation in residuals) |

### 2.2 `metrics/<GROUP>_rational_robust_sgl.csv` and `…_rational_robust_br.csv`

| | |
|--|--|
| **Flag** | `RUN_RATIONAL_ROBUST` |
| **Construction** | Same mode split and `br` pair→model expansion as market robust (§1.2), then Mean / Std / CV / 95% CI by `group × mode × bas × series` |

---

## 3. Related outputs (not under `metrics/`)

| Output | Location | Document |
|--------|----------|----------|
| Figure 2 price/volume paths | `_<GROUP>/<GROUP>_mkt_agg.csv` | [research.md](research.md) |
| Optional Figure 2 plots | `_<GROUP>/plots/mkt_agg/` | [research.md](research.md) |
| Session price/volume plots | `_<GROUP>/plots/market/` | (diagnostic; `RUN_PLOTS`) |

---

## 4. Maintenance

- Metric formula changes belong in `src/analysis/market.py`, `src/analysis/rationality.py` (and related helpers) and in this document.
- Paper Table 1 cells should be reproducible from the robust CSVs without re-reading raw sessions.
