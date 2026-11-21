# BAM NLP Mechanism-Coding Tables

This document describes mechanism-audit outputs under `exp/<GROUP>/_<GROUP>/nlp/`. Coding scores feed the Table 9 panel (`panels/<GROUP>_mechanism.csv`; see [pipeline.md](pipeline.md)) and the bubble FE table (`_<GROUP>/<GROUP>_mechanism_bubble.csv`; see [research.md](research.md)).

**Entry:** `nlp.py` (`RUN_CODE`, `RUN_POST`, `RUN_REFILL_MISS`).  
**Upstream:** `integrate/<GROUP>_output.csv` (plan / insight text).  
**Model / prompt:** same API backends as trading (`API_MODE` / `MODEL_NAME`); template `prompt/nlp_prmt.txt`.

---

## 1. Sample filter

All NLP coding, merge, and miss logic keep only rows with:

- `mode=sgl`
- `bas=nan` (literal non-BAS marker)

`br` and BAS sessions are **excluded**. Legacy columns: `market_type` → `mode`; empty/`null` `bas` → literal `nan`.

---

## 2. Per-row JSON files

| | |
|--|--|
| **Path** | `_<GROUP>/nlp/` |
| **Typical name** | `{session}_{round}_{llm}_{plan\|insight}.json` |
| **Content** | Structured mechanism assessments for one plan or insight text (e.g. DeepSeek / configured auditor) |

Each JSON encodes relevance of the twenty behavioral / non-behavioral mechanisms (paper Table 11 taxonomy) used elsewhere as `mechanism_id` with numeric scores on a continuous scale (typically \(0\)–\(1\)).

---

## 3. `nlp/<GROUP>_output_nlp.csv`

| | |
|--|--|
| **Flag** | `RUN_POST` (written together with the miss table) |
| **Grain** | agent × round on the filtered sgl + `bas=nan` subset of `integrate/_output.csv` |

Adds NLP payloads to the baseline output panel:

| Column | Definition |
|--------|------------|
| `plan_nlp` | Plan scoring JSON as a string (or empty if missing) |
| `insight_nlp` | Insight scoring JSON as a string (or empty if missing) |

Other identity / text columns follow the integrate output schema ([pipeline.md](pipeline.md) §2.3).

---

## 4. `nlp/<GROUP>_output_miss.csv`

| | |
|--|--|
| **Purpose** | List agent×round rows still missing plan and/or insight JSON (for refill) |
| **Schema** | Same columns as the filtered output panel |

If nothing is missing, the file is still written as an **empty table with headers only**, so stale miss files are not left behind.

---

## 5. Refill workflow (`RUN_REFILL_MISS`)

| | |
|--|--|
| **Mutual exclusion** | Cannot run with `RUN_CODE` in the same invocation |
| **Steps** | Read existing `output_miss` (error if absent) → call the API only for still-missing plan/insight sides (skip existing JSON) → full remake of `output_nlp` → rescan JSON and overwrite `output_miss` |
| **With `RUN_POST`** | Refill already includes post; `RUN_POST` is ignored when refill runs |

---

## 6. Downstream use

1. `anal.py` `RUN_MECHANISM` joins `integrate/_mkt` with `output_nlp`, parses `plan_nlp` / `insight_nlp` into long scores → `panels/<GROUP>_mechanism.csv`.
2. `research.py` `RUN_MECHANISM_BUBBLE` regresses scores on a bubble indicator with investor / round / simulation FE → `_<GROUP>/<GROUP>_mechanism_bubble.csv`.

Missing JSON for a mechanism yields missing scores on the panel; research skips non-estimable specs rather than inventing zeros.

---

## 7. Maintenance

- Mechanism id order and names must stay aligned across `nlp.py`, `src/analysis/mechanism.py` (`MECHANISM_ORDER`), and paper Table 11.
- Changing the auditor prompt or score schema requires regenerating JSON and re-running merge / mechanism / research.
