---
name: jev-req-gate
description: 用 Jev (TypeSafe System One) 给 LLM 生成的需求做质量门禁。当用户要对一批需求/用户故事/验收标准做快速质量把关（判断是否无歧义、可验证、完整、自足、正确、可行、必要、是否前后矛盾、是否夹带 AI 通用幻觉），或要把低置信/低评分条目路由给人工时使用。它只做"判断"，不重写需求、不解释原因。
---

# jev-req-gate — Jev 需求质量门禁

让 Jev（TypeSafe System One 模型）对 LLM 生成的需求做**可编程、带置信度**的质量判断，输出放行 / 转人工 / 打回。

## 技能包内容（自包含，不依赖全局安装）

本技能目录自带完整运行时：`src/`（包本体）、`reqgate.py`（免安装入口）、`pyproject.toml`。
未全局安装时，用技能目录内的入口运行（把 `<skill_dir>` 换成技能目录）：

```bash
python3 <skill_dir>/reqgate.py --demo unrealistic
```

已全局安装（`pip install -e .` 或 PyPI 安装）时，三种入口等价：`jev-req-gate` / `python -m jev_req_gate` / `python3 reqgate.py`。

## 新手 3 步（照做即可，5 分钟内看到结果）

1. **看路由逻辑（无需 key）**：`python3 reqgate.py --demo unrealistic` → 输出 `[RED 打回]`，说明装好了。
2. **把关你的第一份文档**：
   ```bash
   export TYPESAFE_API_KEY=你的key
   python3 reqgate.py --from-document 你的需求文档.md --out report.csv
   ```
   它会自动拆解（识别 `1.` / `R01` / `- [ ]` / 表格 / 用户故事行）、编号、逐条判断，报告带需求编号。
3. **读报告**：CSV 打开后看三列——`verdict`（red/yellow/green）、`reasons`（为什么，已人话化）、`id`（对应文档哪条）。red = 建议打回、yellow = 转人工复核、green = 放行。

## 判定口径（怎么读结果，先读这个避免误判）

- **red 打回 = Jev 最可靠的 5 个正向信号任一破线**（self_contained / correct / feasible / necessary < 0.3）**或 contradicts_siblings > 0.7**，或质量均分 < 1.0。
- **green 放行（v0.6.0）= 无红 + 关键信号全健康**：self_contained ≥ 0.5、correct / feasible / necessary / acceptance_quantifiable / non_redundant ≥ 0.6、contradicts_siblings ≤ 0.4、implementation_free ≤ 0.6、质量均分 ≥ 2.0。
- **yellow 转人工 = 无红但有强警告**（上面任一条未达标）。术语低 / risk=high / 个别置信度低是 Jev 中文输出的常态噪声，不再拉黄，只作提示。
- **正常文档应红黄绿都有**：明显坏的红、明显好的绿、灰色转人工。若你的文档全黄（无红无绿），说明它"无致命硬伤但处处需确认"——用 `examples/thresholds.strict.json` 收紧，或检查文档是否整体平庸。
- **implementation_free（需求混入实现方案）不参与打回**（v0.5.0：实测它对"写具体的指标/约束/兼容性"的好需求系统性误伤），只作提示/强警告。团队若坚持要它打回：`--thresholds-file` 里加 `"block_neg_keys": ["contradicts_siblings", "implementation_free"]`。
- **已知盲点（如实）**：Jev 对"与他人重复"（non_redundant）判断弱，重复类坏需求可能被放行（benchmark r15 与 DeepSeek 双双漏检）——冗余去重请在需求管理系统层做编号级核对。
- **它只判断、不解释**：reasons 是信号值不是原因；歧义/矛盾的原因由人工复核。

## 什么时候用它

- 一批需求是 AI 扩写/生成的，需要批量把关再进评审或开发。
- 判断一条需求是否符合项目上下文、是否必要、是否前后矛盾、是否依赖文档外的隐形知识。
- 需要把低质量条目自动路由给人，而不是整篇人工通读。

## 核心概念

- **MECE 5 面**：表述 / 内容 / 现实 / 关系 / 治理，共 22 个原子问题。
- **打回只看 Jev 最可靠的信号**：5 个正向白名单（`self_contained`、`correct`、`feasible`、`necessary`）+ 负向白名单 `contradicts_siblings`（见上"判定口径"）。
- 质量分、`terminology_defined`、`risk`、`implementation_free` 只作提示（Jev 对它们输出偏保守/偏高/易误伤，已校准，见 docs/methodology.md §5.5）。

## 用法

### 方式一：CLI（推荐，项目已装好）

```bash
# 无 API key 演示（了解路由逻辑）
python -m jev_req_gate --demo unrealistic

# 真实把关：需求 + 项目上下文 + 整篇文档（查矛盾）
TYPESAFE_API_KEY=你的key python -m jev_req_gate \
  --file examples/document_demo.json \
  --document-file examples/document_demo.json \
  --project-context "电商库存平台：技术栈 Python/PostgreSQL；库存扣减需考虑订单引用约束；结算依赖内部支付网关" \
  --out report.csv
```

### 方式二：Python API

```python
from jev_req_gate import run_gate, decide, demo_answers
from jev_req_gate.profiles import DEFAULT_THRESHOLDS

verdict, reasons, detail = decide(demo_answers("unrealistic"), DEFAULT_THRESHOLDS)
# -> "red"
```

### 方式三：直接调 TypeSafe API

若未安装本包，可让编码 agent 直接按 `https://docs.typesafe.ai/introduction/quickstart` 组织请求：
把 `{requirement, project_context, document, existing_requirements}` 打包进 `state`，把 22 个问题（见 `src/jev_req_gate/profiles.py`）打包进 `questions`，一次 `POST /v1/systemone` 返回全部概率，再按阈值路由。

## 关键约定（agent 必须遵守）

1. **必须带参照**：跨条目矛盾、上下文契合、隐性依赖都依赖比较。只给单条文本会让 `terminology_defined`/`contradicts_siblings` 失真——请把整篇文档和项目上下文一并放进 state。
2. **问题要原子**：每个问题只问一件事；复杂判断拆成多个 Noul/Score 后在代码里组合。
3. **中间带转人工**：落在 0.25~0.75 的概率不要用代码硬消，路由给人。
4. **不要求 Jev 解释**：它只返回判断，不返回原因；歧义/矛盾的原因由人工复核。

## 项目结构

```
src/jev_req_gate/
  profiles.py   # 22 个原子问题 + 校准后阈值 + profile 校验/加载
  core.py       # decide 路由、state 打包、SDK 归一化、demo
  cli.py        # CLI 入口
  report.py     # 控制台/CSV/JSON 输出
tests/          # pytest：路由、profile、解析、导出
examples/       # 含矛盾/空泛/不可行的真实测试集
docs/methodology.md  # 完整方法论与校准记录
```
