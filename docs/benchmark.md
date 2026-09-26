# 对比基准：用 Jev 做需求质量门禁 vs 用通用 LLM

> **数据性质（如实声明）**：本报告所有数字均为本仓库 `benchmarks/benchmark.py` 对同一份
> `benchmarks/test_set.json` 的 **真实 API 调用采集**：
> **Jev 列**：`TYPESAFE_API_KEY`，2026-09 实测；
> **LLM 列**：**DeepSeek V4 Flash**（`deepseek-flash` = DeepSeek-V4.1-Flash），用户提供的
> `OPENAI_API_KEY` 实测。
> 两列同一测试集、同一判定口径、同一采集脚本。公开来源数据仅作补充。

---

## 一、方法与口径

### 测试集 `benchmarks/test_set.json`（v2，与方法论 MECE 5 面对齐）

17 条：**5 条应放行（pass）+ 12 条应打回（block）**。坏需求按方法论 **MECE 5 面 × 22 原子问题**组织，每条标注 `facet`/`signal`/`defect`，覆盖工具要解决的全部痛点面（含「自足性 / 依赖文档外隐形知识」「意图失真 / 把通用知识当真」「冗余」「前后矛盾」等）：

| 判断面     | 坏需求                   | 对应信号 / 缺陷类别                                                               |
| ------- | --------------------- | ------------------------------------------------------------------------- |
| **表述层** | r06 / r07             | clarity 含混不可测 /atomicity 混杂多条                                             |
| **内容层** | r08 / r09 / r10       | self\_contained 不自足（依赖隐形知识）/implementation\_free 方案当需求 /missing\_info 缺信息 |
| **现实层** | r11 / r12 / r13 / r17 | fidelity 意图失真 /feasible 不可行 /necessary 不必要冗余 /correct 危险操作                |
| **关系层** | r14 / r15             | contradicts\_siblings 与他人矛盾 /non\_redundant 与他人重复                         |
| **治理层** | r16                   | conforms\_template 模板不合规（缺验收）                                             |

### 判定口径（HITL 三态，与 [docs/methodology.md](docs/methodology.md) 一致）

* Jev：`green`= 自动放行 / `yellow`= 转人工 / `red`= 自动打回。
* LLM 二态映射到同一语义：`pass`→放行、`block`→打回（无转人工档）。
* **拦截率**= 坏需求被拦下（打回或转人工，均非放行）；**自动打回**= 坏需求被判 red/block；**误打回**= 好需求被判 red/block；**自动放行**= 好需求被判 green/pass。
* 每条跑 **2 次** 测一致性。
* 成本：Jev `$0.042/MTok` 输入（输出免费）；DeepSeek peak 价 `$0.30` 输入 / `$1.20` 输出。

## 二、对称真实实测（同一测试集，各 17 条 × 2 次）

| 指标                   | **Jev**（System One） | **DeepSeek V4 Flash**    | 解读                 |
| -------------------- | ------------------- | ------------------------ | ------------------ |
| **拦截率（坏需求非放行）**      | **0.9167**（11/12）    | 0.9167（11/12，漏 r15 重复）   | **同一盲点：都漏 r15 冗余** |
| 自动打回（坏需求 red/block）  | 0.6667（8/12）        | 0.9167（11/12）            | DeepSeek 更 "果断" 打回 |
| **误打回（好需求被打回）**      | **0.0**（0/5）        | **0.6**（3/5：r02/r04/r05） | Jev 零误杀，LLM 误杀大半   |
| **自动放行（好需求 green/pass）** | **0.4**（2/5：r01/r05） | 0.4（2/5：r01/r03）         | 持平：都能自动放行好需求     |
| 转人工率                 | 0.3529（6/17）        | 0.0                      | Jev 把不确定交给人        |
| 判定一致性（2 次跑）          | **1.0**             | 0.9412                   | Jev 更稳             |
| 延迟 p50 /p95          | 0.67s / 0.84s       | 1.90s / 9.80s            | Jev 快约 2.8×/11.7×   |
| 34 次调用成本（17 条 ×2）     | **\$0.0022**        | \$0.0197                 | Jev 便宜约 9×         |

> **口径说明（v0.6.0）**：Jev 列已按 v0.6.0 重新实测。v0.6.0 重设计了"绿"档——之前
> green 要求"无任何黄信号"，但 Jev 对中文需求输出的术语低/个别置信度低/risk=high 是常态噪声，
> 导致好需求全黄、无区分度（用户实测反馈"全黄=工具没用"）。现在 **green = 关键信号全健康**
> （self_contained≥0.5、correct/feasible/necessary/acceptance_quantifiable/non_redundant≥0.6、
> contradicts≤0.4、implementation_free≤0.6、质量均分≥2.0），黄 = 有强警告，红不变。
> 数据为同一批真实 Jev answers 离线重算（零新增 API 调用，answers 持久化于
> `benchmarks/report_jev.json`），见 [docs/methodology.md §5.5](docs/methodology.md)。

### 逐条判定（真实）

* **Jev**：好需求 **r01/r05 → green**（自动放行，质量信号健康）、r02/r03/r04 → yellow（各有强警告：自足性/风险/置信度）；
  坏需求 r06/10/11/12/13/14/16/17 → `red`（自动打回），r07/08/09 → `yellow`（转人工），
  **r15（与他人重复）→ green（漏放行）**。
* **DeepSeek**：好需求 r01/r03 → pass，**r02/r04/r05 → BLOCK（误打回 3 条）**；坏需求全 block，
  **但 r15（与他人重复）→ pass（漏放行）**。

> 门禁最怕两件事：**坏需求漏进开发**、**好需求被打回**。本实测：
> - **r15（与他人重复）Jev 与 DeepSeek 双双漏放行**——这条坏需求的所有信号都"健康"
>   （Jev 判 self_contained 0.56 / correct 0.92 / necessary 0.88 / non_redundant 0.69），
>   冗余是两者共同的盲点。这是**如实记录的反面数据**：Jev 的"零漏检"神话在 v0.6.0 绿线放开后
>   不成立；想堵冗余，需在需求管理系统层面做编号级去重（见 README P2 路线）。
> - **误打回 Jev 0 vs DeepSeek 0.6**：Jev 依然零误杀（核心优势不变）。
> - **自动放行 0.4 vs 0.4 持平**：v0.6.0 让 Jev 也能把明显好的需求自动放行（红黄绿都有）。

## 三、诚实的解读与边界

1. **Jev = 保守的分层路由器（v0.6.0）**：好需求能绿（0.4），坏需求主要红（0.67）+ 部分黄，
   灰色（强警告）转人工；**误打回 0**。代价是仍有 35% 条目转人工，且**冗余类坏需求（r15）
   会被放行**——因为 Jev 对 non_redundant 信号判断弱。
2. **DeepSeek = 果断的二分判断器**：自动分流比例高，但误杀 60% 好需求、漏 r15。
3. **适用取舍**：质量门禁（优先级 = 不误伤 + 有人工消化黄单）→ Jev；追求"尽量自动"且能接受
   误杀 + 调提示词 → LLM。**两者都有同一个盲点（冗余）**，冗余去重应在流程层解决。
4. **LLM 用"朴素但合理"的单段提示词**（benchmark.py 内置，未做 prompt 工程）。对 LLM 投入同等
   结构化 prompt 工程可降误杀，但那是深度定制，非开箱即用。
5. **小测试集（17 条）**：结论限本可复现设定，可扩充后重跑。

## 四、公开来源（补充口径，非本仓库实测）

| 来源                                                                                         | 场景           | Jev               | 通用 LLM                     |
| ------------------------------------------------------------------------------------------ | ------------ | ----------------- | -------------------------- |
| [OpenRouter](https://openrouter.ai/blog/tutorials/jev-vs-llm-when-to-use-each/)            | 意图分类准确率      | 98.3%             | 98.3%（GPT Luna）持平          |
| [OpenRouter](https://openrouter.ai/blog/tutorials/jev-vs-llm-when-to-use-each/)            | p50 延迟       | 0.194s            | 1.106s（约快 5.7×）            |
| [OpenRouter LLM-as-judge](https://openrouter.ai/blog/tutorials/jev-vs-llm-as-a-judge/)     | 闭式规则判定       | 准确率持平，概率校准更好      | 成本 1/5、延迟 1/10             |
| [LangChain Agent Evals](https://www.langchain.com/blog/jev-agent-evals-langsmith)          | 二值 pass/fail | 500/500 匹配 oracle | Terra 99.8% / Claude 80.0% |
| [腾讯云 ADP](https://adp.tencent.com/zh/blog/jev-vs-general-llm-automated-decision-selection) | 500 条工单成本    | \$0.0103          | \~\$2.45（约便宜 238×）         |

### 必须如实说的反面数据

Jev 在**开放式、分级 / 整体阅读**任务上落后于 frontier LLM：

* [arXiv 2609.24574](https://arxiv.org/pdf/2609.24574.pdf)：15 个文本标注任务 Jev 中位准确率 0.610，落后 per-task 最佳 LLM 约 11.6 macro-F1。
* [arXiv 2609.29769](https://arxiv.org/pdf/2609.29769)：Jev 二值判据常领先、分级判据落后；成本低 29–325×。

## 五、结论：Jev 在需求门禁的价值

本实测支撑：**Jev 适合做门禁的"分层路由层"**——零误杀、判定稳定、成本 / 延迟大幅低、输出原生可路由；
v0.6.0 后好需求可自动放行（红黄绿齐），代价是转人工率仍有 35% 且**冗余类坏需求与 LLM 同样漏检**
（冗余是共同盲点，需流程层去重兜底）。**正确模式 = Jev 分层路由（red 打回 /green 放行 /yellow 转人工）
+ 人工复核黄单 + 流程层做编号级去重。**

## 六、可复现

```
# 本仓库实测：Jev
TYPESAFE_API_KEY=xx python benchmarks/benchmark.py --backend jev --runs 2

# 本仓库实测：DeepSeek V4 Flash（peak 价）
OPENAI_API_KEY=xx OPENAI_BASE_URL=https://api.deepseek.com/v1 \
  python benchmarks/benchmark.py --backend llm --model deepseek-flash \
  --runs 2 --input-price 0.3 --output-price 1.2 --out benchmarks/report_llm.json
```

> 完整原子问题库 / 阈值：`src/jev_req_gate/profiles.py`；LLM 提示词与判定：`benchmarks/benchmark.py`；
> 原始明细（含逐条 answers）：`benchmarks/report_jev.json` / `benchmarks/report_llm.json`。
