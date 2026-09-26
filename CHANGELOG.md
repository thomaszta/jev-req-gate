# Changelog

All notable changes to `jev-req-gate` are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.2] - 2026-09-26

### Changed (user real-device test: "is the skill package complete? can splitting be improved?")
- **Skill package is now self-contained**: the installed copy at `~/Doubao/skills/jev-req-gate/`
  ships `src/` + `reqgate.py` + `pyproject.toml`, so it runs without a global pip install
  (`python3 <skill_dir>/reqgate.py`). SKILL.md documents both entry modes.
- **Splitting fixes for real-doc shapes**:
  - User-story title lines (`故事 2：远程下发配方`, `US-3 取消订单`) now start a new item instead
    of being swallowed into the previous item's continuation text.
  - Table noise cells (`略` / `无` / `-` / `N/A` …) are filtered — a row of placeholders no
    longer produces a junk requirement item.
- Tests: 54 → 57 (story line, US-number form, table-noise). All passing.

## [0.6.1] - 2026-09-25

### Changed (user-driven: "can ordinary users understand this demo?")
- **First-impression fixes (README zh/en)**: removed dead `<owner>` placeholders (playground
  opens locally in any browser; Pages URL shown as post-publish instruction), added a
  "What is Jev? + price" line to the hero, and rewrote the 30-second path to run on the
  zero-install `reqgate.py --demo` instead of a not-yet-published `pip install jev-req-gate`.
- **`--no-gate` no longer requires an API key** (found during the document-parsing review):
  pure splitting (`.prepared.json`) works without `TYPESAFE_API_KEY`/SDK. Test added.
- **Human-readable reasons**. `decide()` now emits reasons like
  `【自足性】self_contained=0.28 < 0.3：依赖文档外的隐形知识/假设，无法独立理解验证`
  instead of raw signal names — every signal key maps to a Chinese defect label
  (`HUMAN_SHORT`/`HUMAN_NOTE` in profiles.py). CLI output, CSV `reasons` column and
  `--demo` all show the human version. No routing logic changed.

## [0.6.0] - 2026-09-25

### Changed (user-driven: "a normal document should have red, yellow AND green")
- **Green is now meaningful**. Previously green required "no yellow signal at all", but Jev's
  conservative output on Chinese requirements (low terminology, low confidence, risk=high)
  made every good item yellow → 0 greens on real documents, i.e. no differentiation.
  `decide()` now routes: **green = no red + 7 key signals all healthy**
  (`green_score 2.0`, `green_noul_min 0.6` for correct/feasible/necessary/acceptance_quantifiable/
  non_redundant, `green_self_contained 0.5`, `green_contradicts_max 0.4`,
  `green_impl_max 0.6`); **yellow = strong warning present**; **red unchanged**.
  Weak noise (terminology low, risk=high, low confidence, conforms_template low) no longer
  forces yellow — it stays as hints in reasons.
- **Benchmark re-measured on the same real Jev answers (zero new API calls)**:
  good items now r01/r05 → GREEN, r02/r03/r04 → YELLOW; auto-pass 0.0 → **0.4**;
  review rate 0.53 → **0.35**; intercept 1.0 → **0.9167** because r15 (a duplicate of r01,
  whose signals Jev judges healthy) is auto-passed — **the same item DeepSeek also missed**.
  False-block stays 0. Honest trade-off, recorded in docs/benchmark.md.
- Tests: 53 total (green-tier rules + weak-noise-not-blocking-green), all passing.

## [0.5.0] - 2026-09-25

### Changed (real-user finding → fix)
- **`implementation_free` removed from the block whitelist** (`block_neg_keys` added, defaults to
  `["contradicts_siblings"]`). A real user ran a *better-written* requirements document (metrics,
  constraints, compatibility, encryption) and got 8 false REDs — all caused by
  `implementation_free > 0.7` punishing detail. It now only raises a YELLOW hint
  (`> review_neg_hi 0.5`). Teams that still want it as a hard block can set
  `block_neg_keys: ["contradicts_siblings", "implementation_free"]` via `--thresholds-file`.
- **SKILL.md/doc wording now matches code**: "block only on reliable signals" = 5 positive
  whitelist signals + `contradicts_siblings` (negative whitelist). Previously the claim
  contradicted `decide()` for negative dimensions — fixed.

### Added
- `examples/thresholds.strict.json` — opt-in stricter profile (blocks more, for teams that want
  the gate to auto-red instead of routing everything to review).
- SKILL.md "3-step quick start" + "how to read the verdicts" section (a real user reported not
  knowing where to start after invoking the skill).
- Tests: 2 new (implementation_free high → yellow only; custom `block_neg_keys` restores red).
  51 total, all passing.

## [0.4.0] - 2026-09-25

### Added
- **Document adapter (`doc_parser.py` + `--from-document`)**: point the CLI at a *whole* requirements
  document (`.md`/`.txt`) instead of pre-split items. Heuristic splitting recognizes numbered
  items (`1.` / `2.1` / `R01` / `REQ-02`), Markdown lists (`- [ ]`), and table rows; continuation
  lines merge into the parent item; background paragraphs stay out of the item list.
- **Prepared-flow (HITL)**: `--from-document x.md` writes `x.md.prepared.json` with numbered
  items (`R01…`) and original `source_ref`s, prints the split for review, then gates —
  or `--no-gate` to only prepare. Edit the JSON, then `--prepared x.md.prepared.json`
  reuses it with IDs preserved.
- **Item-level `document` semantics**: the split items' full texts (plus background) are fed as
  `state.document` instead of line fragments — `contradicts_siblings` now sees real item context.
- **ID tracking**: CSV reports gain a leading `id` column and console output prefixes
  `[R03 RED 打回]`, so verdicts map back to the source document.
- Tests: 10 new cases (numbers / alpha IDs / lists / tables / continuations / context
  separation / item-level document / prepared round-trip). 49 total, all passing.

## [0.3.0] - 2026-09-25

### Added
- **Request cache** (`store.py`): SQLite cache keyed by request hash (model + state + profile).
  The same requirement + context is judged by Jev once; reruns, threshold tweaks, and report
  regenerations read the cache instead of calling the API. Failed judgments are never cached
  (they are retried on the next run). Cache location: `~/.jev_req_gate/cache.db`, overridable with
  `JEV_REQ_GATE_DB` or `--db`.
- **Label-calibration loop** (`labels.py` + `--export` / `--eval`): `jev-req-gate --export out.jsonl`
  dumps judged requirements with empty `label` fields; humans annotate `pass|block`;
  `--eval` scans a uniform threshold multiplier `k` (0.6–1.4), reports miss / intercept-recall /
  false-block per `k`, and recommends the strictest `k` whose miss rate stays within `--max-error`
  (default 0.1), printed as a ready-to-use `--thresholds-file`.
- New CLI flags: `--db`, `--cache-stats`, `--cache-clear`, `--export`, `--eval`, `--max-error`.
- Tests: 13 new cases (cache hit/miss/dedup, request-hash stability, cache reuse without API calls,
  export format, threshold sweep & recommendation). 39 total, all passing.
- Version bumped to `0.3.0` (`__init__.py`, `cli.py`, `pyproject.toml`).

### Changed
- `run_gate()` accepts optional `store` (and `profile`) and returns `cached`; CLI gates reuse the
  cache automatically and prints “判定来自缓存，未调用 Jev” on hits.
- `--version` now reports `0.3.0`.

## [0.2.0] - 2026-09-25

### Added
- **English docs** for the global community: `README.en.md`, `docs/benchmark.en.md`, `docs/methodology.en.md`.
- **Key-free playground** (`playground/index.html`): interactive, single-file HTML that reproduces the
  real `decide()` routing and calibrated thresholds — no API key or install needed. Ships ready for GitHub Pages.
- **GitHub Action** (`jev-req-gate` composite action + PR workflow): gate requirements in CI, upload a
  CSV report, and fail the job when anything is blocked. See `.github/workflows/req-gate.yml`.
- **pre-commit hook** (`hooks/jev_req_gate_hook.py` + `.pre-commit-hooks.yaml` + `.pre-commit-config.yaml`):
  fail the commit when a changed requirement file contains a blocked item.
- **Benchmark upgraded to real measurements**: LLM column is now **DeepSeek V4 Flash** measured in-repo
  (previously a public-source citation). Jev: accuracy 1.0, zero over-blocking, consistency 1.0, 20 calls
  `$0.0013`; DeepSeek: accuracy 0.8, over-block rate 0.5, consistency 0.9, 20 calls `$0.0101`.
- **PyPI release readiness**: `CHANGELOG.md`, publish workflow (`.github/workflows/publish.yml`),
  version bumped to `0.2.0`.

### Fixed
- `benchmark.py` judging inversion: `_verdict_is_block()` was applied to an already-boolean `majority_block`,
  which inverted the printed verdicts (showed block-recall 0.0 when Jev actually blocked all 6 bad items).
  Fixed and re-measured.
- `benchmark.py` LLM prompt: JSON braces in the prompt collided with `str.format()` placeholders (KeyError).
  Escaped to double braces.

## [0.1.0] - 2026-09 (initial)

- MECE 5 faces × 22 atomic questions (Expression / Content / Reality / Relation / Governance).
- State bundling: requirement + project context + existing requirements + full document in one call.
- Calibrated routing `PASS / REVIEW / BLOCK` with threshold whitelist (reality-layer + contradiction).
- CLI (`jev-req-gate`), Python API, Agent Skill (`skill/SKILL.md`), key-free `--demo`.
- Configurable question profile & thresholds.
- `docs/methodology.md` (v2, with real calibration log §5.5) and `benchmarks/` (test set + benchmark.py).
