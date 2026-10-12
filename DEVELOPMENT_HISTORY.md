# LLM_TRD 项目开发历史

## 项目概述

**项目名称**: LLM Trading Analysis (LLM_TRD)  
**初始提交**: 2025-08-04  
**最新更新**: 2026-01-05  
**主要开发者**: Etlevn  
**总提交数**: 32  

这是一个基于大语言模型（LLM）的交易分析项目，主要用于金融市场分析和交易策略研究。

---

## 开发时间线

### 第一阶段：项目初始化 (2025-08-04)

#### 初始提交 (836cbc0)
- **提交信息**: Initial commit: LLM Trading Analysis project
- **主要内容**:
  - 创建项目基础结构
  - 添加核心模块：
    - `main.py` - 主程序入口
    - `mkt.py` - 市场数据处理
    - `ord.py` - 订单处理
    - `pfl.py` - 投资组合管理
    - `prep.py` - 数据预处理
    - `proc.py` - 数据处理
    - `prompt.py` - Prompt工程
    - `batch.py` - 批处理功能
  - 添加分析模块（Jupyter Notebooks）：
    - `anal/anal.ipynb` - 基础分析
    - `anal/filt.ipynb` - 过滤分析
    - `anal/rat.ipynb` - 比率分析
    - `anal/robust.ipynb` - 稳健性分析
  - 初始化Prompt系统：
    - `init/prompt/experiment_start.txt` - 实验启动Prompt
    - `init/prompt/order_forecast_start.txt` - 订单预测开始Prompt
    - `init/prompt/order_forecast_end.txt` - 订单预测结束Prompt
    - `init/prompt/order_forecast_template.json` - 订单预测模板
    - `init/prompt/experiment_conditions.json` - 实验条件配置
  - 创建配置文件：`requirements.txt`, `.gitignore`
  - **统计**: 21个文件，3693行新增代码

---

### 第二阶段：API集成与架构重构 (2025-08-04)

#### API集成和代码重构 (7a02743)
- **主要功能**:
  - 添加统一的API系统，支持OpenAI和Expected Parrot
  - 将JSON工具和订单验证提取到独立模块
  - 改进配置管理
  - 更新`.gitignore`文件

#### API密钥管理优化 (525ff74)
- **改进内容**:
  - 将OpenAI和Expected Parrot API密钥移至`.env`文件
  - 更新配置以从环境变量加载
  - 为Expected Parrot函数添加API密钥配置

---
### 第三阶段：核心功能增强 (2025-08-07 - 2025-08-21)

#### 战斗模式（Battle Royale）和JSON解析改进 (e0fd82a)
- **新功能**: 添加Battle Royale模式
- **改进**: JSON解析功能优化

#### Bug修复 (d38b27f)
- **修复问题**:
  - 网络错误处理
  - None响应处理
  - Reflection格式问题

#### 重大改进 (ce7a687)
- **改进内容**:
  - XML标签处理
  - 调试系统
  - 简化JSON提取
  - 代码注释英文化

#### BR模式配置优化 (13f812f)
- **优化**: 自动使用custom_models总和配置机制

---

### 第四阶段：数据处理模块完善 (2025-09-05 - 2025-09-25)

#### 输出集成模块 (d901448)
- **新增功能**:
  - 添加`output_integ`模块及配置
  - 更新`integ_merger`以支持`_output.csv`
  - 支持单层文件发现
  - 调整`_output.csv`的列顺序
  - 从merger配置中移除`market_type`

#### 依赖项更新 (621b7fa, 8de2eba)
- 为rat分析添加`scipy`和`statsmodels`依赖
- 将脚本输出消息切换为英文

#### 代码国际化 (21e1b4b)
- 将代码注释翻译为英文
- 进行少量文案编辑

#### 项目同步 (0e6577d)
- 添加`data_proc`集成模块
- 更新`batch.py`, `config.py`, `utils.py`
- 更新notebooks

#### 实验模式重构和HTML收集 (55ea283)
- 重构实验模式
- 添加HTML收集脚本

#### JSON修复工具 (384019d)
- **重大功能**:
  - 提取`json_fix.py`模块
  - 添加全局根目录扫描
  - 在集成器中跳过备份
  - 将备份移至`output/backup`
  - 添加错误转储
  - CLI支持`root/all`参数
  - 配置驱动的备份/启用选项
  - 日志包含实验/组/根目录摘要
  - 添加`SINGLE_MODEL_CONFIG.description`

#### 集成模块自动化 (11c0e78, 4fe8e58)
- 在`*_integ`模块中自动扫描实验
- 为`integ_merger`统一输出目录
- 统一`sgl_llm_type`从每个实验的`sgl_config`获取源
- 更新rx/output/market集成器
- 调整`all_integ`模块

---

### 第五阶段：NLP模块添加 (2025-10-27)

#### NLP模块 (1720f9b)
- **新增功能**:
  - 添加NLP模块，包含缺失数据检测
  - 结果合并功能

---

### 第六阶段：Prompt工程优化 (2025-11-30 - 2025-12-22)

#### Prompt版本选择功能 (ed1cc75)
- 添加`experiment_start` prompt版本选择功能
- 创建`experiment_start_amplify.txt`和`experiment_start_suppress.txt`

#### Prompt工程优化 (eb65ec4)
- 改进`experiment_start`版本选择
- 强化交易策略提示
- 移除旧的amplify/suppress文件

#### Prompt文件重构 (b1a250f, af1892a, 212ec27)
- 重命名prompt文件并更新配置
- 创建多个版本的prompt文件（amp/sup系列）
- 添加更多版本的实验启动和订单预测结束prompt

---

### 第七阶段：BAS模式支持 (2025-12-28 - 2026-01-04)

#### Prompt文件扩展 (247d1a0, 9f129ed)
- 添加更多版本的prompt文件
- 支持多种实验条件组合

#### BAS模式支持 (1fae7b8)
- **重大更新**:
  - 添加BAS模式支持
  - 将prompt文件重组到`bas/`目录
  - 创建20个版本的实验启动prompt（amp 1-20, sup 1-20）
  - 创建对应的订单预测结束prompt
  - 更新配置以支持BAS模式

#### Prompt文件继续扩展 (f515ef9, 4dda1f5)
- 添加更多版本的prompt文件（amp/sup 4, 5, 8）

---

### 第八阶段：代码清理与文档化 (2026-01-05)

#### 代码清理 (494d5b1)
- 将中文注释翻译为英文
- 移除冗余注释
- 清理不必要的文件（如`test.py`）
- **统计**: 8个文件修改，18行新增，172行删除

---

## 分支结构

项目包含以下主要分支：

1. **main** - 主分支，稳定的发布版本
2. **bas** - BAS模式开发分支
3. **integration** - 数据集成功能开发分支
4. **battle_royale** - Battle Royale模式开发分支

---

## 核心模块演进

### 数据处理模块 (data_proc/)
- `rx_integ.py` - 接收数据集成
- `output_integ.py` - 输出数据集成
- `market_integ.py` - 市场数据集成
- `integ_merger.py` - 集成合并器
- `all_integ.py` - 全部集成

### 分析模块 (anal/)
- 从Jupyter Notebooks演化为Python脚本
- `anal.py` - 基础分析
- `rat.py` - 比率分析
- `rob.py` - 稳健性分析

### NLP模块 (nlp/)
- `nlp_main.py` - NLP主程序
- `nlp_miss.py` - 缺失数据检测
- `nlp_merge.py` - 结果合并
- `nlp_utils.py` - NLP工具函数

### Prompt系统 (init/prompt/)
- 从单一版本演化为多版本系统
- 支持多种实验模式（BAS, AMP, SUP）
- 版本化prompt管理
- 实验条件配置化

---

## 技术栈

- **编程语言**: Python
- **API集成**: OpenAI, Expected Parrot
- **数据分析**: scipy, statsmodels
- **配置管理**: JSON配置文件, 环境变量
- **数据格式**: CSV, JSON
- **版本控制**: Git

---

## 主要里程碑

1. **2025-08-04**: 项目初始化，核心架构建立
2. **2025-08-04**: API系统集成完成
3. **2025-08-07**: Battle Royale模式添加
4. **2025-09-05**: 数据处理模块完善
5. **2025-09-22**: JSON修复工具上线
6. **2025-10-27**: NLP模块添加
7. **2025-11-30**: Prompt版本选择功能
8. **2026-01-04**: BAS模式全面支持
9. **2026-01-05**: 代码国际化完成

---

## 开发特点

1. **迭代式开发**: 持续优化和重构
2. **模块化设计**: 功能模块独立，便于维护
3. **配置驱动**: 大量使用配置文件，提高灵活性
4. **多模式支持**: 支持多种实验模式和交易策略
5. **国际化**: 代码和文档逐步英文化
6. **版本管理**: Prompt系统支持版本化管理

---

## 未来展望

基于开发历史，项目可能的发展方向：

1. 继续扩展prompt版本，支持更多实验条件
2. 增强NLP模块功能
3. 优化数据处理性能
4. 添加更多分析工具
5. 完善文档和测试

---

*本文档基于Git提交历史自动生成，最后更新于 2026-01-05*
