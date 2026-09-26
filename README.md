# jev-req-gate

**用 Jev（TypeSafe System One）给 LLM 生成的需求做质量门禁。**

> *[English](README.en.md) · [中文](README.md)*
>
> **🚀 免 key 试玩（二选一）**：本地直接打开 [`playground/index.html`](playground/index.html)（浏览器即可，无需发布）；或发布到 GitHub Pages 后访问 `https://thomaszta.github.io/jev-req-gate/playground/`。

<p align="center">
  <img src="https://img.shields.io/pypi/v/jev-req-gate" alt="PyPI version">
  <img src="https://img.shields.io/pypi/pyversions/jev-req-gate" alt="Python versions">
  <img src="https://img.shields.io/badge/benchmark-real%20measurement-blue" alt="benchmark">
</p>

AI 时代最大的问题不是"需求没人写"，而是"需求太多、太像真的、太难逐条把关"。
`jev-req-gate` 把质量判断从人的主观经验变成**可编程、可批量、带置信度**的结构化信号：
它不重写需求、不解释原因，只回答"这条需求质量处于什么状态"，并按阈值路由 **放行 / 转人工 / 打回**。

**Jev 是什么？** [Jev](https://docs.typesafe.ai/introduction/quickstart) 是 TypeSafe AI 的 System One 模型：不生成文本，只对输入做**并行原子判断**，返回带校准概率的结构化信号（Choice / Score / Noul）——所以它适合当"判断器"，不适合当"生成器"。**贵不贵？** 官方价 `$0.042/MTok` 输入、输出免费；本仓库实测 34 次判定总成本约 `$0.0022`（详见 [docs/benchmark.md](docs/benchmark.md)）。

---

## 特性

- **MECE 5 面 × 22 个原子问题**：表述 / 内容 / 现实 / 关系 / 治理，覆盖 AI 生成需求最会翻车的地方（通用幻觉、意图失真、不可行、冗余、前后矛盾、依赖隐形知识）。
- **5 面综合路由**，阈值已按真实 Jev 输出校准（见 [docs/methodology.md](docs/methodology.md)）。
- **state 打包**：一条需求 + 项目上下文 + 既有需求 + 整篇文档，一次调用并行评估全部问题。
- **多种消费形态**：CLI、Python API、Agent Skill。
- **可配置**：自定义问题库（`--profile-file`）和阈值（`--thresholds-file`）。
- **开箱即验**：`--demo` 无需 API key 即可演示完整路由；浏览器里还有**免 key 在线 playground**（`playground/index.html`，复刻真实路由逻辑）；pytest 测试套件覆盖核心逻辑。
- **真实对比基准**：`benchmarks/` 提供可复现的 Jev-vs-LLM 对比（同一测试集、同一判定口径），Jev 与 **DeepSeek V4 Flash** 均为本仓库真实 API 采集（见 [docs/benchmark.md](docs/benchmark.md)）。
- **CI 与本地门禁**：可复用 **GitHub Action**（PR 门禁 + CSV 报告，见 [.github/workflows/req-gate.yml](.github/workflows/req-gate.yml)）与 **pre-commit hook**（[.pre-commit-hooks.yaml](.pre-commit-hooks.yaml)），发现打回即失败。
- **判断一次、阈值随便调**：请求缓存（SQLite）让同一需求只调一次 Jev；改阈值、重新生成报告不再花钱。
- **标注校准闭环（HITL）**：`--export` 导出判定待人工标 `pass/block`，`--eval` 扫描推荐阈值并直接输出可用的 `--thresholds-file`（见下节）。
- **整篇文档直接用**：`--from-document x.md` 自动拆解需求文档（识别 `1.` / `R01` / `- [ ]` / 表格行）、编号并跑门禁，报告带需求编号可对应回原文；拆解结果可人工确认后再跑（`--prepared`）。

## 安装

```bash
pip install -e .          # 安装命令 jev-req-gate / 模块 jev_req_gate
pip install typesafe-sdk  # 运行时依赖（pip install -e . 会自动装）
export TYPESAFE_API_KEY=你的key
```

不安装也能跑：顶层 `python reqgate.py`（免安装入口）。

## 30 秒看到它怎么干活

```bash
# ① 无需安装、无需 key，先看路由逻辑（3 秒）
python3 reqgate.py --demo unrealistic        # → RED 打回（空泛需求）

# ② 想真实把关：装运行时依赖 + 注册 TypeSafe 拿 key（TypeSafe dashboard）
pip install typesafe-sdk
export TYPESAFE_API_KEY=你的key
python3 reqgate.py --text "提升用户体验"      # → RED（空泛，被打回）
```

选一种适合你团队的嵌入方式——**即时把关 · GitHub Action · pre-commit · Agent Skill · 批量把关**，见 [INTEGRATION.md](INTEGRATION.md)。复制需求文件模板即可开填：[example.json](examples/requirements.example.json) / [example.md](examples/requirements.example.md)。

## 快速开始

```bash
# ① 无 key 演示路由逻辑（三种入口等价：安装后 `jev-req-gate`，或 `python -m jev_req_gate`，或免安装 `python reqgate.py`）
python -m jev_req_gate --demo unrealistic
```

```text
[RED 打回] (demo)
    质量均分: 4.17   风险: low
    - feasible=0.22 < 0.3

共 1 条: 放行=0 转人工=0 打回=1
```

```bash
# ② 真实把关：需求集 + 项目上下文 + 整篇文档（查跨条目矛盾）
TYPESAFE_API_KEY=你的key jev-req-gate \
  --file examples/document_demo.json \
  --document-file examples/document_demo.json \
  --project-context "电商库存管理平台：技术栈 Python/PostgreSQL，含商品/订单/库存三域；库存扣减需考虑订单引用约束与并发，结算依赖内部支付网关" \
  --out report.csv

# ③ 整篇需求文档直接把关（无需手工拆解）：拆解→编号→门禁→报告
TYPESAFE_API_KEY=你的key jev-req-gate \
  --from-document requirements.md --out report.csv
#   → 自动识别 1. / R01 / - [ ] / 表格行，产出 requirements.md.prepared.json
#   先拆解不把关：加 --no-gate；确认条目后：--prepared requirements.md.prepared.json
```

### 真实 Jev 输出示例

用 [examples/document_demo.json](examples/document_demo.json)（含一对矛盾、一条空泛、一条不可行）跑真实 Jev：

| 需求 | Jev 抓到的信号 | 判定 |
|---|---|---|
| 阻止删除被引用商品 | `contradicts_siblings=0.75`（与下条矛盾）| RED |
| 允许强制删除被引用商品 | `contradicts=0.86`、`correct=0.17` | RED |
| 提升用户体验（空泛）| `correct=0.21`、`feasible=0.23` | RED |
| 支付网关结算（合理）| 仅质量分偏低 | YELLOW（未误杀）|
| 50ms 实时拉取第三方（不可行）| `feasible=0.06`、`correct=0.08` | RED |

> 核心结论：Jev 对**现实层（正确/可行/必要/自足）与跨条目矛盾**判断可靠，用于打回硬信号；质量分/术语/风险输出偏保守或偏高，已降权为提示。详细校准见 [docs/methodology.md §5.5](docs/methodology.md)。

## CLI 选项

| 选项 | 说明 |
|---|---|
| `--text "需求"` | 单条需求文本 |
| `--file path` | 批量待审需求（.json/.csv/.txt，已条目化）|
| `--from-document x.md` | **整篇需求文档（.md/.txt）**：自动拆解+编号+门禁一站式（可加 `--no-gate` 只拆解）|
| `--prepared x.prepared.json` | 用人工确认过的拆解结果跑门禁（保留需求编号）|
| `--no-gate` | 与 `--from-document` 连用：只拆解并写出 prepared.json |
| `--project-context` | 项目背景/约束/技术栈（现实层参照）|
| `--existing-file` | 既有需求，用于非冗余判断 |
| `--document-file` | 整篇文档，用于跨条目矛盾判断 |
| `--archived` | 上一版归档需求（可选）|
| `--profile-file` | 自定义问题库 JSON |
| `--thresholds-file` | 自定义阈值 JSON |
| `--demo good\|ambiguous\|unrealistic` | 无 key 演示 |
| `--out report.csv\|.json` | 导出报告 |
| `--db path` | 请求缓存 SQLite 路径（默认 `~/.jev_req_gate/cache.db`，可用 `JEV_REQ_GATE_DB`）|
| `--cache-stats` / `--cache-clear` | 查看缓存统计 / 清空缓存 |
| `--export path.jsonl` | 把缓存中的判定导出为 JSONL（人工标注用）|
| `--eval path.jsonl` | 读回标注，扫描并推荐阈值（`--max-error` 默认 0.1）|

退出码：`0` 全部放行 / `1` 存在打回或 export 无数据 / `2` 用法或依赖错误。

## 标注校准闭环（HITL）

唯一必须人工介入的环节是**中间带裁决**（yellow 转人工）。本工具把它做成可操作闭环，其余全部自动化：

```bash
# ① 正常把关（判定自动进缓存）
jev-req-gate --file requirements.json --project-context "..." --db cache.db

# ② 导出判定，人工把每行 label 改成 pass 或 block
jev-req-gate --export labeled.jsonl --db cache.db
#   {"text":"提升用户体验","verdict":"red","label":null,...}   → 改为 "block"
#   {"text":"支付网关重试","verdict":"yellow","label":null,...} → 改为 "pass"

# ③ 读回标注，扫描 k（白名单阈值倍率），推荐满足漏检上限的最小误伤配置
jev-req-gate --eval labeled.jsonl --max-error 0.1

# ④ 把推荐的 --thresholds-file 写回，即完成一次校准
```

- `eval` 扫描 k ∈ [0.6, 1.4]：k>1 更严（更容易打回）、k<1 更松；报告每个 k 的**漏检率 / 拦截召回 / 误伤率**，推荐漏检可控下误伤最小的 k，并输出可直接保存的阈值 JSON。
- 若存在"Jev 判 green（自动放行）但人工标 block"的条目，`eval` 会明确提示**阈值无法修复**——需要检查该条信号或增补原子问题（这正是门禁该暴露的真相，而不是悄悄调参掩盖）。
- 缓存只存成功判定；失败的调用不缓存，下次运行自动重试。

## 作为 Python 库

```python
from jev_req_gate import run_gate, decide, demo_answers
from jev_req_gate.profiles import DEFAULT_THRESHOLDS

# 纯路由判定（无需 API）
verdict, reasons, detail = decide(demo_answers("unrealistic"), DEFAULT_THRESHOLDS)
assert verdict == "red"

# 走真实 API（需 TYPESAFE_API_KEY）
result = run_gate("提升用户体验", {"project_context": "..."}, DEFAULT_THRESHOLDS)
```

## 作为 Agent Skill

项目自带 `skill/SKILL.md`，可让编码 Agent（Claude Code / Doubao 等）通过技能调用本工具做需求质检，也可让 Agent 按其中约定直接组织 TypeSafe API 请求。

## 项目结构

```
src/jev_req_gate/        # 核心包：profiles(问题库/阈值) · core(路由/state) · cli · report · store(请求缓存) · labels(标注校准) · doc_parser(文档拆解)
tests/                   # pytest：路由判定/问题库完整性/解析/导出/缓存/校准/文档拆解
examples/                # 含矛盾/空泛/不可行的真实测试集
benchmarks/              # 对比基准：测试集 + benchmark.py（Jev/LLM 双后端）
playground/              # 免 key 交互 playground（单文件 HTML，可发布到 Pages）
hooks/                   # pre-commit hook
.github/                 # CI / 发布 workflow + 可复用 jev-req-gate Action
skill/SKILL.md           # Agent Skill 形态
docs/methodology.md      # 完整方法论与真实校准记录
docs/benchmark.md        # Jev vs LLM 对比报告（本仓库实测 + 如实边界）
```

## 集成

**GitHub Action** —— 在 PR 上自动把关需求文件，上传 CSV 报告，有打回即失败：

```yaml
- uses: thomaszta/jev-req-gate/.github/actions/jev-req-gate@v0.2.0
  with:
    requirements-file: requirements/ai-generated.json
    project-context: "电商库存平台：技术栈 Python/PostgreSQL"
    typesafe-api-key: ${{ secrets.TYPESAFE_API_KEY }}
```

示例见 [.github/workflows/req-gate.yml](.github/workflows/req-gate.yml)。**pre-commit** —— 改动文件里出现打回项即阻止提交，注册方式见 [.pre-commit-hooks.yaml](.pre-commit-hooks.yaml) 与 [.pre-commit-config.yaml](.pre-commit-config.yaml)。

## 对比基准（Jev vs 通用 LLM）

同一测试集（17 条，按 MECE 5 面组织）、同一判定口径（HITL 三态），Jev 与 **DeepSeek V4 Flash** 均为**本仓库真实 API 采集**（各 17 条 × 2 次）。实测：

| 指标 | Jev | DeepSeek V4 Flash |
|---|---|---|
| **拦截率（坏需求非放行）** | **0.92**（11/12，漏 r15 重复）| 0.92（漏同 1 条重复）|
| **误打回（好需求被打回）** | **0.0**（0/5）| **0.6**（3/5）|
| 自动放行（好需求）| **0.4**（r01/r05 绿）| 0.4 |
| 转人工率 | 0.35 | 0.0 |
| 判定一致性（2 次跑）| **1.0** | 0.94 |
| 延迟 p50 / p95 | 0.67s / 0.84s | 1.90s / 9.80s |
| 成本（34 次调用）| **$0.0022** | $0.0197 |

见 [docs/benchmark.md](docs/benchmark.md)。**结论**：Jev 适合做门禁的"分层路由层"（v0.6.0）——好需求可自动放行（红黄绿齐）、零误打回、判定稳定、成本/延迟大幅低、输出原生可路由；代价是仍有 35% 转人工、且**冗余类坏需求（r15）与 DeepSeek 同样漏检**（non_redundant 是共同盲点，需流程层编号级去重兜底）。DeepSeek 更"果断"但误杀 60% 好需求。正确模式 = **Jev 分层路由（red 打回 / green 放行 / yellow 转人工）+ 人工复核黄单 + 流程层去重**。

## 边界与免责

- **Jev 只接受文本 state**；暂不支持图片/音视频。
- **它是判断，不是建议**：不重写需求、不解释原因；歧义/矛盾原因由人工复核。
- **校准 ≠ 单条正确**：Jev 概率是群体校准的，中间带（0.25~0.75）必须转人工，不要用代码硬消。
- **本工具是质量门禁，不是需求生成的替代**：它把关 AI 生成的需求，不负责把模糊需求改清楚。

## 路线图

- [ ] 支持从需求管理系统（Jira/飞书/Notion）直接拉取待审需求
- [ ] 输出"缺哪类信息"的高亮清单（对接 `missing_info`）
- [ ] 多模型后端（除 jev-latest 外的 System One 模型）
- [ ] 未判断语义：调用失败标「未判断」→ 转人工并自动重试（对齐 jevclip 的失败处理）

## License

[MIT](LICENSE)
