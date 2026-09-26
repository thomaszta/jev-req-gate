# 把你的流程接到 jev-req-gate（嵌入指南）

> 这是给「要接入的人」看的指南。你不必读完 README——先看**下面 30 秒**能不能跑通，再从 5 种嵌入方式里挑一个适合你团队的。

---

## 30 秒最小可用

```bash
pip install jev-req-gate
export TYPESAFE_API_KEY=你的key
jev-req-gate --text "提升用户体验"          # → RED（空泛，被打回）
jev-req-gate --text "库存不足时自动拦截下单"  # → 看 Jev 判定
```

不传上下文也能跑（`--text` 即可）。这是最低门槛——**装了就能把关**。上下文/文档传得越全，判定越准（见 [什么时候必须带上下文](#什么时候必须带上下文)）。

---

## 5 种嵌入方式（先选一种）

| 方式 | 适合谁 | 嵌入点 | 当前支持 | 需要准备 |
|---|---|---|---|---|
| **A 单条即时把关** | 个人 / 评审人 | 贴一条需求就看 | ✅ | 装包 + key |
| **B 仓库级门禁** | 需求文件在 repo 的团队 | PR 用 GitHub Action、commit 用 pre-commit | ✅ | 需求文件 + key + 一次配置 |
| **C 生成即把关（Agent Skill）** | 用 LLM 批量生成需求的团队 | 生成后让 Agent 调 skill | ✅ | 让 Agent 用 `skill/SKILL.md` |
| **D 批量离线把关** | 一次审整批 | CLI `--file` 一次跑完 | ✅ | 需求文件 |
| **E 需求管理联动** | 用 Jira/飞书/Notion | 拉取 → 把关 → 回写 | ⚠️ 路线图，未实现 | 等适配器 |

> **新手建议**：先做 A（今天就能用），再按需升级到 B（自动化门禁）。E 属于长期目标。

---

## 方式 A · 单条即时把关（个人用）

```bash
# 只看一条
jev-req-gate --text "用户可在 50ms 内实时拉取全量征信数据"
jev-req-gate --text "删除商品时需校验是否被订单引用" \
  --project-context "电商库存平台：Python/PostgreSQL，删除需考虑订单引用约束"
```

- `--project-context` 让「现实层（正确/可行/必要）」判断更准——**强烈建议带上**。
- 结果分 `PASS / REVIEW / BLOCK`；BLOCK 的会打印出触发信号（如 `feasible=0.06 < 0.3`）。

## 方式 B · 仓库级门禁（团队，自动）

适合「需求以文件形式进仓库」的团队（需求即代码）。

**① 准备需求文件**（格式见[模板](#需求文件格式与模板)，`.json`/`.csv`/`.txt` 均可）。

**② GitHub PR 门禁** —— 复制 [.github/workflows/req-gate.yml](.github/workflows/req-gate.yml) 到你的仓库，改两个路径：

```yaml
- uses: your-org/jev-req-gate/.github/actions/jev-req-gate@v0.2.0
  with:
    requirements-file: requirements/ai-generated.json   # ← 你的文件
    project-context: "你的项目背景"                       # ← 你的上下文
    typesafe-api-key: ${{ secrets.TYPESAFE_API_KEY }}    # ← 在仓库 Settings→Secrets 加
```

有 BLOCK 项时 job 失败 → 设成 required check，PR 就合不进去。

**③ commit 本地门禁**（可选，pre-commit）：

```bash
pip install pre-commit
# 把 hooks 摘到你的 .pre-commit-config.yaml：
#   - repo: https://github.com/<你>/jev-req-gate
#     rev: v0.2.0
#     hooks: [{ id: jev-req-gate }]
pre-commit install
```

## 方式 C · 生成即把关（AI 原生，适合「用 LLM 批量生成需求」）

让生成需求的 Agent 在产出后自动把关。项目自带 [skill/SKILL.md](skill/SKILL.md)，Agent 按其中约定：把每条需求 + 项目上下文打包成 state、跑 22 个原子问题、按阈值路由——**生成一批、当即把 BLOCK/REVIEW 标出来**，而不是等人肉通读。

## 方式 D · 批量离线把关（一次审整批）

```bash
jev-req-gate --file requirements/batch.json \
  --project-context "你的上下文" \
  --document-file requirements/batch.json \
  --out report.csv
```

- `--document-file` 传整篇，才能检测**跨条目矛盾**（方式 B/C/D 建议都带）。
- `report.csv` 可贴进看板；也支持 `--out report.json`。

## 方式 E · 需求管理联动（路线图）

从 Jira / 飞书 / Notion 拉取待审需求 → 把关 → 回写 type/priority/risk 标签。尚未实现（见 [路线图](README.md)）；期间可先用方式 D 把导出文件把关。

---

## 需求文件格式与模板

支持 `.json`（数组，元素可带 `text`/`archived`）、`.csv`（`text` 列）、`.txt`（每行一条）。

**先复制模板再填**：[examples/requirements.example.json](examples/requirements.example.json)（JSON，推荐，可带逐条上下文）或
[examples/requirements.example.md](examples/requirements.example.md)（Markdown 转 json/txt 用）。

## 什么时候必须带上下文

| 场景 | 建议带 | 不带会怎样 |
|---|---|---|
| 判断正确/可行/必要 | `--project-context` | 现实层参照缺失，易误判 |
| 判断跨条目矛盾 | `--document-file` | 检测不到条目间矛盾 |
| 判断冗余 | `--existing-file` | 检测不到与既有需求重复 |
| 对齐上一版 | `--archived` | 无法对比旧归档 |

> 记不住也不影响跑——**默认就可用，带全更准**。这是刻意设计：先让你跑起来，再逐步加参照。

## 常见问题

- **key 会泄漏吗？** 用环境变量或 CI Secret，不写进代码/文件（CLI 从 `TYPESAFE_API_KEY` 读）。
- **误判怎么办？** 阈值可调：`--thresholds-file` 传 JSON 覆盖；「误打回好需求」就调高 `block_noul_pos`，「漏检」就调低 `review_score`（见 [docs/methodology.md](docs/methodology.md) §5）。
- **我想加自己的判据？** 复制问题库 JSON，`--profile-file` 传入（格式见 `src/jev_req_gate/profiles.py`）。
- **团队模板不一样？** 问题库可改成符合你团队模板的问题，`conforms_template` 那题换成你的必填字段。

---

*配套：[README](README.md) · [方法论](docs/methodology.md) · [对比基准](docs/benchmark.md) · [playground](playground/index.html)*
