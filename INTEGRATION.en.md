# Wiring jev-req-gate into your workflow (integration guide)

> For the person integrating it. You don't need to read the whole README first —
> try the **30-second path** below, then pick one of the 5 integration modes.

---

## 30-second minimum

```bash
pip install jev-req-gate
export TYPESAFE_API_KEY=your_key
jev-req-gate --text "Improve user experience"     # → RED (vague, blocked)
jev-req-gate --text "Block checkout when stock is insufficient"
```

It runs with `--text` alone — **installed means gated**. The more context/document you pass, the more accurate the verdict (see "when to pass context" below).

## Pick a mode

| Mode | For whom | Hook | Support | To prepare |
|---|---|---|---|---|
| **A · Instant single-item** | individuals / reviewers | paste one requirement | ✅ | install + key |
| **B · Repo-level gate** | teams with requirement files in the repo | GitHub Action on PR, pre-commit on commit | ✅ | file + key + one-time config |
| **C · Gate at generation (Agent Skill)** | teams generating with LLMs | agent calls the skill after generation | ✅ | point agent at `skill/SKILL.md` |
| **D · Batch offline** | review a whole batch at once | CLI `--file` | ✅ | requirement file |
| **E · Tracker integration** | Jira / Feishu / Notion teams | pull → gate → write back | ⚠️ roadmap, not yet | adapter |

> **Start with A** (works today), then upgrade to B for automation. E is a long-term goal.

## Mode A · Instant (personal)

```bash
jev-req-gate --text "User can pull full credit data in real time within 50ms"
jev-req-gate --text "Deleting a product must verify it's not referenced by orders" \
  --project-context "E-commerce inventory: Python/PostgreSQL; deletion must respect order references"
```

`--project-context` makes the reality layer (correct/feasible/necessary) far more accurate — **strongly recommended**.

## Mode B · Repo-level gate (team, automated)

For teams where requirements live in the repo (requirements-as-code).

**①** Prepare a requirement file (`.json`/`.csv`/`.txt`; see [templates](#requirement-file-format--templates)).

**② GitHub PR gate** — copy [.github/workflows/req-gate.yml](.github/workflows/req-gate.yml), change two paths:

```yaml
- uses: your-org/jev-req-gate/.github/actions/jev-req-gate@v0.2.0
  with:
    requirements-file: requirements/ai-generated.json   # ← yours
    project-context: "Your project context"             # ← yours
    typesafe-api-key: ${{ secrets.TYPESAFE_API_KEY }}   # ← add in Settings→Secrets
```

A BLOCK fails the job → make it a required check and blocked PRs can't merge.

**③ Commit gate (optional, pre-commit)**:

```bash
pip install pre-commit
# add to your .pre-commit-config.yaml:
#   - repo: https://github.com/<you>/jev-req-gate
#     rev: v0.2.0
#     hooks: [{ id: jev-req-gate }]
pre-commit install
```

## Mode C · Gate at generation (AI-native)

Point your generating agent at [skill/SKILL.md](skill/SKILL.md). It bundles each requirement + project context into a state, runs the 22 atomic questions, and routes by threshold — **batch-generate, immediately flag BLOCK/REVIEW**, instead of waiting for a human read.

## Mode D · Batch offline

```bash
jev-req-gate --file requirements/batch.json \
  --project-context "your context" \
  --document-file requirements/batch.json \
  --out report.csv
```

Pass `--document-file` (the whole doc) to detect **cross-item contradictions**. `report.csv` (or `--out report.json`) can go straight into your board.

## Mode E · Tracker integration (roadmap)

Pull pending requirements from Jira / Feishu / Notion → gate → write back type/priority/risk labels. Not implemented yet; meanwhile use Mode D on an export.

---

## Requirement file format & templates

Supported: `.json` (array; each element may carry `text`/`archived`), `.csv` (`text` column), `.txt` (one per line).

**Copy a template, then fill it in**: [examples/requirements.example.json](examples/requirements.example.json) (recommended) or
[examples/requirements.example.md](examples/requirements.example.md) (convert md to json/txt first).

## When to pass context

| You want to judge | Pass | Without it |
|---|---|---|
| correct / feasible / necessary | `--project-context` | reality-layer reference missing, misjudges |
| cross-item contradictions | `--document-file` | contradictions undetected |
| redundancy vs existing | `--existing-file` | duplicates undetected |
| vs previous version | `--archived` | no diff against old archive |

> You can't get this wrong — **defaults work, fuller is more accurate**. Designed so you run first and add context later.

## FAQ

- **Key safety?** Use an env var or CI Secret; never commit it (CLI reads `TYPESAFE_API_KEY`).
- **Misjudgments?** Tune thresholds via `--thresholds-file` JSON; "over-blocking good items" → raise `block_noul_pos`; "missing bad items" → lower `review_score` (see [docs/methodology.md](docs/methodology.md) §5).
- **Add your own criteria?** Copy the profile JSON and pass `--profile-file` (format in `src/jev_req_gate/profiles.py`).
- **Different team template?** Rebuild the profile around your required fields; the `conforms_template` question becomes your checklist.

---

*See also: [README](README.md) · [Methodology](docs/methodology.md) · [Benchmark](docs/benchmark.md) · [Playground](playground/index.html)*
