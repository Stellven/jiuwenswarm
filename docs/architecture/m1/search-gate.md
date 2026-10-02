---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt, ../capsule/gate-capsules.md, search-capsule.md]
provides: [research.accept_ideas]
consumes: [cc.gate_capsule_pattern, prompt.gate_judging, cc.type.evidence_bundle, cc.type.verifier_assessment]
depends_on: [../capsule/gate-capsules.md, pipeline.md]
tags: [m1, gate, capsule]
---

> **Draft: reopened for changed shared contracts.** The gate capsule for step `search`: PRD 3.3.6's handoff to the 4.2 Evaluator Gate before Screening (3.4). It follows [the gate capsule pattern](../capsule/gate-capsules.md); only what differs is written here.

# `search_gate`: `research.accept_ideas`

## What it does

It assesses the candidate ideas against two judged step checks:
- **`ideas_grounded`:** each idea is supported by the passages it cites, and is not speculative (PRD 3.3.5's blacklist);
- **`ideas_answer_brief`:** each idea addresses the Brief's objective and stays within its scope.

The deterministic checks (citations resolve, local passages verbatim, Top-K, one to three ideas, size) run in Tier 1. This is PRD 3.3.6's "schema and token limits". If the ideas fail, the run halts before Screening.

## Run-plan entry

The gate slot of step `search` on [the M1 pipeline](pipeline.md): `gate_capsule_name: research.accept_ideas`, with the two step checks above, defined in [the plan](pipeline.md#the-plan-as-recorded).

## Declaration (`capsule.json`)

As [the intent gate](intent-gate.md#declaration-capsulejson), with these differences:

| Field | Value |
|---|---|
| `identity.name` | `research.accept_ideas` |
| `identity.body` | `SKILL.md`, then `rubrics/ideas_grounded.md` and `rubrics/ideas_answer_brief.md` |
| `identity.summary` | `Assess a set of candidate research ideas against the evidence they cite and the brief they answer, per the given criteria and rubrics, answering each criterion with a rationale and verbatim quotes.` |
| `ports.inputs[0].description` | `The idea set, the Brief and intake, and the criteria to judge by.` |

## `rubrics/ideas_grounded.md`

```text
Criterion: ideas_grounded.

For each idea, read the chunks its cited_chunk_ids name, in the idea set's groups.

Pass when every idea's summary and mechanism follow from its cited chunks: each claim the idea makes
about what works, or why, is stated or directly implied by a cited chunk.

Fail when any idea claims something no cited chunk supports, or proposes a speculative or contrarian
direction the chunks do not support. Quote the idea's claim, and say which cited chunks fail to support it.

Unknown when the cited chunks are too short to tell.
```

## `rubrics/ideas_answer_brief.md`

```text
Criterion: ideas_answer_brief.

The Research Brief is the research_brief in the bundle's inputs.

Pass when every idea would, if it worked, advance the Brief's objective, and needs nothing the Brief
puts out of scope (out_of_scope_items) or rules out by its constraints.

Fail when any idea answers a different problem, or needs something out of scope or against a constraint.
Quote the idea and the part of the Brief it conflicts with.

Unknown when the Brief's objective is too vague to tell.
```

## `SKILL.md`

```text
---
name: research.accept_ideas
---
You judge a set of candidate research ideas, with the evidence they cite. When a criterion looks at
inputs, the Research Brief is in the bundle's inputs. Follow the judging instructions, and each
criterion's rubric.
```

## Existing code it touches

None directly. It runs as a skill through the runner and M05.

## Tests

Three test cases, one per pattern check. Their bundles are built from the search capsule's fixtures: one well-grounded idea set, and one whose idea claims more than its chunk says. Each carries `model_replies` and its expected assessment.
