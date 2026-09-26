# Gating LLM-generated requirements with Jev — a field methodology (v2 · MECE 5 faces)

> For the AI era: after various LLMs bulk-produce requirement docs / user stories / acceptance criteria, use Jev (TypeSafe AI's System One model) as a
> **fast, programmable, confidence-bearing quality gate**.
>
> Companion tool: the `jev-req-gate` command in this repo (works out of the box; no-install entry `python reqgate.py`).
> This version reframes requirement quality judgment into 5 orthogonal faces using MECE (mutually exclusive, collectively exhaustive).

---

## 1. Core idea: judgment first, generation steps aside

Jev isn't a replacement for an LLM — it's the LLM's **quality checker**.

| Layer | What | Job |
|---|---|---|
| Generation (fast, hallucination-prone) | any LLM | bulk-produce requirement text |
| Judgment (fast, confident, no explanation) | **Jev** | make atomic quality judgments per requirement, return structured signals |
| Decision | your code | route by threshold: **PASS / REVIEW / BLOCK** |

**Principle**: Jev outputs *judgments*, not *advice*. It won't rewrite a requirement or explain its reasoning. Your job is to **bundle requirement + context into a state, decompose quality into atomic questions, and turn probabilities / scores / labels into routing signals**.

---

## 2. The MECE reframe: 5 orthogonal faces (why these 5)

The quality of "a requirement / a document" is exhaustively cut into **5 non-overlapping faces whose union is complete**:

| Face | Asks | Dimensions | Boundary |
|---|---|---|---|
| **Expression** | how it's worded | unambiguous, readable, atomic | wording |
| **Content** | what it says | complete, self-contained, terminology, quantifiable acceptance, implementation-free | information content |
| **Reality** | whether it holds | correct, feasible, necessary, traceable, faithful | truth / feasibility |
| **Relation** | how it relates to others | consistent, non-redundant, dependencies explicit | alignment with others |
| **Governance** | whether it follows the rules | template compliance, type/priority/risk labels, missing info | process/norm compliance |

> **AI is a cross-cutting axis, not a 6th face.** AI-generation pathologies (generic tone, intent drift, over-detail, redundancy, missing fields) land in the cells of the 5 faces, so locating them as "5 faces × AI failure points" is more precise and more mutually exclusive than making "AI disease" a separate group.
> Exhaustiveness basis: ISO/IEC/IEEE 29148 requirement quality attributes + classic requirements-engineering checklists + AI-scenario extensions.

---

## 3. The question profile: 22 atomic questions (methodology core)

Design principles (from the official TypeSafe docs):

1. **Each question is atomic, single-dimensional.** "Is it clear *and* self-contained" must be split into two.
2. **Noul asks only yes/no propositions**, worded so that *high = positive meaning*; avoid reverse phrasing.
3. **Score defines its scale with level descriptions (a criteria array)**, so the model lands on the scale you wrote.
4. **Choice criteria is a key → meaning map**; keys are labels you can write back into your system.
5. Noul `direction`: `positive` (higher = healthier) / `negative` (higher = more problematic).

### Expression (3 · Score)

| key | instructions | direction / scale |
|---|---|---|
| `clarity` | degree of unambiguous wording | 1 = vague / self-contradictory … 5 = clear, single-meaning |
| `readability` | degree a non-technical reader can follow | 1 = jargon/abstract … 5 = plain to ordinary readers |
| `atomicity` | degree the item focuses on a single responsibility | 1 = mixes several … 5 = fully single |

### Content (6)

| key | primitive | direction | instructions |
|---|---|---|---|
| `completeness` | Score | — | how complete the info is (1 = much missing … 5 = self-contained incl. boundaries & exceptions) |
| `self_contained` | Noul | positive | understandable & verifiable within the document, no out-of-document implicit knowledge |
| `terminology_defined` | Noul | positive | key terms defined within the document |
| `acceptance_quantifiable` | Noul | positive | acceptance criteria are quantifiable |
| `implementation_free` | Noul | negative | treats an implementation solution/detail as the requirement (requirements-vs-solution confusion) |
| `missing_info` | Choice | — | which info is missing: prerequisite / dependency / boundary / terminology / acceptance / none |

### Reality (5 · Noul, all positive) ★ the most important addition this version

| key | direction | instructions |
|---|---|---|
| `correct` | positive | consistent with business goals / true intent — a correct requirement |
| `feasible` | positive | achievable under current technical / resource constraints |
| `necessary` | positive | actually needed for this delivery (not redundant / decorative) |
| `traceable` | positive | traceable to a clear source (user ask / business goal / upstream requirement) |
| `fidelity` | positive | faithful to the original input intent, not drifted/diverged by AI expansion |

> These 5 target the biggest AI pitfall: generating requirements that are **syntactically perfect but simply don't hold in this project**.

### Relation (4 · Noul)

| key | direction | instructions |
|---|---|---|
| `consistent_internal` | positive | internally consistent (title / description / acceptance), no self-contradiction |
| `contradicts_siblings` | negative | contradicts other items in the document |
| `non_redundant` | positive | doesn't duplicate existing requirements |
| `dependencies_declared` | positive | preconditions / dependencies are explicitly declared |

### Governance (4)

| key | primitive | direction | instructions |
|---|---|---|---|
| `conforms_template` | Noul | positive | conforms to the team's requirement template / required fields |
| `req_type` | Choice | — | type: feature/nfr/constraint/assumption |
| `priority` | Choice | — | must/should/could/wont |
| `risk` | Choice | — | high/mid/low |

**Total: Score 4 + Noul 14 + Choice 4 = 22 atomic questions.**

---

## 4. State bundling: from "one text" to "one package"

Cross-item contradiction, context fit, and implicit dependencies all depend on comparison, so the state must carry references:

```
state = {
  "requirement":          "the item under review",
  "project_context":      "project background/constraints/stack/business context",  ← reality (correct/feasible) reference
  "existing_requirements": ["existing req 1", "existing req 2", ...],                ← relation (non-redundancy) reference
  "document":             ["doc item A", "B", "C", ...],                            ← relation (contradiction) reference
  "archived":             "previous-version archived requirements (optional)"
}
```

All atomic questions are evaluated once, in parallel (Jev's questions compute in parallel; adding questions barely adds latency).

---

## 5. Thresholds & routing (5-face synthesis, calibrated against real Jev output)

For each requirement, compute the Score mean `Q_score` (Expression + Content), then combine the faces' Nouls. **Blocking only looks at the 5 signals Jev is most reliable on:**

```
RED  block (any hit):
  reality fatality (whitelist positive < 0.3): self_contained / correct / feasible / necessary
  relation fatality:                            contradicts_siblings > 0.7
  quality floor:                                Q_score < 1.0 (only fires when truly awful)

YELLOW  review (any hit, not red):
  quality hint:  Q_score < 2.2 (Jev scores conservatively; treat as reference)
  risk hint:     risk == "high" (tends to inflate in whole-document mode; hint only)
  other dims:    any positive Noul < 0.5 (e.g. terminology_defined / conforms_template)
                 or negative Noul > 0.5 (e.g. implementation_free)
  uncertainty:   several Nouls in 0.25~0.75 → aggregate hint → human review
  confidence:    any Score confidence < 0.6

GREEN  pass: everything else (key signals healthy + no contradiction + no risk signal)
```

> **Why calibrated this way**: real Jev output on Chinese requirements differs from intuition —
> quality scores (clarity/completeness etc.) are generally very conservative (sound requirements only score ~1.3–2.8), so they're demoted to hints, not block signals;
> `terminology_defined` runs naturally low for Chinese / single items and doesn't participate in blocking;
> `risk` tends to inflate once the whole document is passed, so it's hint-only;
> whereas `self_contained / correct / feasible / necessary / contradicts_siblings` are Jev's most reliable signals and drive blocking.

### 5.5 Real calibration log (2026-09, measured; Chinese requirements + e-commerce project context)

Ran `document_demo.json` (5 items: a contradictory pair, one vague, one infeasible) through real Jev:

| Requirement | Key signals | Verdict |
|---|---|---|
| Block deleting referenced products | contradicts_siblings=0.75 | RED (contradicts next item) |
| Allow force-deleting referenced products | contradicts=0.86, correct=0.17 | RED |
| "Improve user experience" (vague) | correct=0.21, feasible=0.23, self_contained=0.15 | RED |
| Payment gateway settlement (sound) | quality 1.48, mostly middle-band dims | YELLOW (not over-blocked) |
| Pull third-party data real-time within 50ms (infeasible) | feasible=0.06, correct=0.08 | RED |

**Conclusion**: Jev is reliable on the reality layer (correct/feasible/necessary/self-contained) and cross-item contradiction, usable as hard block signals; quality score / terminology / risk should be demoted per the above.

**Reproduction note**: Jev is a calibrated-probability model; single values jitter across calls (contradiction values ~0.70–0.87), so leave headroom in thresholds.

### Threshold tuning principles (from the official Noul docs)

* **0.5**: use when the cost of yes/no is symmetric.
* **Raise**: when false-positive is expensive (over-blocking a good requirement → blocks delivery) → raise the red threshold.
* **Lower**: when a miss is expensive (letting a vague / infeasible requirement through → blows up at release) → lower the review threshold, widen the middle band.
* **The middle band is always for humans**: don't hard-resolve 0.4~0.6 uncertainty in code — route it to a person.

---

## 6. Going from 0 to production

1. **Install the SDK**: `pip install typesafe-sdk` (Python ≥ 3.10); get `TYPESAFE_API_KEY` from the TypeSafe dashboard.
2. **Define the profile**: start from this section's 22 questions; add 2–3 team-specific ones (e.g. "depends on an unshipped interface" → a `feasible` refinement).
3. **Insert the gate**: add a gate node in the pipeline before requirements enter review/development; feed each LLM-produced requirement + project_context + existing set to `jev-req-gate`.
4. **Set thresholds**: first run the default thresholds over a batch of historical requirements to see the misjudgment rate, then tune per §5.
5. **Human closed loop**: route yellow items to the review board with reasons; periodically recalibrate thresholds from human verdicts.
6. **Write back labels**: write Choice results (type/priority/risk) + quality scores back into the requirement tracker to build a quantifiable quality profile.

---

## 7. Boundaries & notes

* **Jev accepts text state**: strings, JSON, objects/arrays all fine; no images / audio / video yet.
* **It doesn't explain**: don't ask "why is it ambiguous" — convert ambiguity/contradiction/drift into Noul probabilities + human review.
* **Calibration ≠ per-item certainty**: Jev probabilities are population-calibrated, not guaranteed per item; therefore the middle band must stay with humans.
* **Question quality sets the ceiling**: the clearer the scale, criteria, and phrasing, the better the judgment; try with and without criteria.
* **Reality layer weighs most**: the most dangerous AI requirement isn't "poorly written" but "well-written yet doesn't hold" — watch the 5 Reality Nouls first.

---

## 8. Official resources

* Quick start / API reference: <https://docs.typesafe.ai/introduction/quickstart>
* Primitive docs: <https://docs.typesafe.ai/primitives/noul> (and choice / score)
* System One concept: <https://docs.typesafe.ai/concepts/system-one>
* Agent Skill: `npx skills add typesafe-ai/skills --skill typesafe-ai`

---

*The companion `jev-req-gate` tool implements this methodology: 5 faces × 22 atomic questions, state bundling, integrated routing, and report output; `--demo` mode shows the full routing logic with no API key.*
