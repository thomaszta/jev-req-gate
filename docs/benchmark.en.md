# Benchmark: gating requirement quality with Jev vs a general LLM

> **Data provenance (stated honestly).** Every number below was produced by the same `benchmarks/benchmark.py` against the same `benchmarks/test_set.json` with real API calls:
> - **Jev column**: measured with `TYPESAFE_API_KEY` (2026-09).
> - **LLM column**: **DeepSeek V4 Flash** (`deepseek-flash` = DeepSeek-V4.1-Flash), measured with the `OPENAI_API_KEY` you supplied.
>
> Both columns share the same test set, judging protocol, and collection script. Public third-party data appears only as supplementary evidence.

---

## 1. Method & protocol

### Test set `benchmarks/test_set.json` (v2, aligned with the MECE 5 faces)

17 items: **5 should-pass + 12 should-block**. Bad items are organized by the methodology's **MECE 5 faces × 22 atomic questions**, each tagged with `facet`/`signal`/`defect`, covering every pain point the tool targets (self-containment / out-of-document implicit knowledge, intent drift / generic knowledge taken as fact, redundancy, contradictions, etc.):

| Face | Bad items | Signal / defect |
|---|---|---|
| **Expression** | r06 / r07 | clarity (vague, untestable) / atomicity (mixed multiple) |
| **Content** | r08 / r09 / r10 | self_contained (relies on hidden knowledge) / implementation_free (solution-as-requirement) / missing_info |
| **Reality** | r11 / r12 / r13 / r17 | fidelity (intent drift) / feasible (infeasible) / necessary (decorative redundancy) / correct (dangerous) |
| **Relation** | r14 / r15 | contradicts_siblings (contradicts another item) / non_redundant (duplicates another) |
| **Governance** | r16 | conforms_template (no acceptance criteria) |

### Judging protocol (HITL three-state, per [docs/methodology.md](docs/methodology.md))

- Jev: `green`=auto-pass / `yellow`=human review / `red`=auto-block.
- LLM two-state mapped to the same semantics: `pass`→pass, `block`→block (no review tier).
- **intercept rate**=bad items intercepted (blocked *or* sent to review — anything not passed); **auto-block**=bad items judged red/block; **false-block**=good items judged red/block; **auto-pass**=good items judged green/pass.
- Each item runs **2×** for consistency.
- Cost: Jev `$0.042/MTok` input (output free); DeepSeek peak `$0.30` input / `$1.20` output.

## 2. Symmetric real results (same test set, 17 items × 2 runs each)

| Metric | **Jev** (System One) | **DeepSeek V4 Flash** | Reading |
|---|---|---|---|
| **Intercept rate (bad items not passed)** | **0.9167** (11/12) | 0.9167 (11/12; missed r15 duplicate) | **Same blind spot: both miss r15 (duplicate)** |
| Auto-block (bad → red/block) | 0.6667 (8/12) | 0.9167 (11/12) | DeepSeek blocks more decisively |
| **False-block (good items blocked)** | **0.0** (0/5) | **0.6** (3/5: r02/r04/r05) | Jev zero, LLM blocks most good items |
| **Auto-pass (good → green/pass)** | **0.4** (2/5: r01/r05) | 0.4 (2/5: r01/r03) | Tie — both auto-pass healthy items |
| Review rate | 0.3529 (6/17) | 0.0 | Jev sends uncertainty to humans |
| Consistency (2 runs) | **1.0** | 0.9412 | Jev steadier |
| Latency p50 / p95 | 0.67s / 0.84s | 1.90s / 9.80s | Jev ≈2.8× / 11.7× faster |
| Cost (34 calls) | **$0.0022** | $0.0197 | Jev ≈9× cheaper |

> **Protocol note (v0.6.0).** The Jev column was re-measured under v0.6.0, which redesigned the **green**
> tier. Previously green required "no yellow signal at all", but Jev's conservative output on Chinese
> requirements (low terminology, low per-dimension confidence, risk=high) made every good item yellow —
> i.e. no differentiation at all (your field feedback: "all yellow means this tool is useless").
> Now **green = all 7 key signals healthy** (self_contained ≥0.5, correct/feasible/necessary/
> acceptance_quantifiable/non_redundant ≥0.6, contradicts_siblings ≤0.4, implementation_free ≤0.6,
> quality ≥2.0); yellow = a strong warning present; red unchanged. Numbers were recomputed **offline from
> the same real Jev answers** (zero new API calls; answers are persisted in `benchmarks/report_jev.json`),
> see [docs/methodology.md §5.5](docs/methodology.md).

### Per-item verdicts (real)

- **Jev**: good items **r01/r05 → green** (auto-passed, signals healthy), r02/r03/r04 → yellow (each has a strong warning: self-containment / risk / confidence); bad r06/10/11/12/13/14/16/17 → `red` (auto-block), r07/08/09 → `yellow` (review), **r15 (duplicate of r01) → green (missed)**.
- **DeepSeek**: good r01/r03 → pass, **r02/r04/r05 → BLOCK (3 over-blocked)**; all bad → block **except r15 (duplicate) → pass (missed)**.

> A gate fears two things: **bad requirements leaking into development** and **good requirements being blocked**.
> - **r15 (a duplicate of r01) is missed by BOTH Jev and DeepSeek** — every signal of r15 looks healthy
>   (Jev: self_contained 0.56 / correct 0.92 / necessary 0.88 / non_redundant 0.69), so redundancy is a
>   **shared blind spot**. This is the honest counter-evidence: v0.6.0's relaxed green line means the
>   "zero misses" claim no longer holds for redundancy; to catch duplicates, do ID-level dedup at the
>   requirements-management layer (see README P2 roadmap).
> - **False-block: Jev 0 vs DeepSeek 0.6** — Jev's core advantage (never hurts good items) is unchanged.
> - **Auto-pass 0.4 vs 0.4** — v0.6.0 lets Jev auto-pass clearly healthy items too (red/yellow/green all present).

## 3. Honest reading & boundaries

1. **Jev is a conservative layered router (v0.6.0)**: good items can go green (0.4), bad items mostly red (0.67) with some yellow, gray-zone (strong warnings) goes to review; **false-block 0**. Costs: 35% of items still go to review, and **redundancy-class bad items (r15) get passed** — Jev's non_redundant signal is weak.
2. **DeepSeek is a decisive binary judge**: higher auto-split ratio, but blocks 60% of good items and misses r15.
3. **Trade-off**: for a quality gate (priorities = don't hurt good items + humans can absorb yellow) → Jev; for "automate as much as possible" and you can tolerate false-blocks and will tune the prompt → LLM. **Both share the redundancy blind spot — handle dedup at the process layer.**
4. **The LLM uses a plain-but-reasonable single prompt** (built into benchmark.py, no prompt engineering). Comparable structured prompting would cut its false-block, but that's deep customization, not turnkey.
5. **Small test set (17 items)**: conclusions hold for this reproducible setting; extend `test_set.json` and rerun.

## 4. Public sources (supplementary, not measured here)

| Source | Scenario | Jev | General LLM |
|---|---|---|---|
| [OpenRouter](https://openrouter.ai/blog/tutorials/jev-vs-llm-when-to-use-each/) | intent-classification accuracy | 98.3% | 98.3% (GPT Luna) tied |
| [OpenRouter](https://openrouter.ai/blog/tutorials/jev-vs-llm-when-to-use-each/) | p50 latency | 0.194s | 1.106s (≈5.7× slower) |
| [OpenRouter LLM-as-judge](https://openrouter.ai/blog/tutorials/jev-vs-llm-as-a-judge/) | closed-form rule judging | accuracy tied, better calibration | 1/5 cost, 1/10 latency |
| [LangChain Agent Evals](https://www.langchain.com/blog/jev-agent-evals-langsmith) | binary pass/fail | 500/500 matches oracle | Terra 99.8% / Claude 80.0% |
| [Tencent ADP](https://adp.tencent.com/zh/blog/jev-vs-general-llm-automated-decision-selection) | 500 tickets cost | $0.0103 | ~$2.45 (≈238× cheaper) |

### The honest counter-evidence

Jev trails frontier LLMs on **open-ended, graded / whole-document** tasks:

- [arXiv 2609.24574](https://arxiv.org/pdf/2609.24574.pdf): across 15 text-annotation tasks Jev's median accuracy is 0.610, ~11.6 macro-F1 behind the per-task-best LLM.
- [arXiv 2609.29769](https://arxiv.org/pdf/2609.29769): Jev often leads on binary criteria, trails on graded; 29–325× cheaper.

## 5. Conclusion: Jev's value in requirement gating

This measurement supports: **Jev fits the "layered routing layer" of a gate** — zero false-block, stable, far cheaper/faster, natively routable output; since v0.6.0 good items can auto-pass (red/yellow/green all present), with the costs being a 35% review rate and **redundancy-class bad items being missed just like an LLM (shared blind spot — catch it with ID-level dedup at the process layer)**. **Correct pattern = Jev layered routing (red block / green pass / yellow review) + humans reviewing yellow + process-level ID dedup.**

## 6. Reproduce

```bash
# Measured here: Jev
TYPESAFE_API_KEY=xx python benchmarks/benchmark.py --backend jev --runs 2

# Measured here: DeepSeek V4 Flash (peak price)
OPENAI_API_KEY=xx OPENAI_BASE_URL=https://api.deepseek.com/v1 \
  python benchmarks/benchmark.py --backend llm --model deepseek-flash \
  --runs 2 --input-price 0.3 --output-price 1.2 --out benchmarks/report_llm.json
```

> Full atomic question profile / thresholds: `src/jev_req_gate/profiles.py`; LLM prompt & judging: `benchmarks/benchmark.py`; raw detail (incl. per-run answers): `benchmarks/report_jev.json` / `benchmarks/report_llm.json`.
