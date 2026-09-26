# 架构演进记录（ADR）

> 本文件记录 jev-req-gate 的架构决策与演进。每条 ADR 含：背景（Context）/ 决策（Decision）/ 后果（Consequences）/ 状态（Status）。
> 状态说明：`已实施` = 代码已落地；`已记录，未实施` = 决策成立、记录在案，等排期。

---

## ADR-001：判断分层——从"单层带全文"演进到"两层判断"

**状态**：已记录，未实施

### Context（背景）

需求质量判断的核心矛盾是判断空间大小：

- 拆成单条独立判断（state = 单条）：**判断空间小**、置信度可独立标定、结果可定位（能说"哪一条不过"）、可缓存（改一条只重判一条）——这是"判断结果缓存"能力成立的前提。
- 但**全拆会漏掉关系性不合格**：前后矛盾、范围不一致、角色越权、覆盖不完整——这些都不在任何单条里，单看每条都"说得通"。
- 当前实现（v0.6.x）：**N 次调用，每次 state 都带全文**（`{requirement, project_context, document, existing_requirements}`），22 个问题（含 contradicts_siblings）在同一次调用里判完。
  - 优点：关系已经能判（每次都能看到全文与其他条目）。
  - 代价：全文被喂 N 次（token 成本 = N × (单条 + 全文)）；关系判断重复执行 N 次，各条独立判可能不一致。

### Decision（决策）

采用**两层结构**，而不是"整篇 vs 拆散"二选一：

```
第一层：拆成单条需求（state = 单条 + 结构化上下文）
  → 判"条内可判"的标准：可行、必要、可测、无歧义、完整、表述…
  → 空间小、可缓存、可定位

第二层：把 N 条关键字段 + 原始文档摘要作为一个 state（1 次调用）
  → 只判"关系性"标准：前后矛盾、范围一致、角色一致、依赖声明、覆盖完整
  → 只跑一次，专治跨条问题
```

路由合并规则：**条内红 或 关系红 → 打回**（合并口径与现有一致，只在信号来源上分层）。

### 判断原则

> 拆分是为了缩小单次判断空间，但"关系"必须有一个不拆的层来兜。
> 全拆 → 漏判关系；全不拆 → 空间大、置信度糊。
> 两层结构，才是"缩小空间"的正解。

### Consequences（后果与约束）

- **成本**：从 N × (单条+全文) 降为 N × 单条 + 1 × (摘要 + N 条关键字段)。大批量文档（几十条）时省约一个数量级的 token。
- **一致性**：关系判断从 N 次独立判断收敛为 1 次，天然一致。
- **关键约束（半关系性信号）**：去掉全文后，`self_contained`（自足性）与 `terminology_defined`（术语已定义）失去参照——它们需要知道"文档内定义了哪些术语/假设"。因此**第一层必须挂结构化上下文**（`glossary` + `assumptions` + `constraints`），自足性判断从"读全文猜"变成"对表判"。这与"模板把隐形知识逼成显式字段"的方案衔接，二者配套成立。
- **向后兼容**：未提供 glossary/assumptions 时，第一层退化到现状（带全文兜底）；提供模板字段后才走分层。

### 落地清单（未实施，排期时按此推进）

1. `profiles.py`：22 个原子问题拆成两组——条内组（约 18 个：clarity/readability/atomicity/completeness/self_contained/terminology_defined/acceptance_quantifiable/implementation_free/missing_info/correct/feasible/necessary/traceable/fidelity/conforms_template/req_type/priority/risk）与关系组（consistent_internal/contradicts_siblings/non_redundant/dependencies_declared）。
2. `core.py`：两层调用（第一层 N 次、第二层 1 次）+ 路由合并（条内红 或 关系红 → 打回）。
3. state 打包：第一层挂 `glossary/assumptions/constraints`（模板字段）；第二层喂文档摘要 + 各条 id/text/verdict。
4. 测试：新增两层路由合并用例（现有 57 个测试覆盖单层路由，改造后保持兼容）。

### 关联

- 与"需求条目模板"方案（结构化条目 + 共享上下文：glossary/assumptions/dependencies）配套，第一层依赖其上下文字段。
- 与"判断结果缓存"（SQLite 缓存 + `--export/--eval` 校准闭环）前提一致：拆分后单条可缓存，改一条只重判一条。
