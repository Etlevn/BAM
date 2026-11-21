# BAM Research End Tables

This document explains **paper-facing** outputs written at the group root `exp/<GROUP>/_<GROUP>/` (not under `research/`). It covers scientific questions, estimating equations, fixed effects / clustering, and how to read coefficients, differences, \(t\)-statistics, and stars.

Upstream data contracts: [pipeline.md](pipeline.md) (integrate + panels), [metrics.md](metrics.md) (Table 1 robust inputs), [nlp.md](nlp.md) (mechanism scores).

**Entries**

| Script | Outputs covered here |
|--------|----------------------|
| `anal.py` (`RUN_MKT_AGG`, optional `RUN_MKT_AGG_PLOT`) | `<GROUP>_mkt_agg.csv` (+ plots) |
| `anal.py` (`RUN_INTERVENTION`) | `<GROUP>_intervention.csv` (Table 10) |
| `research.py` (`RUN_*` flags) | Eight FE coefficient CSVs (Tables 2–9 style) |

Modules under `research/*.py` are libraries only; configure groups once in root `research.py`.

---

## 0. Shared conventions

### 0.1 Defaults

Formal rounds \(T=20\), \(\mathrm{FV}=14\), initial shares \(=4\) unless noted ([pipeline.md](pipeline.md)).

### 0.2 Investor / simulation identifiers

For agent-level FE tables, **Investor FE** uses

\[
\texttt{agent\_id}=\texttt{\{session\}|\{llm\}}
\]

**Simulation FE** is the session id. **Round FE** is the round index. **Market-type FE** (Tables 5–6) is `mode` (`sgl` / `br`).

### 0.3 Stars (FE tables and intervention)

When a \(p\)-value is present:

| Condition | `star` |
|-----------|--------|
| \(p<0.01\) | `***` |
| \(p<0.05\) | `**` |
| \(p<0.1\) | `*` |
| otherwise / non-finite \(p\) | empty |

### 0.4 Long coefficient CSV schema (FE jobs)

Typical columns: `group`, `spec`, `term`, `coef`, `std_err`, `t`, `p`, `star`, `n`, `adj_r2`, `fe_investor`, `fe_round`, `fe_simulation`, `cluster` (plus table-specific fields such as `mechanism_id` / `outcome`).

**How to read:** each row is one estimated coefficient. Match `spec` to the locked column in the paper table; the paper’s parenthetical \(t\) corresponds to column `t`; stars follow §0.3. FE flags document which fixed effects were on for that spec.

---

## 1. Figure 2 — `<GROUP>_mkt_agg.csv`

| | |
|--|--|
| **Question** | How do average prices (with uncertainty) and volumes evolve over rounds within each `mode × bas × series`? |
| **Grain** | `group × mode × bas × series × round` (sessions pooled) |
| **Flag** | `anal.py` `RUN_MKT_AGG` (requires `integrate/_mkt.csv`) |
| **Note** | No BR pair→model expansion (prices/volumes are market-level) |

### Construction

1. Deduplicate `_mkt` at `(group, mode, bas, series, session, round)` keeping `mkt_prc`, `mkt_vol`.
2. Within each `group × mode × bas × series`, for formal round \(t\):

\[
\overline{P}_t=\frac{1}{n_t}\sum_s P_{s,t},\qquad
\mathrm{CI}_t=\text{95\% }t\text{-interval for }\overline{P}_t,\qquad
\overline{V}_t=\frac{1}{n_t}\sum_s V_{s,t}
\]

| Column | Meaning |
|--------|---------|
| `mean_price` | \(\overline{P}_t\) |
| `ci_low` / `ci_up` | 95% CI for mean price |
| `mean_volume` | \(\overline{V}_t\) |
| `fundamental_value` | Constant FV |
| `n` | Sessions contributing to that key×round |

Optional plots (`RUN_MKT_AGG_PLOT`): `_<GROUP>/plots/mkt_agg/{mode}_{bas}_{series}.png`.

---

## 2. Table 2 — Disposition (`<GROUP>_disposition.csv`)

| | |
|--|--|
| **Module** | `research/disposition.py` |
| **Input** | `panels/<GROUP>_behavior.csv` |
| **Flag** | `research.py` `RUN_DISPOSITION` |

### Theory / question

Do AI agents exhibit the **disposition effect**—a higher propensity to sell after paper gains relative to WAPP—and does this survive controlling for stated average price expectations?

### Variables

- \(Y=\texttt{sell\_dummy}\): net seller in the round.
- \(\texttt{gain\_dummy}=1\{P_{t-1}>\mathrm{WAPP}_t\}\).
- \(\texttt{avg\_expectation}\): mean of four forecast prices.

### Locked specs (cluster = agent)

| Spec | Equation | FE |
|------|----------|----|
| 1 | `sell_dummy ~ gain_dummy` | Investor |
| 2 | same | Investor + Round + Simulation |
| 3 | `sell_dummy ~ gain_dummy + avg_expectation` | Investor |
| 4 | same | Investor + Round + Simulation |

**Interpretation:** a positive `gain_dummy` coefficient means agents are more likely to be net sellers after gains (disposition). Specs 3–4 ask whether the effect is absorbed by beliefs (`avg_expectation`).

---

## 3. Table 3 — Extrapolation (`<GROUP>_extrapolation.csv`)

| | |
|--|--|
| **Module** | `research/extrapolation.py` |
| **Input** | `panels/<GROUP>_behavior.csv` |
| **Flag** | `RUN_EXTRAPOLATION` |

### Theory / question

Do agents **extrapolate** recent realized returns into multi-horizon expected returns, and does the strength rise with forecast horizon?

### Variables

- \(Y\in\{\texttt{exp\_ret\_h0},\texttt{exp\_ret\_h2},\texttt{exp\_ret\_h5},\texttt{exp\_ret\_h10}\}\).
- \(X=\{\texttt{ret},\texttt{ret\_lag1},\texttt{ret\_lag2},\texttt{ret\_lag3}\}\) (current and three lagged realized returns).

### Locked specs (cluster = agent)

Odd specs: Investor FE only. Even specs: Investor + Round + Simulation FE. Specs 1–2 → \(h0\); 3–4 → \(h2\); 5–6 → \(h5\); 7–8 → \(h10\).

**Interpretation:** positive loadings on recent returns indicate extrapolative expectations; comparing columns across horizons measures **horizon amplification** (paper narrative: short-run momentum projected into longer horizons).

---

## 4. Table 4 — Belief–action (`<GROUP>_belief_action.csv`)

| | |
|--|--|
| **Module** | `research/belief_action.py` |
| **Input** | `panels/<GROUP>_behavior.csv` |
| **Flag** | `RUN_BELIEF_ACTION` |

### Theory / question

Do period-\(t\) expected returns predict **next-period** net buying (`buy_dummy_next`)?

### Locked specs (cluster = agent)

For each horizon \(h\in\{0,2,5,10\}\), two FE nests (Investor only vs full Investor+Round+Simulation):

\[
\texttt{buy\_dummy\_next}\sim\texttt{exp\_ret\_h\{h\}}
\]

**Interpretation:** positive coefficients mean more bullish forecasts today raise the probability of net buying tomorrow (belief–action coupling).

---

## 5. Table 5 — Bid–offer gap (`<GROUP>_bid_offer.csv`)

| | |
|--|--|
| **Module** | `research/bid_offer.py` |
| **Input** | `panels/<GROUP>_equilibrium.csv` |
| **Flag** | `RUN_BID_OFFER` |
| **Cluster** | session (simulation) |

### Theory / question

Does market-wide **order imbalance** (submitted buy minus sell quantity) predict the next price change?

\[
Y=\texttt{price\_change\_next}=P_{t+1}-P_t,\qquad
X=\texttt{bid\_offer\_gap}
\]

### Locked specs

| Spec | FE |
|------|----|
| 1 | none |
| 2 | Round |
| 3 | Simulation |
| 4 | Round + Simulation |
| 5 | Simulation + Market type (`mode`) |
| 6 | Round + Simulation + Market type |

**Interpretation:** a positive gap coefficient means excess buy pressure forecasts subsequent price increases (disequilibrium adjustment).

---

## 6. Table 6 — Disagreement (`<GROUP>_disagreement.csv`)

| | |
|--|--|
| **Module** | `research/disagreement.py` |
| **Input** | `panels/<GROUP>_equilibrium.csv` |
| **Flag** | `RUN_DISAGREEMENT` |
| **Cluster** | session |

### Theory / question

Is cross-sectional **disagreement** in average price forecasts associated with higher dollar trading volume (Hong–Stein-style channel)?

\[
Y=\texttt{dollar\_volume}=P_t V_t,\qquad
X=\texttt{disagreement}
\]

### Locked specs

| Spec | FE |
|------|----|
| 1 | none |
| 2 | Round |
| 3 | Simulation |
| 4 | Round + Simulation + Market type |

**Interpretation:** a positive coefficient means periods with more dispersed beliefs coincide with more trading activity.

---

## 7. Table 7 — Stated belief (`<GROUP>_stated_belief.csv`)

| | |
|--|--|
| **Module** | `research/stated_belief.py` |
| **Input** | `panels/<GROUP>_cognition.csv` |
| **Flag** | `RUN_STATED_BELIEF` |
| **Cluster** | session |

### Theory / question

Do **stated actions** encoded from plan/insight text align with short- and long-horizon expected returns?

- \(Y\in\{\texttt{exp\_ret\_h0},\texttt{exp\_ret\_h10}\}\) (Methods horizons; no \(\Delta=1\) elicitation).
- \(X\in\{\texttt{stated\_action\_plan},\texttt{stated\_action\_insight}\}\in\{-1,0,1\}\).

### Locked specs (eight columns)

Pairs of Investor-only vs full FE for each \((Y,X)\) combination listed in the module header (specs 1–8).

**Interpretation:** positive coefficients mean more buy-leaning language co-moves with higher expected returns (reasoning ↔ beliefs consistency). Horizon \(h10\) columns test longer-run alignment.

---

## 8. Table 8 — Stated action (`<GROUP>_stated_action.csv`)

| | |
|--|--|
| **Module** | `research/stated_action.py` |
| **Input** | `panels/<GROUP>_cognition.csv` |
| **Flag** | `RUN_STATED_ACTION` |
| **Cluster** | session |

### Theory / question

Do stated actions in text predict **next-period** net buying?

\[
Y=\texttt{buy\_dummy\_next},\qquad
X\in\{\texttt{stated\_action\_plan},\texttt{stated\_action\_insight}\}
\]

### Locked specs (four columns)

Plan vs insight × (Investor FE only vs full Investor+Round+Simulation FE).

**Interpretation:** positive coefficients mean buy-leaning language today raises the chance of net buying tomorrow (reasoning ↔ actions).

---

## 9. Table 9 — Mechanism bubble (`<GROUP>_mechanism_bubble.csv`)

| | |
|--|--|
| **Module** | `research/mechanism_bubble.py` |
| **Input** | `panels/<GROUP>_mechanism.csv` (sgl + `bas=nan`; needs NLP) |
| **Flag** | `RUN_MECHANISM_BUBBLE` |
| **Cluster** | agent |

### Theory / question

Which audited **reasoning mechanisms** score higher during bubble episodes (\(P_t>\mathrm{FV}\)) than in non-bubble rounds, after investor / round / simulation FE?

For each `mechanism_id` and score channel `outcome ∈ {score_plan, score_insight}`:

\[
\texttt{outcome} \sim \texttt{bubble}\ \big|\ \texttt{agent\_id}+\texttt{round}+\texttt{session}
\]

The paper’s “Difference” column is the coefficient on `bubble`. Specs with no within-FE score variation or non-finite inference are skipped.

**Interpretation:** a positive, starred `bubble` coefficient means that mechanism’s NLP score is elevated in bubble states (candidate cognitive driver). Compare plan vs insight channels separately in the long CSV.

---

## 10. Table 10 — Intervention (`<GROUP>_intervention.csv`)

| | |
|--|--|
| **Builder** | `src/analysis/intervention.py` via `anal.py` `RUN_INTERVENTION` |
| **Logic** | **Not** the same as Tables 2–9 FE regressions: BAS **prompt shocks** (amplify / suppress a heuristic) vs same-mode **base** |
| **Outcome** | Session mean formal-round market price (default); **not** NLP \(0\)–\(1\) scores |
| **Paper note** | Table 10 does **not** claim FE + clustered SE; this repo reports Welch two-sample tests |

### Design

For each heuristic, markets run under:

- **Amp** — instructional shock intensifying the heuristic  
- **Sup** — instructional shock dampening it  
- **Bench** — `bas=base` (`b_*` series), pooled **within the same `mode`** (sgl/br never mixed)

Non-BAS (`bas=nan`) rows are dropped. If a group has no BAS sessions, anal skips the file.

### Columns (paper-aligned)

| Column | Meaning |
|--------|---------|
| `mean_amp` / `mean_sup` / `mean_bench` | Arm means of session `mean_price` |
| `diff_amp_bench`, `t_amp_bench`, `p_amp_bench`, `star_amp_bench` | Amp − Bench |
| `diff_sup_bench`, … | Sup − Bench |
| `diff_amp_sup`, … | Amp − Sup |
| `n_amp` / `n_sup` / `n_bench` | Session counts |
| `outcome` | Default `mean_price` |

**Interpretation:** positive Amp−Bench differences mean amplifying that heuristic raises average prices / bubble severity relative to base; negative Sup−Bench differences mean suppression cools prices. Compare to paper Table 10 cells (levels ≈ 15–22 for mean price).

---

## 11. Paper ↔ file map

| Paper | End file at `_<GROUP>/` | Upstream |
|-------|-------------------------|----------|
| Table 1 | (cells from) `metrics/*_market_robust_{sgl,br}.csv` | [metrics.md](metrics.md) |
| Figure 2 | `_mkt_agg.csv` | `integrate/_mkt` |
| Table 2 | `_disposition.csv` | `panels/_behavior` |
| Table 3 | `_extrapolation.csv` | `panels/_behavior` |
| Table 4 | `_belief_action.csv` | `panels/_behavior` |
| Table 5 | `_bid_offer.csv` | `panels/_equilibrium` |
| Table 6 | `_disagreement.csv` | `panels/_equilibrium` |
| Table 7 | `_stated_belief.csv` | `panels/_cognition` |
| Table 8 | `_stated_action.csv` | `panels/_cognition` |
| Table 9 | `_mechanism_bubble.csv` | `panels/_mechanism` ← NLP |
| Table 10 | `_intervention.csv` | BAS sessions in `_mkt` |

---

## 12. Suggested run order

1. `integ.py` → integrate tables  
2. `nlp.py` (if Table 9) → `nlp/`  
3. `anal.py` → metrics, panels, `mkt_agg`, `intervention`  
4. `research.py` → eight FE CSVs  

---

## 13. Maintenance

- Locked FE specs live in `research/*.py` headers and `SPECS` tuples; changing a paper column requires updating the module **and** this document.
- Do not reintroduce a `_<GROUP>/research/` output directory; end tables stay at the group root.
