# BAM — Behavioral Agent Markets

*LLM Trading Agents for Stock Market Simulation and Behavioral Finance Research*

Paper: *Dissecting AI Trading: Behavioral Finance and Market Bubbles* (Ouyang & Sui). This repository implements the market, stores run records, and builds the group-level tables used for analysis. Field definitions and estimating equations live under [`docs/`](docs/).

## What this repo does

- Runs multi-period open-call auctions where every trader is an LLM (single-model or mixed-model markets).
- Records plans/insights, forecasts, orders, holdings, wealth, prices, and volume per session.
- Optionally overlays BAS amplification / suppression prompt shocks.
- Aggregates completed sessions into group CSVs, scores text against a fixed mechanism list, and estimates paper-style panels / FE tables.

Run artifacts (`exp/`, `log/`) and API keys (`.env`) stay local and are gitignored.

## Pipeline at a glance

```text
main.py / batch.py     →  exp/<GROUP>/<series>/<session>/
integ.py               →  _<GROUP>/integrate/
nlp.py                 →  _<GROUP>/nlp/          (optional; Table 9 path)
anal.py                →  _<GROUP>/metrics/, panels/, root mkt_agg & intervention
research.py            →  _<GROUP>/ FE coefficient CSVs
```

| Doc | Contents |
| --- | --- |
| [docs/pipeline.md](docs/pipeline.md) | `integrate/` and `panels/` |
| [docs/metrics.md](docs/metrics.md) | `metrics/` |
| [docs/nlp.md](docs/nlp.md) | `nlp/` |
| [docs/research.md](docs/research.md) | Root end tables (Figure 2, Tables 2–10 style) |

## Requirements

Python 3.12 or 3.13.

```bash
pip install -e .
cp .env.example .env   # set keys for the API mode in config.py; do not commit .env
```

Main dependencies include `edsl`, `openai`, `pandas`, `numpy`, `python-dotenv`, `matplotlib`, `seaborn`, `scipy`, `statsmodels`, and `pyfixest` (for `research.py`).

## Configure and run experiments

All experiment settings live in [`config.py`](config.py).

### Output path

```text
exp/{EXP_GROUP}/{series}/{YYYYMMDD_HHMMSS}/
```

- `EXP_GROUP` is required (e.g. `SGL`, `BR`, `BAS`). Empty aborts startup.
- `series` is automatic: single-model → sanitized `model_name`; battle-royale → models joined with ` & `. With BAS on, series are prefixed `b_` / `aNN_` / `sNN_`.

### Market composition (`EXPERIMENT_MODE`)

| Mode | Meaning |
| --- | --- |
| `sgl` | Every trader uses `SINGLE_MODEL_CONFIG` (`num_llms` seats). |
| `br` | Heterogeneous market: seats from `BATTLE_ROYALE_CONFIG["custom_models"]`; assignment `sequential` / `random` / `balanced` (saved as `br_config.json`). |

### API mode

`API_CONFIG["api_mode"]`: `expected_parrot` | `openai` | `deepseek`.

### BAS prompts

Shared templates are under `prompt/`. With `USE_BAS_MODE`, `BAS_BIAS_ID` (`base` / `amp_NN` / `sup_NN`) injects a one-line shock and prefixes the series folder. `base` is the in-group benchmark (empty shock). Set `USE_BAS_MODE=False` for unprefixed runs.

### Launch

```bash
# group + mode + BAS id + model (other settings from config.py)
python main.py SGL sgl base gpt-4o
python main.py BR br off "gpt-4o,claude-3-7-sonnet-20250219"
python main.py   # config.py as-is

python batch.py  # repeat NUM_RUNS; stops on non-zero exit
```

One `main.py` invocation creates one session under `exp/`, runs practice (if configured), then formal rounds. Logs go to `log/`. A failed model call can pause and wait for Enter before retrying that trader.

Other useful switches: `AUTO_JSON_FIX`, `DEBUG_CONFIG["save_raw_responses"]`.

## How a run proceeds

`main.py` creates one session directory (`YYYYMMDD_HHMMSS`). Practice (if any) lives under `{session}/prac/`; formal rounds use the session root. Round 0 state is under `{io_root}/input/r0/`.

Each formal round:

1. Read prior plans, insights, reflection, market history, and portfolio.
2. Call the assigned model for orders, forecasts, and updated text.
3. Validate / optionally repair JSON (`AUTO_JSON_FIX`).
4. Clear the book and write `market/`.
5. Settle shares, cash, dividend, and interest; write the next `input/`.

```text
input/r0  →  prompt + model  →  output/rN/*.json
                ├── orders / plans / insights
                ├── clearing → market/rN.csv, mkt.csv
                └── settle   → next market.txt / portfolio.txt
```

## Market design (defaults)

Parameters: `config.EXPERIMENT_CONFIG`. Prompts under `prompt/` are filled at runtime.

| Parameter | Default | Role |
| --- | --- | --- |
| Initial cash | 100 | Starting cash |
| Initial shares | 4 | Starting shares |
| Terminal value | 14 | Cash per share after the last round (FV) |
| Interest rate | 5% | Interest on cash each round |
| Dividend | 0.4 or 1.0 | Low / high dividend |
| Dividend probability | 0.5 | Weight on the low dividend |
| Practice rounds | 3 | Learning rounds |
| Trading rounds | 20 | Formal rounds |

Settlement (`src/portfolio/settle.py`) follows `dividend_mode`: `"fixed"` credits expected dividend each round; `"random"` draws one common low/high for all traders. After the last round, shares redeem at terminal value.

Orders are limit orders and do not carry across periods. No short sales beyond holdings; no spend beyond cash. Clearing (`src/market/clearing.py`) maximizes traded volume; tied prices average (floored); no cross → bid–ask midpoint; empty/one-sided book → previous price.

## Session record layout

| Path | Contents |
| --- | --- |
| `config.json` | Session config, assignments, experiment snapshot, `status` |
| `input/rN/` | Plans, insights, reflection, market history, portfolio shown to traders |
| `output/rN/` | Model JSON: plans, insights, forecasts, orders |
| `market/rN.csv` | Orders and fills that round |
| `market/mkt.csv` | Price and volume by round |

## Offline analysis

Edit `GROUPS` (and flags) at the top of each entry script, then run from the repo root. Group outputs live under `exp/<GROUP>/_<GROUP>/`.

### Integrate — `integ.py`

Scans complete formal sessions; merges into `integrate/`. Non-complete sessions (except `running` / missing config) move to `<series>/_incomplete/`.

- `integrate/<GROUP>_mkt.csv` — prices, holdings, forecasts  
- `integrate/<GROUP>_rx.csv` — orders  
- `integrate/<GROUP>_output.csv` — plan / insight text  

```bash
python integ.py
```

### NLP — `nlp.py` (optional)

Codes `mode=sgl` and `bas=nan` rows only. Writes under `nlp/`: per-row JSON, `<GROUP>_output_nlp.csv`, `<GROUP>_output_miss.csv`. `RUN_REFILL_MISS` is mutually exclusive with `RUN_CODE`.

```bash
python nlp.py
```

### Analyze — `anal.py`

Produces `metrics/` (market + rational, plus robust splits), `panels/` (behavior / equilibrium / cognition / mechanism), root `<GROUP>_mkt_agg.csv`, and root `<GROUP>_intervention.csv` (BAS Table 10 when applicable).

```bash
python anal.py
```

### Research FE — `research.py`

Reads `panels/` and writes coefficient CSVs at the group root (`_disposition`, `_extrapolation`, …, `_mechanism_bubble`). Toggle with `RUN_*` flags. Modules under `research/` are libraries, not standalone CLIs.

```bash
python research.py
```

## Repository layout

```text
config.py                 experiment + API parameters
main.py                   one session → src.runtime.runner
batch.py                  repeated sessions
integ.py                  → src.integ
anal.py                   → src.analysis
nlp.py                    → src.nlp
research.py               → research/* FE jobs
src/market/               clearing, order book
src/agents/               LLM calls, validate, battle-royale
src/portfolio/            settle, dividend, prepare
src/prompts/              build / fill
src/runtime/              setup, paths, runner, batch
src/integ/                group aggregation
src/analysis/             metrics, panels, intervention
src/nlp/                  mechanism coding, merge, miss
src/support/              utils, repair
research/                 FE table modules (library)
prompt/                   trading + NLP templates (+ BAS)
docs/                     pipeline / metrics / nlp / research contracts
tests/                    unit tests
```

`exp/`, `log/`, and `.env` are gitignored. Writable session state lives only under `exp/`.
