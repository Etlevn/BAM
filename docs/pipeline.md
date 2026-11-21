# BAM Pipeline Tables

This document describes **intermediate** CSV tables under `exp/<GROUP>/_<GROUP>/`: the integ extracts in `integrate/` and the analysis panels in `panels/`. It is a data contract for how rows are built—not a guide to reading paper coefficients. For market/rational metrics see [metrics.md](metrics.md). For NLP coding outputs see [nlp.md](nlp.md). For paper end tables (Figure 2, Tables 2–10 style FE / intervention) see [research.md](research.md).

Paths look like `exp/TEST/_TEST/integrate/TEST_mkt.csv` or `exp/SGL/_SGL/panels/SGL_behavior.csv`.

**Entry scripts**

| Script | Writes |
|--------|--------|
| `integ.py` | `integrate/<GROUP>_{mkt,rx,output}.csv` |
| `anal.py` (`RUN_BEHAVIOR` / `RUN_EQUILIBRIUM` / `RUN_COGNITION` / `RUN_MECHANISM`) | `panels/<GROUP>_{behavior,equilibrium,cognition,mechanism}.csv` |

**Shared experiment defaults** (from `config.EXPERIMENT_CONFIG` unless noted)

| Symbol | Default | Config key |
|--------|---------|------------|
| Formal rounds \(T\) | 20 | `total_rounds` |
| Fundamental value \(\mathrm{FV}\) | 14 | `stock_value` |
| Initial endowment of shares | 4 | `initial_stocks` |

---

## 1. Identity keys

Most integ and panel tables begin with (a subset of) these columns. Merges and within-arm calculations are stratified by these keys so mixed groups never pool across `mode` / `bas` / `series` incorrectly.

| Column | Meaning |
|--------|---------|
| `group` | First-level experiment folder name (`TEST`, `SGL`, `BR`, `BAS`, …) |
| `mode` | Market composition: `sgl` (single-model) or `br` (mixed / battle-royale pair) |
| `bas` | BAS bias id; non-BAS sessions use the literal string `nan` (not a missing float) |
| `series` | Second-level series folder (model name, or `modelA & modelB`; BAS often prefixed `b_` / `a01_` / `s20_`) |
| `session` | Third-level session directory (usually a timestamp) |
| `round` | Trading round index (formal period typically \(1,\ldots,T\)) |
| `llm` | Trader seat id (e.g. `llm_001`) |
| `llm_type` | Model name assigned to that seat |

---

## 2. Integrate tables (`integ.py` → `_<GROUP>/integrate/`)

`integ.py` scans complete formal sessions under `exp/<GROUP>/`, reads `mode` / LLM assignments from each session’s `config.json`, and writes three group-level CSVs. Incomplete non-running sessions are moved under `<series>/_incomplete/`.

### 2.1 `<GROUP>_mkt.csv`

| | |
|--|--|
| **Grain** | agent × round |
| **Source** | Per-session `input/r*` market / portfolio / forecast text |
| **Downstream** | Figure 2 (`_<GROUP>/<GROUP>_mkt_agg.csv`); Tables 2–4 panels; equilibrium / cognition / mechanism |

| Column | Definition |
|--------|------------|
| `mkt_prc` | Cleared market price \(P_t\) in the round |
| `mkt_vol` | Cleared volume in the round |
| `stk_num` | Share holdings after the round |
| `stk_val` | Mark-to-market value of holdings |
| `cash` | Cash balance |
| `div` / `int` | Dividend / interest received |
| `fcst_k_rnd` / `fcst_k_prc` | \(k\)-th forecast target round and forecast price (typically \(k=1..4\), horizons near \(0,2,5,10\)) |

Within a fixed `(session, round)`, all agents share the same `mkt_prc` / `mkt_vol` (market-level); holdings and forecasts are agent-specific.

### 2.2 `<GROUP>_rx.csv`

| | |
|--|--|
| **Grain** | order line (agent × round × order) |
| **Source** | Per-session `market/r*.csv` |
| **Downstream** | Submitted / filled quantities for sell/buy dummies and WAPP updates on the behavior and cognition panels |

| Column | Definition |
|--------|------------|
| `b/s` | `BUY` or `SELL` |
| `num` | Submitted quantity |
| `prc` | Limit price |
| `mkt` | Round clearing price |
| `ord` | Filled quantity (`0` if unfilled) |
| `deal` | Fill price (`0` if unfilled) |

### 2.3 `<GROUP>_output.csv`

| | |
|--|--|
| **Grain** | agent × round |
| **Source** | Model outputs: plan / insight text |
| **Downstream** | NLP coding ([nlp.md](nlp.md)); cognition stated-action panel |

| Column | Definition |
|--------|------------|
| `obs` | Other observation / raw text fragments when present |
| `plan` | Trading-plan text |
| `insight` | Insight / reflection text |

---

## 3. Panels (`anal.py` → `_<GROUP>/panels/`)

Panels are **analysis-ready** intermediate tables. Fixed-effect paper regressions are produced later by `research.py` from these files (see [research.md](research.md)).

### 3.1 `panels/<GROUP>_behavior.csv`

| | |
|--|--|
| **Grain** | agent × round |
| **Flags** | `RUN_BEHAVIOR` (requires `integrate/_mkt` + `_rx`) |
| **Paper variables** | Tables 2–4 |
| **Consumed by** | `_disposition.csv`, `_extrapolation.csv`, `_belief_action.csv` |

#### Order aggregates (from `_rx`)

| Column | Definition |
|--------|------------|
| `buy_submitted` / `sell_submitted` | Sum of submitted buy / sell quantities in the round |
| `buy_filled_qty` / `buy_filled_cost` | Filled buy quantity; \(\sum(\mathrm{ord}\times\mathrm{deal})\) |
| `sell_dummy` | \(1\{\text{sell\_submitted}>\text{buy\_submitted}\}\) (Table 2 outcome) |
| `buy_dummy` | \(1\{\text{buy\_submitted}>\text{sell\_submitted}\}\) |
| `buy_dummy_next` | Next-round `buy_dummy` (Table 4: period-\(t\) beliefs → period-\(t{+}1\) buys) |

#### WAPP and gain (Table 2)

- Initialize WAPP \(=\mathrm{FV}\) and shares \(=\) `initial_stocks`.
- Update WAPP **only on buy fills**:

\[
\mathrm{WAPP}'
=
\frac{S\cdot\mathrm{WAPP}+Q_{\mathrm{buy}}\cdot\bar{P}_{\mathrm{deal}}}{S+Q_{\mathrm{buy}}}
\]

Sells do not change WAPP.

| Column | Definition |
|--------|------------|
| `wapp` | WAPP at the **start** of the round |
| `gain_dummy` | \(1\{P_{t-1}>\mathrm{WAPP}_t\}\); for \(t=1\), \(P_0:=\mathrm{FV}\) |
| `avg_expectation` | Arithmetic mean of the four `fcst_*_prc` prices in the round |

#### Realized and expected returns (Table 3)

\[
r_t=\frac{P_t-P_{t-1}}{P_{t-1}}
\]

| Column | Definition |
|--------|------------|
| `ret` | Realized return \(r_t\) |
| `ret_lag1`…`ret_lag4` | \(r_{t-1},\ldots,r_{t-4}\) |
| `exp_ret_h0` / `h2` / `h5` / `h10` | If forecast target relative to current round has \(\Delta\in\{0,2,5,10\}\): \(\hat{P}/P_t-1\) |

---

### 3.2 `panels/<GROUP>_equilibrium.csv`

| | |
|--|--|
| **Grain** | session × round (market level) |
| **Flags** | `RUN_EQUILIBRIUM` (requires `_mkt` + `_rx`) |
| **Paper variables** | Tables 5–6 |
| **Consumed by** | `_bid_offer.csv`, `_disagreement.csv` |

| Column | Definition |
|--------|------------|
| `mkt_prc` / `mkt_vol` | Cleared price and volume (`_mkt` deduped at session×round) |
| `price_change_next` | \(P_{t+1}-P_t\) (Table 5 outcome); missing in the last round |
| `bid_offer_gap` | \(\sum Q_{\mathrm{buy}}^{\mathrm{sub}}-\sum Q_{\mathrm{sell}}^{\mathrm{sub}}\) over all agents |
| `buy_submitted` / `sell_submitted` | Market-wide submitted buy / sell totals |
| `disagreement` | Cross-sectional sample SD of agents’ mean forecast prices (average of four horizons) |
| `dollar_volume` | \(P_t\times V_t\) |
| `n_agents` | Agents with a valid average forecast in the round |

---

### 3.3 `panels/<GROUP>_cognition.csv`

| | |
|--|--|
| **Grain** | agent × round |
| **Flags** | `RUN_COGNITION` (requires `_mkt` + `_rx` + `_output`) |
| **Paper variables** | Tables 7–8 |
| **Consumed by** | `_stated_belief.csv`, `_stated_action.csv` |
| **Note** | Does **not** use NLP mechanism scores (those feed Table 9) |

#### Stated action (text direction)

Count buy / sell keywords in `plan` and `insight` separately (word lists in `src/analysis/cognition.py`: `BUY_KEYWORDS` / `SELL_KEYWORDS`; whole-word, case-insensitive):

\[
\mathrm{net}=n_{\mathrm{buy}}-n_{\mathrm{sell}},\qquad
\mathrm{Stated\ Action}=\operatorname{sign}(\mathrm{net})\in\{-1,0,1\}
\]

Missing text → missing stated action (not zero). Columns: `stated_action_plan`, `stated_action_insight`, plus keyword counts `buy_kw_*` / `sell_kw_*`.

#### Expected returns and next-period buying

Expected-return columns match the behavior panel (`exp_ret_h*`; Methods horizons \(h\in\{0,2,5,10\}\); `exp_ret_t10` aliases `exp_ret_h10`). Paper Table 7 headers that once wrote \(R_{t+1}\) are **not** followed; see `docs/paper/definition_audit.md`.

| Column | Definition |
|--------|------------|
| `buy_dummy` | Same as behavior: \(1\{\text{buy\_submitted}>\text{sell\_submitted}\}\) |
| `buy_dummy_next` | Next-round `buy_dummy` (Table 8) |

---

### 3.4 `panels/<GROUP>_mechanism.csv`

| | |
|--|--|
| **Grain** | agent × round × mechanism (long; 20 mechanisms per agent–round) |
| **Flags** | `RUN_MECHANISM` (needs `integrate/_mkt` + `nlp/<GROUP>_output_nlp.csv`; skips if NLP missing) |
| **Sample** | `mode=sgl` and `bas=nan` only (same filter as NLP) |
| **Paper variables** | Table 9 inputs |
| **Consumed by** | `_mechanism_bubble.csv` |

| Column | Definition |
|--------|------------|
| `mkt_prc` | Cleared price |
| `bubble` | \(1\{P_t>\mathrm{FV}\}\) (default \(\mathrm{FV}=14\); **equality is non-bubble**) |
| `mechanism_id` | Mechanism id aligned with `nlp.py` / paper Table 11 |
| `score_plan` | Parsed `plan_nlp` → `numeric_score` (missing if JSON/mechanism absent) |
| `score_insight` | Parsed `insight_nlp` → `numeric_score` |

This panel stores scores only; bubble FE contrasts are estimated in research ([research.md](research.md)).

---

## 4. Paper mapping (data side)

| Paper object | Pipeline input | End table (see research.md) |
|--------------|----------------|-----------------------------|
| Tables 2–4 | `panels/_behavior` | `_disposition`, `_extrapolation`, `_belief_action` |
| Tables 5–6 | `panels/_equilibrium` | `_bid_offer`, `_disagreement` |
| Tables 7–8 | `panels/_cognition` | `_stated_belief`, `_stated_action` |
| Table 9 | `panels/_mechanism` (via NLP) | `_mechanism_bubble` |

---

## 5. Maintenance

- Changing a panel formula: update `src/analysis/*` and this document together.
- Complementary inventory notes: `docs/paper_v5/data_dictionary.md` (does not replace this contract).
