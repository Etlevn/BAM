# AIT (AI Trading)

**Behavioral finance and market dynamics of LLM traders in an experimental stock market.**

Laboratory asset markets have shown that prices can leave a known fundamental value when traders form expectations and trade with one another. AIT is the computational market used to ask that question of language models. Each trader is an LLM. It receives the market rules, its portfolio, and the history so far, then returns limit orders, a price forecast, and the plans and insights it writes down. The market clears the orders into a price, settles cash, shares, dividends, and interest, and carries that state into the next period.

The same rules run in two compositions. In a single-model market every trader is one model. In a heterogeneous market several models share a fixed set of traders and clear against one another. A two-model market is that second composition with two model entries.

Each run records prices, volume, orders, holdings, wealth, forecasts, and the text the model produced. The record lines those objects up as:

```text
plans and insights → forecasts → orders → holdings and wealth → market price
```

Plans and insights are model-generated text. They are the trader’s stated account of the period, not a direct observation of an internal reasoning process. This repository runs the market, stores that record, and prepares it for analysis.

## Research question

Under the same cash, inventory, dividend, and clearing constraints:

1. Do different models state different plans and submit different forecasts and orders?
2. How do those differences appear in prices, volume, holdings, and wealth when one model trades alone, and when several models trade in the same market?

The market summaries measure how far prices move from fundamental value, how forecasts compare with later prices, and how dispersed those results are across repeated runs. A separate coding step scores plans and insights against a fixed list of behavioral-finance mechanisms. Those summaries and scores describe the record. They do not by themselves identify why a price path occurred.

## What the system does

- Runs a multi-period stock market whose price is formed from the traders’ own limit orders, then updates holdings, cash, dividends, and interest.
- Gives every trader the same prompt structure, portfolio state, and market history.
- Runs a single-model market, or a heterogeneous market in which several models are assigned to a fixed set of traders.
- Repeats full experiments in batch, with logs and a configuration snapshot for each run.
- Checks structured model output and repairs malformed JSON before it enters the order book. A failed model call can pause that trader and wait for a retry.
- Integrates prices, orders, holdings, forecasts, and model text into tables indexed by run, trader, and period.
- Summarizes price deviation from fundamental value, forecast error, and cross-run dispersion.
- Scores plans and insights for a fixed list of behavioral-finance mechanisms.

Experiment outputs, logs, and API keys are not part of the repository. Each run writes them locally.

## Market design

Default parameters live in `config.py` (`EXPERIMENT_CONFIG`). Prompt templates under `prompt/` are filled from that config at runtime.

| Parameter | Default | Role |
| --- | --- | --- |
| Initial cash | 100 | Cash each trader starts with |
| Initial shares | 4 | Shares each trader starts with |
| Terminal value | 14 | Cash paid per share after the last round |
| Interest rate | 5% | Interest credited on cash each round |
| Dividend | 0.4 or 1.0 | Low and high dividend per share |
| Dividend probability | 0.5 | Weight on the low dividend |
| Practice rounds | 3 | Rounds used to learn the market |
| Trading rounds | 20 | Formal rounds |

The trader prompt describes the dividend as a random draw of 0.4 or 1.0 each period, identical for every trader. Settlement in `src/portfolio/settle.py` follows `EXPERIMENT_CONFIG["dividend_mode"]`: `"fixed"` credits the expectation each round (0.7 at defaults; legacy), `"random"` draws one common low/high for all traders that round. Interest is then credited on cash. After the last trading round, remaining shares are converted at the terminal value, not at the last market price.

Orders are limit orders and are not carried across periods. A trader cannot sell more shares than it holds or spend more cash than it has. `src/market/clearing.py` clears the book by searching for the price that maximizes traded volume. If several prices tie, it uses their average, rounded down. If the two sides do not cross, it sets the price to the bid–ask midpoint. If the book is empty or one-sided, the previous price stands.

## How a run proceeds

`main.py` creates **one** session directory per run (`YYYYMMDD_HHMMSS`; retries if that second is taken). When `practice_rounds` is greater than zero, practice runs under `{session}/prac/`, then formal rounds use the session root (`input/`, `output/`, `market/`). Round 0 lives at `{io_root}/input/r0/`. Practice reflections are written directly to formal `{session}/input/r0/*_reflection.txt`.

Each round does the following:

1. Read the previous period’s plans, insights, reflection, market history, and portfolio.
2. Ask the assigned model for orders, forecasts, and updated plans and insights.
3. Validate the response and repair malformed JSON when `AUTO_JSON_FIX` is on.
4. Write the order book and clear a market price.
5. Update each trader’s shares, cash, dividend, and interest, and write the next period’s input files.

Round 0 defaults are generated by `prepare.py` under `{io_root}/input/r0/`. Later rounds read `input/r<N-1>/` and write `output/r<N>/`, `market/`, and the next `input/` directory.

```text
Round 0 state (input/r0)
        │
        ▼
Prompt + model call
        │
        ▼
Structured output (output/rN/*.json)
        │
        ├── orders   → plans, insights, order book
        ├── clearing → market/rN.csv and mkt.csv
        └── settle   → next market.txt and portfolio.txt
```

## Requirements

Python 3.12 or 3.13.

```bash
pip install -e .
```

The main dependencies are `edsl` (Expected Parrot), `openai`, `pandas`, `numpy`, `python-dotenv`, `matplotlib`, `seaborn`, `scipy`, and `statsmodels`.

Copy `.env.example` to `.env` in the repository root, then set the key for the API mode you select in `config.py`. Do not commit `.env`.

```bash
cp .env.example .env
```

## Configuration

All experiment settings are in `config.py`.

### Experiment output path

New runs are written under:

```text
exp/{EXP_GROUP}/{series}/{YYYYMMDD_HHMMSS}/
```

- `EXP_GROUP` is required in `config.py` (for example `2_EP` or `3_BR`). An empty value aborts startup.
- `series` is automatic: single-model uses the sanitized `model_name` (`/` → `_`); battle-royale joins sanitized model names with ` & `.

### Market composition

`EXPERIMENT_MODE` is `"sgl"` or `"br"`.

- **Single model (`sgl`).** Every trader uses `SINGLE_MODEL_CONFIG`. `num_llms` is the number of traders. `service_name` is optional and is passed through to Expected Parrot when set (for example `deep_infra`, `google`, or `together`).
- **Battle Royale (`br`).** This is the heterogeneous market. Traders are split across `BATTLE_ROYALE_CONFIG["custom_models"]`. Two entries make a two-model market; more entries make a larger mix. The trader count is the sum of each model’s `count`. `assignment_strategy` is `sequential`, `random`, or `balanced`. The assignment is saved as `br_config.json` inside the run directory. A single-model run saves `sgl_config.json`.

### API mode

`API_CONFIG["api_mode"]` is one of:

- `expected_parrot` — models are called through Expected Parrot / EDSL
- `openai`
- `deepseek`

### Prompts and BAS mode

Shared prompts live in `prompt/`. With `USE_BAS_MODE`, `BAS_BIAS_ID` (`base` / `amp_NN` / `sup_NN`) overlays one sentence onto templates and prefixes the series folder (`b_` / `aNN_` / `sNN_`). Works for sgl and br; `base` is an empty shock (in-group benchmark). Set `USE_BAS_MODE=False` for unprefixed standard templates.

### Other switches

- `AUTO_JSON_FIX` repairs JSON after each round and can keep a backup.
- `DEBUG_CONFIG["save_raw_responses"]` stores the raw model text before parsing.
- `batch.py` sets `NUM_RUNS`, the number of full experiments to launch in sequence.

## Running an experiment

From the repository root:

```bash
python main.py
```

One invocation creates a run directory under `exp/`, runs practice (if configured), then runs the formal market. Logs go to `log/`.

To repeat the same configuration:

```bash
python batch.py
```

`batch.py` stops the batch if a run exits with a non-zero status. A failed model call can also pause inside `ord.py` and wait for Enter before retrying that trader.

## Recorded data

A run directory contains:

| Path | Contents |
| --- | --- |
| `config.json` | Unified session config (models, assignments, experiment snapshot, `status`) |
| `input/rN/` | Plans, insights, reflection, market history, and portfolio shown to each trader |
| `output/rN/` | Model JSON: plans, insights, price forecasts, and submitted orders |
| `market/rN.csv` | Orders and executions for that round |
| `market/mkt.csv` | Price and volume by round |

`integ.py` (backed by `src/integ/`) turns those files into group-level tables. Edit the config block at the top of `integ.py` to choose first-level folders under `exp/` (for example `SGL`, `BR`). For each group it scans formal sessions, reads `market_type` and `llm` assignments from that session's `config.json`, and writes only under a result folder whose name mirrors the on-disk first-level directory (same spelling/case, with a leading `_`):

- `exp/SGL/_SGL/SGL_rx.csv` — orders from `market/r*.csv`
- `exp/SGL/_SGL/SGL_mkt.csv` — portfolio / market history / forecasts from `input/.../*_market.txt`
- `exp/SGL/_SGL/SGL_output.csv` — obs / plan / insight from `output/r*/llm_*.json`

`classify_group_sessions` in `src/integ/session.py` (used by `integ.py`) does both in one pass: `status=complete` formal sessions are merged; `status=running` (and sessions with no config yet) are left in place; other non-complete sessions are moved under `exp/<GROUP>/<series>/_incomplete/<session>/`. Intermediate per-session integ CSVs are not written.

```bash
python integ.py
```

## Analysis

`anal.py` (backed by `src/analysis/`) mirrors `integ.py`: edit `GROUPS` at the top, then run from the repo root. It reuses `classify_group_sessions` (complete formal sessions only; running/no-config left in place; other non-complete moved to `<series>/_incomplete/`). Fundamental value and total rounds come from `config.EXPERIMENT_CONFIG` (`stock_value`, `total_rounds`). Outputs land under `exp/<GROUP>/_<GROUP>/`:

- `<GROUP>_market.csv` — session-level MSE(FV), amplitude, portfolio-value variance
- `<GROUP>_market_robust.csv` — long-form summary by `group × series × Metric` (mean / std / CV / 95% CI)
- `<GROUP>_rational.csv` — session-level forecast rationality (MSE, error distribution, unbiasedness, AR(1)/DW)
- `<GROUP>_rational_robust.csv` — same robust long form for rationality metrics

```bash
python anal.py
```

## NLP

`nlp.py` (backed by `src/nlp/`) mirrors `integ.py` / `anal.py`: set `GROUPS` and `RUN_CODE` / `RUN_POST` at the top. API/model/workers/mechanism list live in the same file. Prompt template is `prompt/nlp_prmt.txt`. For each group it reads `exp/<GROUP>/_<GROUP>/<GROUP>_output.csv` and writes:

- `nlp/*.json` — per-row plan/insight mechanism coding
- `<GROUP>_output_nlp.csv` — output table with `plan_nlp` / `insight_nlp` columns
- `<GROUP>_output_miss.csv` — rows missing plan and/or insight JSON

```bash
python nlp.py
```

## Repository layout

```text
config.py                 parameters only
main.py                   entry → src.runtime.runner
integ.py                  entry → src.integ (group CSV tables)
anal.py                   entry → src.analysis (market + rationality)
nlp.py                    entry → src.nlp (mechanism coding / merge / miss)
src/market/               clearing, order book prep
src/agents/               trading calls, validate, battle
src/portfolio/            settle, dividend, prepare
src/prompts/              build, fill
src/runtime/              setup, paths, runner, batch
src/integ/                orders, snapshots, outputs aggregation
src/analysis/             market metrics, rationality, robustness
src/nlp/                  mechanism coding, merge, miss
src/support/              utils, repair, collect
prompt/                   trading + NLP prompts (+ bas_biases.json)
```

`exp/`, `log/`, and `.env` are gitignored. `prompt/` holds read-only templates at the repo root. Per-run writable state (including `input/r0/` and `prac/`) lives only under each session directory in `exp/`.
