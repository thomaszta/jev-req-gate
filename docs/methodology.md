# Jev 驱动的 LLM 生成需求质量把关 —— 落地方法论（v2・MECE 5 面版）

> 面向 AI 时代：各种 LLM 批量生成需求文档 / 用户故事 / 验收标准之后，用 Jev（TypeSafe AI 的 System One 模型）做
>
> **快速、可编程、带置信度的质量门禁**
>
> 。
> 配套工具：`jev-req-gate` 命令（本仓库，可开箱即用；免安装入口 `python reqgate.py`）。
> 本版依据 MECE（相互独立、完全穷尽）原则，将需求质量判断重构为 5 个正交判断面。



***

## 一、核心思路：判断优先，生成让位

Jev 不是 LLM 的替代，而是 LLM 的**质检器**。



| 层               | 用什么     | 干什么                     |
| --------------- | ------- | ----------------------- |
| 生成层（快、会幻觉）      | 任意 LLM  | 批量产出需求文本                |
| 判断层（快、带置信度、不解释） | **Jev** | 对每条需求做原子质量判断，返回结构化信号    |
| 决策层             | 你的代码    | 按阈值路由：**放行 / 转人工 / 打回** |

**原则**：Jev 输出的是「判断」而非「建议」。它不重写需求、不解释原因。你要做的是**把需求 + 上下文打包成 state，把质量维度拆成原子问题，把概率 / 分数 / 标签变成路由信号**。



***

## 二、MECE 重构：5 个正交判断面（为什么是这 5 个）

对 "一条需求 / 一篇文档" 的质量判断，穷尽地切成 **5 个互不重叠、合起来完整**的面：



| 判断面                | 问什么     | 含维度                      | 边界         |
| ------------------ | ------- | ------------------------ | ---------- |
| **表述层 Expression** | 它怎么说    | 无歧义、可读、原子                | 措辞层面       |
| **内容层 Content**    | 它说了什么   | 完整、自足、术语、验收可量化、实现无关      | 信息量层面      |
| **现实层 Reality**    | 它是否成立   | 正确、可行、必要、可追踪、意图保真        | 真假 / 可行性层面 |
| **关系层 Relation**   | 它和别人的关系 | 一致、非冗余、依赖显式化             | 与他物对齐层面    |
| **治理层 Governance** | 它守不守规矩  | 模板合规、类型 / 优先级 / 风险标签、缺信息 | 流程规范层面     |

> **AI 是横切轴，不是第 6 面**
>
> ：AI 生成病（通用味、意图失真、过度细节、冗余、漏字段）会落到 5 个面各自的格子里，因此用 "5 面 × AI 易错点" 定位，比把 "AI 病" 单列一组更准确、更互斥。
> 穷尽依据：ISO/IEC/IEEE 29148 需求质量属性 + 需求工程经典清单 + AI 场景扩展。



***

## 三、问题库：22 个原子问题（方法论核心）

设计原则（来自 TypeSafe 官方文档）：



1. **每个问题原子、单维度**。「是否清晰且自足」要拆成两个。

2. **Noul 只问 yes/no 命题**，措辞保证「高值 = 正向含义」，不要反向提问。

3. **Score 用等级描述（criteria 数组）定义刻度**，模型落在你写的刻度上。

4. **Choice 的 criteria 是 键→含义 映射**，键名是可写回系统的标签。

5. Noul 的 `direction`：`positive`（值越高越健康）/ `negative`（值越高越有问题）。

### 表述层（3・Score）



| key           | instructions   | direction / 刻度             |
| ------------- | -------------- | -------------------------- |
| `clarity`     | 该需求表述的无歧义程度    | 1 = 含混 / 自相矛盾 … 5 = 清晰单义   |
| `readability` | 非技术受众能读懂该需求的程度 | 1 = 满口行话 / 抽象 … 5 = 普通读者可懂 |
| `atomicity`   | 该需求聚焦单一职责的程度   | 1 = 混杂多条 … 5 = 完全单一        |

### 内容层（6）



| key                       | 原语     | direction | instructions                                 |
| ------------------------- | ------ | --------- | -------------------------------------------- |
| `completeness`            | Score  | —         | 该需求信息完整的程度（1 = 大量缺失 … 5 = 完整自足含边界异常）         |
| `self_contained`          | Noul   | positive  | 该需求在文档内自足，无需文档外隐形知识即可理解和验证                   |
| `terminology_defined`     | Noul   | positive  | 该需求的关键术语在本文档内有定义                             |
| `acceptance_quantifiable` | Noul   | positive  | 该需求的验收标准可量化                                  |
| `implementation_free`     | Noul   | negative  | 该需求把实现方案 / 细节当成了需求（需求与方案混淆）                  |
| `missing_info`            | Choice | —         | 缺哪类信息：前置条件 / 依赖接口 / 边界异常 / 术语定义 / 验收判据 / 无缺失 |

### 现实层（5・Noul 全 positive）★ 本轮最重要新增



| key         | direction | instructions                     |
| ----------- | --------- | -------------------------------- |
| `correct`   | positive  | 该需求与业务目标 / 真实意图一致，是正确的需求         |
| `feasible`  | positive  | 该需求在当前技术 / 资源约束下可实现              |
| `necessary` | positive  | 该需求是本次交付实际需要的内容（非冗余 / 装饰）        |
| `traceable` | positive  | 该需求可追溯到明确的来源（用户诉求 / 业务目标 / 上游需求） |
| `fidelity`  | positive  | 该需求忠实于原始输入意图，未被 AI 扩写发散或跑题       |

> 这 5 条针对 AI 最大的坑：
>
> **生成 "语法完全正确、项目里根本不成立" 的需求**
>
> 。

### 关系层（4・Noul）



| key                     | direction | instructions                |
| ----------------------- | --------- | --------------------------- |
| `consistent_internal`   | positive  | 该条目内部（标题 / 描述 / 验收标准）自洽、不矛盾 |
| `contradicts_siblings`  | negative  | 该条与文档中其他条目存在矛盾              |
| `non_redundant`         | positive  | 该条不与已有需求重复                  |
| `dependencies_declared` | positive  | 该条的前置条件 / 依赖已被显式声明          |

### 治理层（4）



| key                 | 原语     | direction | instructions                         |
| ------------------- | ------ | --------- | ------------------------------------ |
| `conforms_template` | Noul   | positive  | 该条符合团队需求模板 / 必填字段要求                  |
| `req_type`          | Choice | —         | 类型：feature/nfr/constraint/assumption |
| `priority`          | Choice | —         | 优先级：must/should/could/wont           |
| `risk`              | Choice | —         | 风险：high/mid/low                      |

**合计：Score 4 + Noul 14 + Choice 4 = 22 个原子问题。**



***

## 四、state 打包：从 "一条文本" 升级为 "一个包"

跨条目矛盾、上下文契合、隐性依赖都依赖比较，因此 state 必须带参照：



```
state = {

&#x20; "requirement":          "当前待审条目",

&#x20; "project\_context":      "项目背景/约束/技术栈/业务场景",     ← 现实层(正确/可行)参照

&#x20; "existing\_requirements":\["已有需求1", "已有需求2", ...],       ← 关系层(非冗余)参照

&#x20; "document":             \["整篇文档条目A", "B", "C", ...],      ← 关系层(矛盾)参照

&#x20; "archived":             "上一版归档需求（可选）"

}
```

所有原子问题一次性并行评估（Jev 的 questions 是并行计算，加问题几乎不增耗时）。



***

## 五、阈值与路由（5 面综合，已按真实 Jev 输出校准）

对每条需求，先算**表述 + 内容**的 Score 均分 `Q_score`，再综合各面 Noul。**打回只看 Jev 最可靠的 5 个信号**：



```
红 打回（任一命中）：

&#x20; 现实层致命（白名单 positive<0.3）：self\_contained / correct / feasible / necessary

&#x20; 关系层致命： contradicts\_siblings > 0.7

&#x20; 质量分兜底： Q\_score < 1.0（极差才触发）

黄 转人工（任一命中，未达红）：

&#x20; 质量分提示： Q\_score < 2.2（Jev 质量分打得保守，作参考）

&#x20; 风险提示：   risk == "high"（整篇文档模式下易偏高，仅提示）

&#x20; 其他维度：   任一 positive Noul < 0.5（如 terminology\_defined / conforms\_template）

&#x20;            或 negative Noul > 0.5（如 implementation\_free）

&#x20; 不确定带：   多个 Noul 落在 0.25\~0.75 → 聚合提示，转人工

&#x20; 置信度：     任一 Score 的 confidence < 0.6

绿 放行（v0.6.0：关键信号全健康，无红时）：

&#x20; self\_contained ≥ 0.5，且 correct / feasible / necessary / acceptance\_quantifiable / non\_redundant ≥ 0.6

&#x20; 且 contradicts\_siblings ≤ 0.4 且 implementation\_free ≤ 0.6 且质量均分 ≥ 2.0

&#x20; （术语低 / risk=high / 个别置信度低是 Jev 中文输出常态噪声，只作提示，不拉黄）

```

> **为何这样校准**
>
> ：真实 Jev 对中文需求的输出分布与直觉不同 ——
> 质量分（clarity/completeness 等）普遍打得很保守（合理需求也仅 1.3~2.8），故降为提示而非打回硬信号；
> `terminology_defined`
>
>  在中文 / 单条下天然偏低，不参与打回；
> `risk`
>
>  在传入整篇文档后易整体偏高，仅作提示；
> 而 
>
> `self_contained / correct / feasible / necessary / contradicts_siblings`
>
>  是 Jev 判断最可靠的信号，用于打回。
> v0.6.0 补充：好需求的关键信号分布（sc 0.37–0.64 / corr 0.85–0.90 / feas 0.88–0.91 / nec 0.85–0.89 /
> con 0.14–0.17）与坏需求（sc 大多 ≤0.35）存在清晰分隔，因此绿线建立在"关键信号健康"上；
> 但 **non_redundant 是弱信号**（r15 重复需求被 Jev 判 0.69 健康 → 漏放行），冗余去重需流程层兜底。

### 5.5 真实校准记录（2026-09 实测，中文需求 + 电商项目上下文）

用 `document_demo.json`（5 条，含一对矛盾、一条空泛、一条不可行）跑真实 Jev：



| 需求                | 关键信号                                              | 判定          |
| ----------------- | ------------------------------------------------- | ----------- |
| 阻止删除被引用商品         | contradicts\_siblings=0.75                        | RED（与下条矛盾）  |
| 允许强制删除被引用商品       | contradicts=0.86, correct=0.17                    | RED         |
| 提升用户体验（空泛）        | correct=0.21, feasible=0.23, self\_contained=0.15 | RED         |
| 支付网关结算（合理）        | 质量分 1.48，多数维度中间带                                  | YELLOW（未误杀） |
| 50ms 实时拉取第三方（不可行） | feasible=0.06, correct=0.08                       | RED         |

**结论**：Jev 对现实层（正确 / 可行 / 必要 / 自足）与跨条目矛盾判断可靠，可作打回硬信号；质量分 / 术语 / 风险需按上述降权。

**复现注意**：Jev 是校准概率模型，单值跨调用有抖动（矛盾值约 0.70\~0.87），阈值需留余量。

**补充校准（v0.5.0，真实用户实测驱动）**：用户对一份"写得更规范"的需求文档（含指标、约束、
兼容性、加密方案）实测，8 条红**全部**由 `implementation_free > 0.7` 触发——好版（45 条）反而比
坏版（28 条，0 红）打出更多红。根因：`implementation_free` 对"具体实现细节/指标/约束"存在
**系统性误伤**（它区分不了"指标"与"实现方案"）。据此：
- `implementation_free` 从打回白名单移出（v0.5.0），只作 yellow 提示（`> review_neg_hi 0.5`）；
- 负向打回白名单 `block_neg_keys` 默认仅 `["contradicts_siblings"]`；
- 团队若坚持让"方案混入"打回，可在 `--thresholds-file` 显式加回 `implementation_free`。
该修复已在 benchmark 复测（r09 从 red 降 yellow，拦截率 1.0 不变，见 docs/benchmark.md）。

**绿线校准（v0.6.0，用户实测驱动："正常需求应该有红黄绿都有"）**：真实 Jev answers 分析显示，
好需求的关键信号全部健康（r01–r05：self_contained 0.37–0.64、correct 0.85–0.90、feasible 0.88–0.91、
necessary 0.85–0.89、contradicts 0.14–0.17），却因**常态噪声**（terminology_defined 0.15–0.24、
个别维度置信度低、risk=high）被拉进黄——绿的定义错了：不该是"无任何黄信号"，而应是
**关键信号全健康**。据此：
- 新增绿档：green = 无红 + `self_contained≥0.5` + `correct/feasible/necessary/acceptance_quantifiable/
  non_redundant≥0.6` + `contradicts_siblings≤0.4` + `implementation_free≤0.6` + `质量均分≥2.0`；
- 黄 = 有任一强警告；弱噪声（术语低 / risk=high / 个别置信度低 / conforms_template 低）只作提示，
  不再决定绿黄；
- benchmark 复测（同一批真实 answers 离线重算，零新增 API）：好需求 r01/r05 → green、r02/r03/r04 →
  yellow；坏需求 8 red + 3 yellow + **r15（与 r01 重复）→ green（漏放行）**——r15 所有信号被 Jev 判为
  健康（non_redundant=0.69），冗余是 Jev 与 DeepSeek 的共同盲点（两者都漏 r15），如实记录：
  **绿线放开后"零漏检"不成立，冗余去重需在流程层（编号级）兜底**。数字见 docs/benchmark.md。

### 阈值调参原则（来自官方 Noul 文档）



* **0.5**：yes/no 处理成本对称时用。

* **调高**：假阳性代价高（误打回一条好需求 → 阻塞交付）→ 提高 red 阈值。

* **调低**：漏检代价高（漏掉有歧义 / 不可行的需求 → 上线爆雷）→ 降低 review 阈值、扩大中间带。

* **中间带永远是给人的**：0.4\~0.6 的不确定不要用代码硬消，转人工。



***

## 六、落地步骤（从 0 到生产）



1. **装 SDK**：`pip install typesafe-sdk`（Python ≥ 3.10），从 TypeSafe dashboard 拿 `TYPESAFE_API_KEY`。

2. **定 profile**：用本节的 22 题起步，补 2–3 条团队专属（如「是否依赖未上线接口」→ 现实层 feasible 的细分）。

3. **接入口**：在需求进入评审 / 开发的流水线加 gate 节点，把 LLM 输出的每条需求 + project\_context + 既有需求集喂给 `jev-req-gate`。

4. **设阈值**：先用默认阈值跑一批历史需求看误判率，按第五节原则调。

5. **人工闭环**：黄单进评审看板标注原因；定期用人工结论校准阈值。

6. **写回标签**：把 Choice 结果（type/priority/risk）+ 质量分写回需求管理系统，形成可统计的质量画像。



***

## 七、边界与注意事项



* **Jev 接受文本 state**：字符串、JSON、对象 / 数组均可；暂不支持图片 / 音视频。

* **它不解释**：不要问「为什么有歧义」，把歧义 / 矛盾 / 失真转成 Noul 概率 + 人工复核。

* **校准 ≠ 单条正确**：Jev 概率是群体校准的，不代表每条都对；因此中间带必须留给人。

* **问题质量决定上限**：量表、criteria、问句措辞越清晰判断越准；带 / 不带 criteria 各试一次。

* **现实层权重最高**：AI 需求最危险的不是 "写得差"，而是 "写得好但不成立"—— 现实层 5 个 Noul 优先盯。



***

## 八、官方资源



* Quick start / API 参考：[https://docs.typesafe.ai/introduction/quickstart](https://docs.typesafe.ai/introduction/quickstart)

* 原语文档：[https://docs.typesafe.ai/primitives/noul](https://docs.typesafe.ai/primitives/noul)（及 choice /score）

* System One 概念：[https://docs.typesafe.ai/concepts/system-one](https://docs.typesafe.ai/concepts/system-one)

* Agent Skill：`npx skills add typesafe-ai/skills --skill typesafe-ai`



***

*配套工具 `jev-req-gate` 已实现本版方法论：5 面 22 个原子问题、state 打包、综合路由与报告输出；*`--demo`* 模式无需 API key 即可演示完整路由逻辑。*