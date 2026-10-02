---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt, ../capsule/gate-capsules.md, requirement-capsule.md]
provides: [research.accept_brief]
consumes: [cc.gate_capsule_pattern, prompt.gate_judging, cc.type.evidence_bundle, cc.type.verifier_assessment]
depends_on: [../capsule/gate-capsules.md, requirement-capsule.md, pipeline.md]
tags: [m1, gate, capsule]
---

> **Draft: reopened for changed shared contracts.** The gate capsule for step `requirement`: PRD 3.2.7's handoff to the 4.2 Evaluator Gate before search (3.3). It follows [the gate capsule pattern](../capsule/gate-capsules.md); only what differs is written here.

# `brief_gate`: `research.accept_brief`

## What it does

It assesses the Research Brief against the step's judged check, `brief_objective_faithful`: the objective says what the user asked for, chooses no solution, and the scope adds nothing the request did not say. The deterministic checks (evidence grounded, defaults, metrics) run in Tier 1. If the Brief fails, the run halts before search.

## Run-plan entry

The gate slot of step `requirement` on [the M1 pipeline](pipeline.md): `gate_capsule_name: research.accept_brief`, with one step check, `brief_objective_faithful`, defined in [the plan](pipeline.md#the-plan-as-recorded).

## Declaration (`capsule.json`)

As [the intent gate](intent-gate.md#declaration-capsulejson), with these differences:

| Field | Value |
|---|---|
| `identity.name` | `research.accept_brief` |
| `identity.body` | `SKILL.md`, then `rubrics/brief_objective_faithful.md` |
| `identity.summary` | `Assess a Research Brief against the request it was compiled from, per the given criteria and rubrics, answering each criterion with a rationale and verbatim quotes.` |
| `ports.inputs[0].description` | `The Research Brief, its intake, and the criteria to judge by.` |

## `rubrics/brief_objective_faithful.md`

```text
Criterion: brief_objective_faithful.

Pass when all hold:
- The objective states the problem the prompt asks to solve, in the prompt's own terms.
- The objective names no method, model, library or technique the prompt did not name.
- Every in_scope_items entry is something the prompt asks to cover.

Fail when the objective chooses a solution, changes what is asked, or a scope item adds work the prompt
does not ask for. Quote the prompt's words and the Brief's that show it.

Unknown when the prompt is too vague to tell what the objective should be.
```

## `SKILL.md`

```text
---
name: research.accept_brief
---
You judge a Research Brief: the contract every later research step reads. When a criterion looks at inputs, the
user's request is the intake's "prompt" in the bundle's inputs. Follow the judging instructions, and each
criterion's rubric.
```

## Existing code it touches

None directly. It runs as a skill through the runner and M05.

## Tests

Three test cases, one per pattern check. Each input is a bundle built from a requirement capsule fixture: a faithful Brief, and one whose objective names a solution. Each has `model_replies` and its expected assessment.
