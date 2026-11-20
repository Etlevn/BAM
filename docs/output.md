# BAM — `exp/<GROUP>/_<GROUP>/` 结果表说明

本文档说明各 group 汇总目录下、与 **整合 / 分析 / NLP** 相关的关键 CSV（及 Figure 2 图）的用途、字段含义与计算公式。  
路径形如：`exp/SGL/_SGL/SGL_*.csv`、`exp/BR/_BR/BR_*.csv`。

**约定：**

- 正式交易轮默认 \(T=20\)（`config.EXPERIMENT_CONFIG["total_rounds"]`）。
- 基本价值默认 \(\mathrm{FV}=14\)（`stock_value`）。
- 初始持股默认 \(4\)（`initial_stocks`）。
- 下表中的「开关」指根目录入口脚本顶部的布尔配置。

---

## 0. 公共键列（integ / 多数面板共用）

| 字段 | 含义 |
|------|------|
| `group` | 第一层实验组名（如 `SGL`、`BR`、`BAS`） |
| `series` | 第二层系列（单模型名，或 `modelA & modelB`；BAS 常带 `b_` / `a01_` / `s20_` 前缀） |
| `session` | 第三层场次目录名（时间戳） |
| `market_type` | `sgl` 或 `br` |
| `bas` | BAS bias id；非 BAS 常为字面量 `null` 或空 |
| `round` | 轮次（正式期多为 1…20） |
| `llm` | 交易者 id（如 `llm_001`） |
| `llm_type` | 该席位对应的模型名 |

---

## 1. Integ 整合表（`integ.py`）

### 1.1 `<GROUP>_mkt.csv`

**粒度：** agent × round  
**来源：** 各 session 的 `input/r*` 市场/持仓/预测文本  
**用途：** 市场价格、持仓、预测面板；Figure 2（`_mkt_agg`）与 Tables 2–4（`_behavior`）的上游。

| 字段 | 含义 |
|------|------|
| `mkt_prc` | 该轮市场清算价 \(P_t\) |
| `mkt_vol` | 该轮市场成交量 |
| `stk_num` | 该轮结束后持股数量 |
| `stk_val` | 持股按市价计的价值 |
| `cash` | 现金 |
| `div` / `int` | 股息 / 利息 |
| `fcst_k_rnd` / `fcst_k_prc` | 第 \(k\) 个预测的目标轮次与预测价格（通常 \(k=1..4\)，horizon 约 0/2/5/10） |

同一 `(session, round)` 下，所有 agent 的 `mkt_prc`/`mkt_vol` 相同（市场级），持仓与预测因人而异。

### 1.2 `<GROUP>_rx.csv`

**粒度：** 订单行（agent × round × 单笔订单）  
**来源：** 各 session `market/r*.csv`  
**用途：** 提交/成交订单；构造卖出/买入 dummy 与 WAPP 更新。

| 字段 | 含义 |
|------|------|
| `b/s` | `BUY` / `SELL` |
| `num` | 提交数量 |
| `prc` | 限价 |
| `mkt` | 该轮清算价 |
| `ord` | 成交数量（约等于成交份数；`0` 表示未成交） |
| `deal` | 成交价（未成交多为 `0`） |

### 1.3 `<GROUP>_output.csv`

**粒度：** agent × round  
**来源：** 模型输出中的 plan / insight 文本  
**用途：** NLP 审计输入。

| 字段 | 含义 |
|------|------|
| `obs` | 其它观测/原文片段（若有） |
| `plan` | 交易计划文本 |
| `insight` | 经验/洞察文本 |

---

## 2. Anal — 市场质量（`anal.py`）

### 2.1 `<GROUP>_market.csv`

**粒度：** session（一场实验一行）  
**开关：** `RUN_MARKET`  
**论文：** Table 1 的 session 级原料（再经 robust 按系列平均）。

对正式轮 \(t=1,\ldots,T\)：

\[
\mathrm{MSE}(\mathrm{FV})=\frac{1}{T}\sum_{t=1}^{T}(P_t-\mathrm{FV})^2
\]

\[
\mathrm{Amplitude}=\max_{t\in\{1,\ldots,T\}} P_t-\mathrm{FV}
\]

\[
\mathrm{PV\ Variance}=\frac{1}{T}\sum_{t=1}^{T}\mathrm{Var}_i\!\left(\mathrm{PV}_{i,t}\right)
\]

其中 \(\mathrm{PV}_{i,t}=\) 现金 + 预期赎回价值（`Expected redemption`，按 \(\mathrm{FV}\times\) 持股），\(\mathrm{Var}_i\) 为该轮横截面方差（实现为 `numpy.var`，总体方差）。

| 字段 | 含义 |
|------|------|
| `rounds` | 计入的正式轮数 |
| `mse` | 上式 MSE(FV) |
| `amplitude` | 上式 Amplitude |
| `pv_variance` | 上式 PV Variance |

### 2.2 `<GROUP>_market_robust.csv`

**粒度：** `(group, series, Metric)` 长表  
**开关：** `RUN_MARKET_ROBUST`  
**做法：** 对 `_market.csv` 中同一 `series` 下各 session 的 `mse` / `amplitude` / `pv_variance` 做**等权**汇总。

| 字段 | 含义 |
|------|------|
| `Metric` | `mse` / `amplitude` / `pv_variance` |
| `Mean` | 跨 session 算术平均（Table 1 主用） |
| `StdDev` | 样本标准差（\(n-1\)） |
| `CV` | \(\mathrm{StdDev}/\mathrm{Mean}\) |
| `95% CI Lower` / `Upper` | 对 Mean 的 95% \(t\) 置信区间（SEM + `t.interval`） |
| `CI Width / Mean` | 区间宽度 / Mean |
| `n` | session 数 |

### 2.3 `<GROUP>_market_agg_robust.csv`（仅 BR）

**开关：** `RUN_MARKET_AGG_ROBUST`  
**做法：** 将配对 `series`（`A & B`）拆成单模型：一场 BR 的 MSE/Amp/PV **复制两行**，`series` 改为模型 A、B；再按 2.2 同样做 Mean / CI。  
**论文：** Table 1 **Mixed-Model** 列（按模型加总）。  
不落盘中间明细表。

### 2.4 `<GROUP>_mkt_agg.csv`

**粒度：** round（组内跨所有 session）  
**开关：** `RUN_MKT_AGG`（**必须**已有 `_mkt.csv`，否则报错）  
**论文：** Figure 2 数据。

步骤：

1. 从 `_mkt` 按 `(session, round)` 去重，保留 `mkt_prc`、`mkt_vol`。  
2. 对每个正式轮 \(t\)，令 \(\{P_{s,t}\}\) 为各 session 价格：

\[
\overline{P}_t=\frac{1}{n_t}\sum_s P_{s,t},\quad
\mathrm{CI}_t=\text{95\% }t\text{-interval of }\overline{P}_t
\]

\[
\overline{V}_t=\frac{1}{n_t}\sum_s V_{s,t}
\]

| 字段 | 含义 |
|------|------|
| `round` | 正式轮次 |
| `mean_price` | \(\overline{P}_t\) |
| `ci_low` / `ci_up` | 价格均值的 95% CI |
| `mean_volume` | \(\overline{V}_t\) |
| `fundamental_value` | FV（常数列） |
| `n` | 该轮有效 session 数 |

### 2.5 `plots/_mkt_agg.png`

**开关：** `RUN_MKT_AGG_PLOT`（默认关）  
均价曲线 + CI 阴影 + 成交量柱 + FV 虚线（Figure 2 风格）。依赖 `_mkt_agg.csv` 或同次运行的 `RUN_MKT_AGG`。

### 2.6 `plots/<series>/<session>.png`

**开关：** `RUN_PLOTS`  
单场双轴价量图（旧版样式），与 Table 1/2 无直接对应。

---

## 3. Anal — 预测理性（`anal.py`）

### 3.1 `<GROUP>_rational.csv`

**粒度：** session  
**开关：** `RUN_RATIONAL`  

从各 agent 输出中的 `price_forecasts` 对齐真实成交价，预测误差：

\[
e=\hat{P}-P_{\mathrm{true}}
\]

| 字段 | 含义 |
|------|------|
| `mse` | 预测的均方误差 \(\overline{(\hat{P}-P)^2}\) |
| `mean_error` / `std_error` | 误差均值 / 标准差 |
| `skewness` / `kurtosis` | 误差分布偏度 / 峰度 |
| `t_stat_error` / `p_val_error` | 误差均值是否为 0 的单样本 \(t\) 检验 |
| `ar1_coef` / `ar1_pval` | 误差对自身滞后的 AR(1) 系数与 p 值 |
| `dw_stat` | Durbin–Watson（残差序列相关） |

### 3.2 `<GROUP>_rational_robust.csv`

**开关：** `RUN_RATIONAL_ROBUST`  
对 `_rational.csv` 按 `series` 做与 2.2 相同的 Mean / Std / CV / 95% CI 长表。

---

## 4. Anal — 行为面板 Tables 2–4（`anal.py`）

### 4.1 `<GROUP>_behavior.csv`

**粒度：** agent × round  
**开关：** `RUN_BEHAVIOR`（**必须** `_mkt` + `_rx`，否则报错）  
**论文：** Tables 2–4 变量（本仓库当前只算数据，不输出 FE 回归表）。

#### 订单汇总（由 `_rx`）

| 字段 | 含义 |
|------|------|
| `buy_submitted` / `sell_submitted` | 本轮提交买/卖数量合计 |
| `buy_filled_qty` / `buy_filled_cost` | 成交买入数量、\(\sum(\mathrm{ord}\times\mathrm{deal})\) |
| `sell_dummy` | \(1\{\text{sell\_submitted}>\text{buy\_submitted}\}\)（Table 2 因变量） |
| `buy_dummy` | \(1\{\text{buy\_submitted}>\text{sell\_submitted}\}\) |
| `buy_dummy_next` | 下一轮的 `buy_dummy`（Table 4：用本期预期解释下期买入） |

#### WAPP 与 Gain（Table 2）

- 初始：WAPP \(=\mathrm{FV}\)，持股 \(=\) `initial_stocks`。  
- 仅**买入成交**更新：

\[
\mathrm{WAPP}'=\frac{S\cdot\mathrm{WAPP}+Q_{\mathrm{buy}}\cdot\bar{P}_{\mathrm{deal}}}{S+Q_{\mathrm{buy}}}
\]

卖出不改变 WAPP。  
- `wapp`：本轮**开始**时的 WAPP。  
- `gain_dummy`：\(1\{P_{t-1}>\mathrm{WAPP}_t\}\)；\(t=1\) 时 \(P_{0}:=\mathrm{FV}\)。  
- `avg_expectation`：本轮四个 `fcst_*_prc` 的算术平均。

#### 收益与预期收益（Table 3）

\[
r_t=\frac{P_t-P_{t-1}}{P_{t-1}}
\]

| 字段 | 含义 |
|------|------|
| `ret` | 本轮实现收益 \(r_t\) |
| `ret_lag1`…`ret_lag4` | \(r_{t-1},\ldots,r_{t-4}\) |
| `exp_ret_h0/h2/h5/h10` | 若预测目标相对本轮 \(\Delta\in\{0,2,5,10\}\)：\(\hat{P}/P_t-1\) |

---

## 5. Anal — 均衡面板 Tables 5–6（`anal.py`）

### 5.1 `<GROUP>_equilibrium.csv`

**粒度：** session × round（市场层）  
**开关：** `RUN_EQUILIBRIUM`（**必须** `_mkt` + `_rx`，否则报错）  
**论文：** Tables 5–6 变量（只算数据，不输出 FE 回归表）。

| 字段 | 含义 |
|------|------|
| `mkt_prc` / `mkt_vol` | 该轮清算价、成交量（`_mkt` 按 session×round 去重） |
| `price_change_next` | \(P_{t+1}-P_t\)（Table 5 因变量） |
| `bid_offer_gap` | \(\sum Q_{\mathrm{buy}}^{\mathrm{sub}}-\sum Q_{\mathrm{sell}}^{\mathrm{sub}}\)（全体提交量差） |
| `buy_submitted` / `sell_submitted` | 该轮全市场提交买/卖总量 |
| `disagreement` | 各 agent「四期限预测价格均值」的横截面样本标准差 |
| `dollar_volume` | \(P_t\times V_t\)（清算成交金额） |
| `n_agents` | 该轮有有效平均预期的 agent 数 |

最后一轮无 `price_change_next`（为缺失）。

---

## 6. Anal — 认知一致性面板 Tables 7–8（`anal.py`）

### 6.1 `<GROUP>_cognition.csv`

**粒度：** agent × round  
**开关：** `RUN_COGNITION`（**必须** `_mkt` + `_rx` + `_output`，否则报错）  
**论文：** Tables 7–8 变量（只算数据，不输出 FE 回归表）。  
**不用** `_output_nlp` 机制评分（那是 Table 9）。

#### Stated Action（文本方向）

对 `plan` / `insight` 分别统计买入 / 卖出关键词出现次数（默认词表见 `src/analysis/cognition.py` 的 `BUY_KEYWORDS` / `SELL_KEYWORDS`；整词、大小写不敏感；不计 order/bid/hold 等）：

\[
\mathrm{net}=n_{\mathrm{buy}}-n_{\mathrm{sell}},\quad
\mathrm{Stated\ Action}=\operatorname{sign}(\mathrm{net})\in\{-1,0,1\}
\]

缺文本 → **缺失**（≠ 0）。Plan / Insight 分开编码为 `stated_action_plan` / `stated_action_insight`；并保留词数 `buy_kw_*` / `sell_kw_*`。

#### 预期收益（Table 7）

与 `_behavior` 相同：\(\hat{P}/P_t-1\)，按 Methods \(h\in\{0,2,5,10\}\) 写入 `exp_ret_h*`；`exp_ret_t10`=`exp_ret_h10`。

论文 Table 7 表头曾写 \(R_{t+1}\)；已决定按 Methods/代码 \(h\in\{0,2,5,10\}\) 为准，**不与该表头对齐**（见 `docs/paper/definition_audit.md`）。短期与 Table 3 相同，用 `exp_ret_h0` 等。

自变量为**当轮** Stated Action；因变量为**当轮**预期收益。

#### 下期买入（Table 8）

| 字段 | 含义 |
|------|------|
| `buy_dummy` | 与 `_behavior` 相同：\(1\{\text{buy\_submitted}>\text{sell\_submitted}\}\) |
| `buy_dummy_next` | 下一轮 `buy_dummy`（Table 8：用 \(t\) 的 Stated Action 解释 \(t{+}1\) 净买入） |

---

## 7. Anal — 机制面板 Table 9（`anal.py`）

### 7.1 `<GROUP>_mechanism.csv`

**粒度：** agent × round × mechanism（长表，20 机制 × 每 agent–round）  
**开关：** `RUN_MECHANISM`（**必须** `_mkt` + `_output_nlp`，否则报错）  
**论文：** Table 9 变量（只算数据；泡沫差与 FE 后置）。

| 字段 | 含义 |
|------|------|
| `mkt_prc` | 该轮清算价 |
| `bubble` | \(1\{P_t>\mathrm{FV}\}\)（默认 \(\mathrm{FV}=14\)；**等于 14 为非泡沫**） |
| `mechanism_id` | 与 `nlp.py` / Table 11 对齐的机制 id |
| `score_plan` | 解析 `plan_nlp` → `numeric_score`（缺 JSON / 缺该机制为缺失） |
| `score_insight` | 解析 `insight_nlp` → `numeric_score` |

不做 FE 差分回归；不自动调用 DeepSeek。

---

## 8. Anal — 干预面板 Table 10（`anal.py`）

### 8.1 `<GROUP>_intervention.csv`（通常 `BAS`）

**粒度：** session（一场 BAS 实验一行）  
**开关：** `RUN_INTERVENTION`（**必须** 该组 `_mkt`；Benchmark 为**同组** `bas=base` / series `b_*`，不读外部 group）  
**论文：** Table 10 原料（市场层均价；**不是** NLP 0–1 分）。

| 字段 | 含义 |
|------|------|
| `bas` | bias id（`base` / `amp_01`…`sup_20`） |
| `arm` | `base` / `amp` / `sup` |
| `mechanism_id` | `amp_XX`/`sup_XX` → 机制；`base` 为空 |
| `model` | 从 `series` 去掉 `b_` / `a01_` / `s01_` 前缀 |
| `mean_price` | 正式轮 session×round 清算价均值（Table 10 主结果量级 ≈14–22） |
| `mse` / `amplitude` / `pv_variance` | 若有 `_market.csv` 则按 session 合并 |
| `bench_mean_price` | 同组 `arm=base` 各场 `mean_price` 的池化均值 |
| `bench_source` | 固定 `base` |
| `n_bench` | base 场次数 |

运行：`BAS_BIAS_ID=base|amp_NN|sup_NN`（sgl/br 皆可；只改 prompt + 前缀 `b_`/`aNN_`/`sNN_`）。`RUN_ALL_BAS`：base → 40 amp/sup。

### 8.2 `<GROUP>_intervention_mech.csv`

**粒度：** mechanism（20 行）  
由 `_intervention` 汇总：`mean_amp` / `mean_sup` / `mean_bench`，以及 Amp−Bench、Sup−Bench、Amp−Sup 的差分与 Welch \(t\)（Bench 为同组 base 场次样本）。**不是**论文最终 FE 表；缺 base 或样本过少时 \(t\) 可能缺失。

操控检验（NLP 分数）未并入本文件，可后置。

---

## 9. NLP（`nlp.py`）

### 9.1 `nlp/*.json`

单条 plan/insight 的机制评分 JSON（DeepSeek 等）。文件名约：`{session}_{round}_{llm}_{plan|insight}.json`。

### 9.2 `<GROUP>_output_nlp.csv`

**开关：** `RUN_POST`（与 miss 合并）  
在 `_output.csv` 上增加：

| 字段 | 含义 |
|------|------|
| `plan_nlp` | 对应 plan 评分 JSON 原文（字符串） |
| `insight_nlp` | 对应 insight 评分 JSON 原文 |

### 9.3 `<GROUP>_output_miss.csv`

列出 plan 或 insight JSON **缺失** 的 agent×round 行（便于补跑），列结构同 output 面板。

---

## 10. 与论文表的对应（数据侧）

| 论文 | 主要数据文件 |
|------|----------------|
| Table 1 Single | `_market_robust`（按模型 `series`） |
| Table 1 Mixed | `_market_agg_robust`（BR，按单模型） |
| Figure 2 | `_mkt_agg`（+ 可选 `_mkt_agg.png`） |
| Tables 2–4 | `_behavior` |
| Tables 5–6 | `_equilibrium` |
| Tables 7–8 | `_cognition` |
| Table 9 | `_mechanism`（依赖 `_output_nlp`） |
| Table 10 | `_intervention` / `_intervention_mech`（BAS；Bench=`base`/`b_*`） |
| 预测理性（方法/辅助） | `_rational` / `_rational_robust` |

---

## 11. 维护说明

- 改指标口径时：同步改 `src/analysis/*` 实现与本文公式。  
- A1 inventory 字段见 `docs/paper_v5/data_dictionary.md`（与本文互补，不替代）。  
- 生成入口：`integ.py` / `anal.py` / `nlp.py`。
