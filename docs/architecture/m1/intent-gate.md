---
type: design
status: past
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-02.txt, ../capsule/gate-capsules.md, intent-capsule.md]
provides: [research.accept_intent]
consumes: [cc.gate_capsule_pattern, prompt.gate_judging, cc.type.evidence_bundle, cc.type.verifier_assessment]
depends_on: [../capsule/gate-capsules.md, intent-capsule.md, pipeline.md]
tags: [m1, gate, capsule]
---

> **Draft: reopened for changed shared contracts.** The gate capsule for step `intent`. It follows [the gate capsule pattern](../capsule/gate-capsules.md); only what differs is written here.

# Historical `intent_gate`: `research.accept_intent`

## What it does

It assesses whether the IntentIR from `research.compile_intent` is faithful to its bound `source_text`. It is also where PRD 3.1.5's deferred sense check is met: text too vague to judge yields `unknown`, blocks the step, and enters human triage. The IntentIR must add nothing and omit nothing central. The deterministic half is the intent capsule's own checks, which the Gate host runs first.

## Run-plan entry

The gate slot of step `intent` on [the M1 pipeline](pipeline.md): `gate_capsule_name: research.accept_intent`, with one step check, `intent_fidelity`, given in full on [the intent capsule](intent-capsule.md#gate).

## Declaration (`capsule.json`)

```json
{
  "schema_version": "cc.declaration.v1",
  "identity": {
    "name": "research.accept_intent",
    "kind": "skill",
    "body": [
      {"path": "SKILL.md", "sha256": "<author kit>"},
      {"path": "rubrics/intent_fidelity.md", "sha256": "<author kit>"}
    ],
    "summary": "Assess an IntentIR against the prompt it was compiled from, per the given criteria and rubrics, answering each criterion with a rationale and verbatim quotes."
  },
  "ports": {
    "inputs": [{"name": "evidence_bundle", "type": "evidence_bundle", "required": true,
                "description": "The IntentIR, its intake, and the criteria to judge by."}],
    "outputs": [{"name": "verifier_assessment", "type": "verifier_assessment", "check_id": "answers_every_criterion",
                 "description": "One answer per criterion."}]
  },
  "needs": {
    "when": [],
    "external": [{"ref": "prompt.gate_judging", "decl_hash": "<admitted>", "purpose": "the shared judging instructions"}],
    "network": "none", "human_interaction": "none", "resources": {"timeout_s": 120}
  },
  "changes": {"effect_class": "pure", "effects": [], "state_kind": "none"},
  "guarantees": {"checks": [
    {"id": "answers_every_criterion", "anchor": "deterministic", "target": "ports.outputs.verifier_assessment",
     "over": "inputs_and_outputs", "applies_at": "both",
     "runner": {"ref": "checks/gate_checks.py:answers_every_criterion", "sha256": "<author kit>"},
     "description": "The assessment answers every criterion of the bundle exactly once, in the bundle's order, and no other.",
     "author": "muk"},
    {"id": "quotes_from_bundle", "anchor": "deterministic", "target": "ports.outputs.verifier_assessment",
     "over": "inputs_and_outputs", "applies_at": "both",
     "runner": {"ref": "checks/gate_checks.py:quotes_from_bundle", "sha256": "<author kit>"},
     "description": "Every pass or fail has at least one quote, and every quote appears verbatim in the bundle's inputs or outputs as the skill prompt renders them, after collapsing every run of whitespace to one space in both.",
     "author": "muk"},
    {"id": "assessment_matches_expected", "anchor": "reference", "target": "ports.outputs.verifier_assessment",
     "over": "outputs", "applies_at": "admission",
     "runner": {"ref": "checks/gate_checks.py:assessment_matches_expected", "sha256": "<author kit>"},
     "description": "On a test case, each criterion's result equals the expected result for that check_id.",
     "author": "muk"}
  ]},
  "evolution": {"rsi": "none"}
}
```

The three checks are [the pattern's](../capsule/gate-capsules.md#the-three-checks-every-gate-capsule-carries); `checks/gate_checks.py` is byte-identical in every gate capsule. Add `{"path": "checks/gate_checks.py", ...}` to the Candidate's files, as every check runner file ([open issues](../open-issues.md) 2).

## `SKILL.md`

```text
---
name: research.accept_intent
---
You judge an IntentIR: a structured reading of a user's research request. When a criterion looks at
inputs, the request is `source_text.text` in the bundle's inputs. Follow the judging instructions, and
each criterion's rubric.
```

No `model` key: the gate uses the runtime's default model, the author's choice.

## `rubrics/intent_fidelity.md`

```text
Criterion: intent_fidelity.

Pass when both hold:
- Every goal, outcome and constraint in the IntentIR restates something the prompt says, and its
  source_spans point at that text.
- Every request the prompt makes (what to find, what to make, what to do, and every "must" or "must not")
  appears as a goal, an outcome or a constraint.

Fail when an item states something the prompt does not say, or a request in the prompt is missing.
Quote the prompt's words, and the item, that show it.

Unknown when the prompt is too vague to tell what it asks.

Do not judge ambiguities, conflicts or unknowns: they record what is open, and may be empty.
```

## Existing code it touches

None directly. It runs as a skill through the runner and M05 ([integration](../system/integration.md#codex-the-model-for-m05)).

## Tests

Three test cases, one per pattern check. Each input is an `evidence_bundle` built from the intent capsule's fixtures: a faithful IntentIR, one with a constraint removed, and one for the third check that reuses either. Each has `model_replies` with a recorded judge reply, and its expected `verifier_assessment`: `pass` for a faithful IntentIR, `fail` for a broken one.

## Open

- The rubric's line between "restates" and "infers" is a judgement call. Calibration (a `verifier_audit` Finding on a labelled set) is unchecked at M1, so every result carries `judge_unmeasured`.
