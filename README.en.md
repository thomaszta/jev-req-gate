# jev-req-gate

**A quality gate for AI-generated requirements, powered by Jev (TypeSafe System One).**

> *[English](README.en.md) · [中文](README.md)*
>
> **🚀 Try it instantly — no API key, no install** (either way): open [`playground/index.html`](playground/index.html) locally in any browser; or after publishing to GitHub Pages, visit `https://thomaszta.github.io/jev-req-gate/playground/`.

<p align="center">
  <img src="https://img.shields.io/pypi/v/jev-req-gate" alt="PyPI version">
  <img src="https://img.shields.io/pypi/pyversions/jev-req-gate" alt="Python versions">
  <img src="https://img.shields.io/badge/benchmark-real%20measurement-blue" alt="benchmark">
</p>

In the AI era the problem isn't "nobody writes requirements" — it's that there are *too many*, they *look too real*, and nobody can review them one by one. `jev-req-gate` turns quality judgment from a subjective human habit into **programmable, batchable, confidence-bearing structured signals**: it doesn't rewrite requirements and doesn't explain its reasoning. It only answers *"what state is this requirement's quality in"* and routes each item to **PASS / REVIEW / BLOCK** by calibrated thresholds.

**What is Jev?** [Jev](https://docs.typesafe.ai/introduction/quickstart) is TypeSafe AI's System One model: it generates no text — it answers parallel atomic judgments on your input and returns calibrated, structured signals (Choice / Score / Noul). It is a *judge*, not a *writer*. **How much does it cost?** Official pricing is `$0.042/MTok` input, output free; this repo measured 34 judgments at a total of ≈`$0.0022` (see [docs/benchmark.md](docs/benchmark.md)).

---

## Highlights

- **MECE 5 faces × 22 atomic questions**: Expression / Content / Reality / Relation / Governance — covering exactly where AI-generated requirements fail (generic hallucinations, intent drift, infeasibility, redundancy, contradictions, reliance on out-of-document implicit knowledge).
- **Calibrated routing**: thresholds tuned against real Jev output (see [docs/methodology.md](docs/methodology.md)).
- **State bundling**: one requirement + project context + existing requirements + the full document are evaluated together in a single call.
- **Multiple consumption shapes**: CLI, Python API, Agent Skill.
- **Configurable**: custom question profile (`--profile-file`) and thresholds (`--thresholds-file`).
- **Try it with zero friction**: `--demo` needs no API key; a **key-free [playground](playground/index.html)** reproduces the routing in your browser; pytest covers the core logic.
- **Real, reproducible benchmark**: `benchmarks/` runs Jev vs an LLM on the same test set and same judging protocol — **both Jev and DeepSeek V4 Flash were measured for real in this repo** (see [docs/benchmark.md](docs/benchmark.md)).
- **CI & local gating**: a reusable [GitHub Action](.github/workflows/req-gate.yml) (PR gate + CSV report) and a [pre-commit hook](.pre-commit-hooks.yaml) that fail on blocked requirements.
- **Judge once, tune the threshold for free**: a SQLite request cache means the same requirement is judged by Jev once; threshold tweaks and report regeneration never spend another call.
- **Label-calibration loop (HITL)**: `--export` dumps judged requirements with empty `label` fields; annotate `pass|block`; `--eval` scans and recommends a threshold set printed as a ready-to-use `--thresholds-file` (see next section).
- **Point it at a whole document**: `--from-document x.md` splits the requirements document (recognizes `1.` / `R01` / `- [ ]` / table rows), numbers the items, and gates in one command; reports carry IDs that map back to the source. Confirm the split first with `--no-gate` / `--prepared`.

## Install

```bash
pip install -e .          # installs the `jev-req-gate` command / `jev_req_gate` module
export TYPESAFE_API_KEY=your_key
```

`typesafe-sdk` is a runtime dependency and installs automatically. No install needed to try it: `python reqgate.py` works from the repo root.

## See it work in 30 seconds

```bash
# ① No install, no API key — see the routing logic (3 seconds)
python3 reqgate.py --demo unrealistic        # → RED (vague requirement blocked)

# ② For real gating: install the runtime dep + get a key from the TypeSafe dashboard
pip install typesafe-sdk
export TYPESAFE_API_KEY=your_key
python3 reqgate.py --text "Improve user experience"   # → RED (vague, blocked)
```

Pick an integration mode that fits your team — **instant · GitHub Action · pre-commit · agent skill · batch** — see [INTEGRATION.md](INTEGRATION.md). Copy a requirement file template to get started: [example.json](examples/requirements.example.json) / [example.md](examples/requirements.example.md).

## Quick start

```bash
# ① Demo the routing logic without any API key
python -m jev_req_gate --demo unrealistic
```

```text
[RED BLOCK] (demo)
    quality avg: 4.17   risk: low
    - feasible=0.22 < 0.3

1 total: pass=0 review=0 block=1
```

```bash
# ② Real gate: requirements + project context + full document (catches cross-item contradictions)
TYPESAFE_API_KEY=your_key jev-req-gate \
  --file examples/document_demo.json \
  --document-file examples/document_demo.json \
  --project-context "E-commerce inventory platform: Python/PostgreSQL; order-reference constraints and concurrency on stock deduction; settlement depends on an internal payment gateway" \
  --out report.csv

# ③ Gate a whole requirements document without manual splitting: split → number → gate → report
TYPESAFE_API_KEY=your_key jev-req-gate \
  --from-document requirements.md --out report.csv
#   → recognizes 1. / R01 / - [ ] / table rows; writes requirements.md.prepared.json
#   Split only: add --no-gate; after confirming items: --prepared requirements.md.prepared.json
```

### Real Jev output sample

Run against [examples/document_demo.json](examples/document_demo.json) (contains a contradictory pair, one vague item, one infeasible item):

| Requirement | Signal Jev caught | Verdict |
|---|---|---|
| Block deleting referenced products | `contradicts_siblings=0.75` (contradicts the next item) | RED |
| Allow force-deleting referenced products | `contradicts=0.86`, `correct=0.17` | RED |
| "Improve user experience" (vague) | `correct=0.21`, `feasible=0.23` | RED |
| Payment gateway settlement (sound) | only a low quality score | YELLOW (not over-blocked) |
| Pull third-party data in real-time within 50ms (infeasible) | `feasible=0.06`, `correct=0.08` | RED |

> Core finding: Jev is reliable on **reality-layer (correct/feasible/necessary/self-contained) and cross-item contradiction** signals — use them as hard block signals. Quality score / terminology / risk output is conservative or inflated and is demoted to a hint. Full calibration in [docs/methodology.md §5.5](docs/methodology.md).

## CLI options

| Option | Meaning |
|---|---|
| `--text "requirement"` | Single requirement text |
| `--file path` | Batch of requirements (.json/.csv/.txt, already split) |
| `--from-document x.md` | **Whole requirements document (.md/.txt)**: split + number + gate in one command (add `--no-gate` to only split) |
| `--prepared x.prepared.json` | Reuse a human-confirmed split (IDs preserved) |
| `--no-gate` | With `--from-document`: split and write prepared.json only |
| `--project-context` | Project background / constraints / stack (reality-layer reference) |
| `--existing-file` | Existing requirements, for non-redundancy judgment |
| `--document-file` | The full document, for cross-item contradiction judgment |
| `--archived` | Previous-version archived requirements (optional) |
| `--profile-file` | Custom question profile JSON |
| `--thresholds-file` | Custom thresholds JSON |
| `--demo good\|ambiguous\|unrealistic` | Key-free demo |
| `--out report.csv\|.json` | Export report |
| `--db path` | Request-cache SQLite path (default `~/.jev_req_gate/cache.db`; `JEV_REQ_GATE_DB` overrides) |
| `--cache-stats` / `--cache-clear` | Show cache stats / clear the cache |
| `--export path.jsonl` | Export cached judgments as JSONL for human labeling |
| `--eval path.jsonl` | Read labels back, scan and recommend thresholds (`--max-error`, default 0.1) |

Exit codes: `0` all pass / `1` some blocked (or empty export) / `2` usage or dependency error.

## Label-calibration loop (HITL)

The one part that genuinely needs a human is **the middle band** (yellow → review). This tool turns that into an actionable loop and automates everything else:

```bash
# ① Gate normally (judgments land in the cache automatically)
jev-req-gate --file requirements.json --project-context "..." --db cache.db

# ② Export judgments; change each row's label to pass or block
jev-req-gate --export labeled.jsonl --db cache.db

# ③ Read labels back; scan k (whitelist threshold multiplier) and recommend
#    the least-false configuration whose miss rate stays within --max-error
jev-req-gate --eval labeled.jsonl --max-error 0.1

# ④ Save the printed thresholds JSON as your --thresholds-file
```

- `eval` scans k ∈ [0.6, 1.4]: k>1 is stricter (blocks more), k<1 looser. It reports **miss / intercept-recall / false-block** per k and recommends the strictest k whose miss rate stays ≤ `--max-error`, printing a ready-to-save thresholds JSON.
- If any item was auto-passed (green) yet labeled `block`, `eval` tells you plainly that **thresholds cannot fix it** — inspect that item's signals or add an atomic question. It surfaces the truth instead of quietly tuning it away.
- Only successful judgments are cached; failures are never cached and are retried on the next run.

## As a Python library

```python
from jev_req_gate import run_gate, decide, demo_answers
from jev_req_gate.profiles import DEFAULT_THRESHOLDS

# Pure routing (no API needed)
verdict, reasons, detail = decide(demo_answers("unrealistic"), DEFAULT_THRESHOLDS)
assert verdict == "red"

# Real API gate (requires TYPESAFE_API_KEY)
result = run_gate("Improve user experience", {"project_context": "..."}, DEFAULT_THRESHOLDS)
```

## As an Agent Skill

The repo ships `skill/SKILL.md` so an agent (Claude Code / Doubao / etc.) can either drive this tool for requirement QA, or follow its conventions to call TypeSafe directly.

## Project layout

```
src/jev_req_gate/        # core package: profiles(questions/thresholds) · core(routing/state) · cli · report · store(cache) · labels(calibration) · doc_parser(document split)
tests/                   # pytest: routing / profile integrity / parsing / export / cache / calibration / document split
examples/                # real test set with contradiction / vague / infeasible items
benchmarks/              # benchmark: test set + benchmark.py (jev / llm backends)
playground/              # key-free interactive playground (single HTML file)
hooks/                   # pre-commit hook
.github/                 # CI + publish workflows, reusable jev-req-gate action
skill/SKILL.md           # Agent Skill shape
docs/methodology.md      # full methodology & real calibration log
docs/benchmark.md        # Jev vs LLM benchmark report (measured + honest boundaries)
```

## Integrations

**GitHub Action** — gate requirements on every PR, upload a CSV report, and fail the job when anything is blocked:

```yaml
- uses: thomaszta/jev-req-gate/.github/actions/jev-req-gate@v0.2.0
  with:
    requirements-file: requirements/ai-generated.json
    project-context: "E-commerce inventory platform: Python/PostgreSQL"
    typesafe-api-key: ${{ secrets.TYPESAFE_API_KEY }}
```

See the bundled [PR workflow](.github/workflows/req-gate.yml). **pre-commit** — fail the commit when a changed requirement file contains a blocked item; register via `.pre-commit-hooks.yaml` or the local example in `.pre-commit-config.yaml`.

## Benchmark: Jev vs a general LLM

Same test set (17 items, organized by MECE 5 faces), same judging protocol (HITL three-state), **both measured for real in this repo** (17 items × 2 runs each):

| Metric | **Jev** | **DeepSeek V4 Flash** |
|---|---|---|
| **Intercept rate (bad not passed)** | **0.92** (11/12, missed r15 duplicate) | 0.92 (missed the same duplicate) |
| **False-block (good blocked)** | **0.0** (0/5) | **0.6** (3/5) |
| Auto-pass (good) | **0.4** (r01/r05 green) | 0.4 |
| Review rate | 0.35 | 0.0 |
| Judgment consistency (2 runs) | **1.0** | 0.94 |
| Latency p50 / p95 | 0.67s / 0.84s | 1.90s / 9.80s |
| Cost (34 calls) | **$0.0022** | $0.0197 |

See [docs/benchmark.md](docs/benchmark.md). **Conclusion**: Jev fits the "layered routing layer" of a gate (v0.6.0) — good items can auto-pass (red/yellow/green all present), zero false-blocking, stable, far cheaper/faster, natively routable output; the costs are a 35% review rate and **redundancy-class bad items (r15) being missed just like DeepSeek — a shared blind spot, catch it with ID-level dedup at the process layer**. DeepSeek is more "decisive" but false-blocks 60% of good items. Correct pattern = **Jev layered routing (red block / green pass / yellow review) + humans reviewing yellow + process-level dedup**.

## Boundaries & disclaimer

- **Jev accepts text state only** — no images/audio/video.
- **It judges, it doesn't advise**: it won't rewrite a vague requirement or explain *why*. Reasons are for human review.
- **Calibration ≠ per-item certainty**: Jev probabilities are population-calibrated; the middle band (0.25~0.75) *must* go to human review — don't hard-resolve it in code.
- **It's a gate, not a generator**: it gates AI-generated requirements; it won't make vague requirements clear.

## Roadmap

- [ ] Pull pending requirements straight from requirement trackers (Jira / Feishu / Notion)
- [ ] Emit a "what info is missing" highlight list (wire up `missing_info`)
- [ ] Multiple System One models beyond `jev-latest`
- [ ] Undecided semantics: failed calls marked "undecided" → route to review and auto-retry (aligned with jevclip's failure handling)

## License

[MIT](LICENSE)
