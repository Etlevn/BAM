# LLM Trading Analysis Project

本项目是一个基于大语言模型（LLM）的交易分析实验系统，用于研究多个LLM代理在模拟交易环境中的行为表现。

## 目录

- [环境准备](#环境准备)
- [项目配置](#项目配置)
  - [环境变量配置](#环境变量配置)
  - [主程序配置](#主程序配置)
- [运行主程序](#运行主程序)
- [模块说明](#模块说明)
  - [anal/ 分析模块](#anal-分析模块)
  - [data_proc/ 数据处理模块](#data_proc-数据处理模块)
  - [nlp/ 自然语言处理模块](#nlp-自然语言处理模块)

---

## 环境准备

### 1. Python 环境

确保系统已安装 Python 3.8 或更高版本。

### 2. 安装依赖

在项目根目录下运行：

```bash
pip install -r requirements.txt
```

主要依赖包括：
- `edsl` - 实验设计支持库
- `pandas` - 数据处理
- `numpy` - 数值计算
- `python-dotenv` - 环境变量管理
- `matplotlib`, `seaborn` - 数据可视化
- `scipy`, `statsmodels` - 统计分析

---

## 项目配置

### 环境变量配置

在项目根目录创建 `.env` 文件，并配置所需的 API 密钥：

```bash
# OpenAI API (用于 openai 模式)
OPENAI_API_KEY=your_openai_api_key_here

# Expected Parrot API (用于 expected_parrot 模式)
EXPECTED_PARROT_API_KEY=your_expected_parrot_api_key_here

# DeepSeek API (用于 deepseek 模式)
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

**注意**：
- 根据在 `config.py` 中配置的 `api_mode`，至少需要配置对应的 API 密钥。
- 请勿将 `.env` 文件提交到版本控制系统。建议在 `.gitignore` 中添加 `.env`。

### 主程序配置

编辑 `config.py` 文件，配置以下关键选项：

#### 1. 实验模式选择 (EXPERIMENT_MODE)

选择实验运行模式：

```python
EXPERIMENT_MODE = "sgl"  # "sgl" 单模型模式 或 "br" 大逃杀模式
```

- **"sgl" (Single Model Mode)**: 所有代理使用同一个模型
- **"br" (Battle Royale Mode)**: 多个不同模型进行竞争

**注意**: 切换 `EXPERIMENT_MODE` 时，请确保对应的配置（`SINGLE_MODEL_CONFIG` 或 `BATTLE_ROYALE_CONFIG`）已正确设置。

#### 2. 单模型模式配置 (SINGLE_MODEL_CONFIG)

当 `EXPERIMENT_MODE = "sgl"` 时，配置以下参数：

```python
SINGLE_MODEL_CONFIG = {
    "num_llms": 20,                    # LLM 代理总数
    "model_name": "gpt-4o",            # 使用的模型名称
    "description": "ChatGPT-4o",       # 模型描述（可选）
    "service_name": "",                # 服务名称（如 "deep_infra", "google", "together"），留空使用默认
}
```

#### 3. 大逃杀模式配置 (BATTLE_ROYALE_CONFIG)

当 `EXPERIMENT_MODE = "br"` 时，配置以下参数：

```python
BATTLE_ROYALE_CONFIG = {
    "assignment_strategy": "sequential",  # 分配策略: "random", "sequential", "balanced"
    "custom_models": [
        {
            "name": "claude-3-7-sonnet-20250219",
            "count": 10,
            "description": "Claude 3.7 Sonnet",
            "service_name": ""
        },
        {
            "name": "gemini-2.0-flash-001",
            "count": 10,
            "description": "Gemini 2.0 Flash",
            "service_name": ""
        }
    ]
}
```

#### 4. API 模式配置 (API_CONFIG)

```python
API_CONFIG = {
    "api_mode": "expected_parrot",  # "openai", "expected_parrot", 或 "deepseek"
    # API 密钥从 .env 文件自动加载
}
```

#### 5. BAS 模式配置 (USE_BAS_MODE)

```python
USE_BAS_MODE = True  # True: 使用 BAS 模式提示文件, False: 使用标准提示文件
```

当 `USE_BAS_MODE = True` 时，系统会从 `init/prompt/bas/` 目录读取 BAS 模式的提示文件。

**默认配置**：

在 `config.py` 中的 `PROMPT_FILES_BAS` 默认配置为：

```python
PROMPT_FILES_BAS = {
    "experiment_start": "experiment_start_amp_1.txt",  # BAS 模式实验启动提示
    "order_forecast_end": "order_forecast_end_amp_1.txt",  # BAS 模式订单预测结束提示
}
```

**切换不同配置**：

BAS 模式支持通过手动修改 `config.py` 中的文件名来切换不同的配置组合。

在 `init/prompt/bas/` 目录下，提供了以下文件：

- **amplify 系列**（20 种配置，编号 1-20）：
  - `experiment_start_amp_1.txt` 到 `experiment_start_amp_20.txt`
  - `order_forecast_end_amp_1.txt` 到 `order_forecast_end_amp_20.txt`

- **suppress 系列**（20 种配置，编号 1-20）：
  - `experiment_start_sup_1.txt` 到 `experiment_start_sup_20.txt`
  - `order_forecast_end_sup_1.txt` 到 `order_forecast_end_sup_20.txt`

**使用方法**：

要切换到不同的配置，只需修改 `config.py` 中的 `PROMPT_FILES_BAS` 字典。例如：

```python
# 使用 amp_5 配置
PROMPT_FILES_BAS = {
    "experiment_start": "experiment_start_amp_5.txt",
    "order_forecast_end": "order_forecast_end_amp_5.txt",
}

# 或使用 sup_10 配置
PROMPT_FILES_BAS = {
    "experiment_start": "experiment_start_sup_10.txt",
    "order_forecast_end": "order_forecast_end_sup_10.txt",
}

# 或使用 amp_20 配置
PROMPT_FILES_BAS = {
    "experiment_start": "experiment_start_amp_20.txt",
    "order_forecast_end": "order_forecast_end_amp_20.txt",
}
```

**配置组合说明**：

- 共有 **40 种不同的配置组合**：
  - 20 种 amp 配置（amp_1 到 amp_20）
  - 20 种 sup 配置（sup_1 到 sup_20）
- 每种配置包含两个文件：
  - `experiment_start_*.txt`：实验启动提示文件
  - `order_forecast_end_*.txt`：订单预测结束提示文件
- 两个文件必须使用**相同的后缀**（如同时使用 amp_5 或同时使用 sup_10）

**注意事项**：

1. 修改 `PROMPT_FILES_BAS` 后，确保对应的文件存在于 `init/prompt/bas/` 目录中
2. `experiment_start` 和 `order_forecast_end` 应使用相同的配置编号（如都使用 amp_5 或都使用 sup_10）
3. 文件名格式必须严格匹配：`experiment_start_[amp|sup]_[1-20].txt` 和 `order_forecast_end_[amp|sup]_[1-20].txt`

#### 6. 实验参数配置 (EXPERIMENT_CONFIG)

```python
EXPERIMENT_CONFIG = {
    "initial_cash": 100,          # 初始现金
    "initial_stocks": 4,          # 初始股票数量
    "stock_value": 14,            # 股票基础价值
    "interest_rate": 0.05,        # 利率
    "dividend_low": 0.4,          # 股息下限
    "dividend_high": 1.0,         # 股息上限
    "dividend_prob": 0.5,         # 股息概率
    "practice_rounds": 3,         # 练习轮数
    "total_rounds": 20            # 总轮数
}
```

---

## 运行主程序

配置完成后，在项目根目录运行：

```bash
python main.py
```

主程序将按以下流程执行：

1. **初始化实验目录**：在 `exp/` 目录下创建新的实验运行目录
2. **准备 Round 0**：生成初始市场和投资组合文件
3. **运行练习轮**（如果 `practice_rounds > 0`）：
   - 执行指定轮数的练习
   - 完成后运行反思提示
4. **运行正式轮**：
   - 执行 `total_rounds` 轮正式实验
   - 每轮包括：LLM 决策 → 订单处理 → 市场价格清算 → 投资组合更新

实验结果将保存在 `exp/` 目录下的对应实验文件夹中。

---

## 数据文件流转说明

理解数据文件在练习轮和正式轮之间的流转过程对于理解实验机制至关重要。以下是每个轮次中数据文件的生成和流转流程：

### Round 0（初始化阶段）

**生成位置**：`init/r0/`

**生成文件**：
- `llm_XXX_r0_market.txt` - 初始市场信息（价格、成交量、持仓等）
- `llm_XXX_r0_portfolio.txt` - 初始投资组合信息（现金、持股数等）
- `llm_XXX_r0_plans.txt` - 初始计划文件（内容为 "(NONE)"）
- `llm_XXX_r0_insights.txt` - 初始洞察文件（内容为 "(NONE)"）

这些文件由 `prep.prepare_round_zero()` 根据实验配置生成，作为第一轮的输入数据。

### Round N（N ≥ 1）- 数据流转流程

每一轮（包括练习轮和正式轮）的数据流转包括以下步骤：

#### 1. 输入文件读取（Round N 开始）

**读取位置**：
- Round 1：从 `init/r0/` 读取
- Round N (N > 1)：从 `exp/[timestamp]/input/r{N-1}/` 读取

**读取文件**：
- `llm_XXX_r{N-1}_plans.txt` - 上一轮的计划
- `llm_XXX_r{N-1}_insights.txt` - 上一轮的洞察
- `llm_XXX_r{N-1}_reflection.txt` - 反思内容（练习轮后或存在时）
- `llm_XXX_r{N-1}_market.txt` - 上一轮的市场信息
- `llm_XXX_r{N-1}_portfolio.txt` - 上一轮的投资组合信息

#### 2. Prompt 生成与 LLM 调用

**模块**：`ord.run_experiment_round()`

**过程**：
- 读取提示模板（从 `init/prompt/` 或 `init/prompt/bas/`）：
  - `experiment_start.txt` / `experiment_start_amp_X.txt` / `experiment_start_sup_X.txt`
  - `experiment_conditions.json`
  - `order_forecast_start.txt`
  - `order_forecast_end.txt` / `order_forecast_end_amp_X.txt` / `order_forecast_end_sup_X.txt`
  - `order_forecast_template.json`
- 组合上述输入文件和提示模板，生成完整的 Prompt
- 调用 LLM API（根据配置的 API 模式）
- 解析 LLM 响应

#### 3. LLM 输出保存

**保存位置**：`exp/[timestamp]/output/r{N}/`

**生成文件**：
- `llm_XXX_r{N}.json` - LLM 的完整响应，包含：
  - `new_content.PLANS.txt` - 新生成的计划
  - `new_content.INSIGHTS.txt` - 新生成的洞察
  - `new_content.price_forecasts` - 价格预测（如果适用）
  - `submitted_orders` - 提交的订单（订单类型、数量、限价）

#### 4. 输出处理与下一轮输入准备

**模块**：`proc.prepare_next_round()`

**处理过程**：
- 从 `output/r{N}/llm_XXX_r{N}.json` 提取数据
- 提取 `PLANS.txt` 和 `INSIGHTS.txt` 内容
- 保存到 `input/r{N}/`：
  - `llm_XXX_r{N}_plans.txt` ← 提取自 JSON
  - `llm_XXX_r{N}_insights.txt` ← 提取自 JSON
- 提取订单数据并记录到订单簿

#### 5. 市场价格清算

**模块**：`mkt.compute_market_price()`

**生成文件**：
- `exp/[timestamp]/market/r{N}.csv` - 该轮的订单和成交数据
- 更新 `exp/[timestamp]/market/mkt.csv` - 累积的市场价格和成交量数据

#### 6. 市场与投资组合信息生成

**模块**：`pfl.compute_market_and_portfolio_all()`

**生成位置**：`exp/[timestamp]/input/r{N}/`

**生成文件**：
- `llm_XXX_r{N}_market.txt` - 当前轮的市场信息，包含：
  - 市场价格和成交量
  - 持仓和现金变化
  - 股息和利息收入
  - 提交的订单和执行情况
- `llm_XXX_r{N}_portfolio.txt` - 当前轮的投资组合信息，包含：
  - 当前市场价格
  - 回购价格
  - 持股数量和现金
  - 股票价值和预期赎回价值

这些文件将作为下一轮（Round N+1）的输入文件。

### 练习轮（Practice Rounds）的特殊流程

练习轮（`mode="prac"`）与正式轮的数据流转流程相同，但在所有练习轮结束后会执行额外的**反思轮（Reflection Round）**：

**反思轮（Round practice_rounds + 1）**：
- **输入**：使用练习轮的所有历史数据
- **输出**：生成 `llm_XXX_r{practice_rounds}_reflection.txt`
- **保存位置**：`exp/[timestamp]/input/r{practice_rounds}/`
- **用途**：反思内容将作为正式轮第一轮的输入之一

### 数据流转示意图

```
Round 0 (init/r0/)
    ↓
[市场/组合/计划/洞察文件]
    ↓
Round 1 输入 (input/r0/ 或 init/r0/)
    ↓
Prompt 生成 + LLM 调用 (ord.py)
    ↓
LLM 输出 (output/r1/*.json)
    ↓
输出处理 (proc.py) → 生成 plans.txt, insights.txt → input/r1/
    ↓
市场价格清算 (mkt.py) → market/r1.csv
    ↓
市场/组合生成 (pfl.py) → input/r1/_market.txt, _portfolio.txt
    ↓
Round 2 输入 (input/r1/)
    ↓
[循环继续...]
```

### 关键目录结构

```
exp/[timestamp]/
├── input/
│   ├── r1/          # Round 1 的输入文件（市场、组合、计划、洞察）
│   ├── r2/          # Round 2 的输入文件
│   └── ...
├── output/
│   ├── r1/          # Round 1 的 LLM 输出（JSON 文件）
│   ├── r2/          # Round 2 的 LLM 输出
│   └── ...
└── market/
    ├── r1.csv       # Round 1 的订单数据
    ├── r2.csv       # Round 2 的订单数据
    └── mkt.csv      # 累积的市场价格和成交量
```

---

## 模块说明

**注意**: 运行分析模块和 NLP 模块前，请确保主程序已成功运行并生成相应的数据文件。

### anal/ 分析模块

分析模块用于对实验结果进行统计分析。

#### 配置文件：`anal/anal_config.json`

```json
{
  "base_dir": "/path/to/experiment/directory",
  "fundamental_value": 14
}
```

**配置说明**：
- `base_dir`: 实验目录的绝对路径（可以是单个实验目录或包含多个实验的父目录）
- `fundamental_value`: 股票的基础价值（默认 14）

#### 运行方法

**1. 基础分析 (anal.py)**

计算每个实验的轮数、MSE（均方误差）、振幅和投资组合方差，并生成价格-成交量双轴图：

```bash
python anal/anal.py --config anal/anal_config.json
```

如果不指定 `--config`，默认使用 `anal/anal_config.json`。

**2. RAT 分析 (rat.py)**

分析价格预测误差，计算 MSE、误差分布统计、无偏性 t 检验和自相关：

```bash
python anal/rat.py --config anal/anal_config.json
```

**3. ROB 稳健性分析 (rob.py)**

计算分析结果的稳健性统计（均值、标准差、变异系数、95% 置信区间）：

```bash
python anal/rob.py --config anal/anal_config.json
```

---

### data_proc/ 数据处理模块

数据处理模块用于整合和合并实验产生的各种数据文件。

#### 配置文件说明

**1. all_integ_config.json** - 统一集成配置

用于一次性运行所有数据处理流程：

```json
{
  "market_type": "sgl",
  "root_directory": "/path/to/project/root",
  "experiment_directory": "exp",
  "run_market": true,
  "run_rx": true,
  "run_output": true,
  "market_output_filename": "_mkt.csv",
  "rx_output_filename": "_rX.csv",
  "output_output_filename": "_output.csv"
}
```

**配置说明**：
- `market_type`: 市场类型（"sgl" 或 "br"）
- `root_directory`: 项目根目录路径
- `experiment_directory`: 实验目录名称（相对于 root_directory）
- `run_market`, `run_rx`, `run_output`: 是否运行对应的处理流程
- `*_output_filename`: 各流程的输出文件名

**2. market_integ_config.json** - 市场数据整合配置

```json
{
  "market_type": "sgl",
  "root_directory": "/path/to/project/root",
  "experiment_directory": "",
  "output_filename": "_mkt.csv"
}
```

**3. rx_integ_config.json** - 响应数据整合配置

```json
{
  "market_type": "sgl",
  "root_directory": "/path/to/project/root",
  "experiment_directory": "",
  "output_filename": "_rX.csv"
}
```

**4. output_integ_config.json** - 输出数据整合配置

```json
{
  "market_type": "sgl",
  "root_directory": "/path/to/project/root",
  "experiment_directory": "",
  "output_filename": "_output.csv"
}
```

**5. integ_merger_config.json** - 批量合并配置

用于将多个实验的结果合并为单个 CSV 文件：

```json
{
  "root_directory": "/path/to/project/root",
  "out_dir": "_sgl",
  "run_rx": true,
  "rx_expected_filename": "_rX.csv",
  "rx_merged_output": "sgl_rx.csv",
  "run_market": true,
  "market_expected_filename": "_mkt.csv",
  "market_merged_output": "sgl_mkt.csv",
  "run_output": true,
  "output_expected_filename": "_output.csv",
  "output_merged_output": "sgl_output.csv"
}
```

#### 运行方法

**1. 统一运行所有数据处理流程**

```bash
python data_proc/all_integ.py --config data_proc/all_integ_config.json
```

**2. 单独运行各处理流程**

```bash
# 市场数据整合
python data_proc/market_integ.py --config data_proc/market_integ_config.json

# 响应数据整合
python data_proc/rx_integ.py --config data_proc/rx_integ_config.json

# 输出数据整合
python data_proc/output_integ.py --config data_proc/output_integ_config.json
```

**3. 批量合并多个实验结果**

```bash
python data_proc/integ_merger.py --config data_proc/integ_merger_config.json
```

---

### nlp/ 自然语言处理模块

NLP 模块用于分析 LLM 交易代理输出中的行为偏差。

#### 配置文件：`nlp/nlp_config.json`

```json
{
  "file_settings": {
    "default_input_file": "/path/to/input.csv",
    "prompt_template": "nlp_prmt_2.txt"
  },
  "processing_settings": {
    "max_processing_rows": null,
    "max_workers": 100
  },
  "output_settings": {
    "save_individual_json": true
  },
  "api_settings": {
    "api_mode": "deepseek",
    "model_name": "deepseek-chat"
  },
  "evaluation_settings": {
    "evaluate_plan": true,
    "evaluate_insight": true
  },
  "mechanism_order": [
    "rational_speculative_bubble",
    "synchronization_risk",
    "asymmetric_information",
    "extrapolation_vs_anchor",
    "diagnostic_expectations",
    "wavering_behavior",
    "disposition_effect",
    "momentum_vs_newswatcher",
    "feedback_trading",
    "overconfidence",
    "self_attribution_bias",
    "herding_contagion",
    "disagreement_heterogeneous_beliefs",
    "representativeness_heuristic",
    "new_era_thinking",
    "availability_bias",
    "limited_arbitrage_awareness",
    "loss_aversion",
    "narrative_tone",
    "statistical_testing"
  ]
}
```

**配置说明**：
- `file_settings`: 输入文件和提示模板配置
- `processing_settings`: 处理设置（最大处理行数、并发工作线程数）
- `output_settings`: 输出设置（是否保存单独的 JSON 文件）
- `api_settings`: API 配置（API 模式和模型名称）
- `evaluation_settings`: 评估设置（是否评估计划和洞察）
- `mechanism_order`: 行为机制评估顺序列表
- `max_workers`: 多线程处理，可根据系统性能调整

#### 运行方法

**主程序 (nlp_main.py)**

```bash
python nlp/nlp_main.py --input /path/to/input.csv --output /path/to/output/ --config nlp/nlp_config.json
```

**参数说明**：
- `--input`: 输入 CSV 文件路径（必需）
- `--output`: 输出目录路径（必需）
- `--config`: 配置文件路径（可选，默认使用 `nlp/nlp_config.json`）

**合并结果 (nlp_merge.py)**

合并多个 NLP 分析结果：

```bash
python nlp/nlp_merge.py --input_dir /path/to/nlp/results/ --output /path/to/merged_output.csv
```

**缺失数据处理 (nlp_miss.py)**

处理分析过程中缺失的数据：

```bash
python nlp/nlp_miss.py --input /path/to/input.csv --output /path/to/output/
```

---

## 项目结构

```
LLM_TRD/
├── config.py              # 主配置文件
├── main.py                # 主程序入口
├── .env                   # 环境变量（需自行创建）
├── requirements.txt       # Python 依赖
├── anal/                  # 分析模块
│   ├── anal_config.json
│   ├── anal.py
│   ├── rat.py
│   └── rob.py
├── data_proc/             # 数据处理模块
│   ├── all_integ_config.json
│   ├── all_integ.py
│   ├── market_integ_config.json
│   ├── market_integ.py
│   ├── rx_integ_config.json
│   ├── rx_integ.py
│   ├── output_integ_config.json
│   ├── output_integ.py
│   ├── integ_merger_config.json
│   └── integ_merger.py
├── nlp/                   # NLP 模块
│   ├── nlp_config.json
│   ├── nlp_main.py
│   ├── nlp_merge.py
│   └── nlp_miss.py
├── exp/                   # 实验输出目录（自动创建）
├── log/                   # 日志目录（自动创建）
└── init/                  # 初始化文件目录
    ├── prompt/            # 提示文件
    │   ├── bas/           # BAS 模式提示文件
    │   └── ...            # 标准提示文件
    └── ...
```