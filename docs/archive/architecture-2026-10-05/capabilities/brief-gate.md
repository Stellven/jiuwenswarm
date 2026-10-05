---
id: cap.brief-gate
type: gate-profile
status: draft
version: 2
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [research.accept_brief]
consumes: [cc.type.evidence_bundle, cc.type.verifier_assessment]
depends_on: [../capsule/gate-host.md, README.md]
tags: [m1, gate, profile]
level: detail
prd: [3.2.7, 4.2.1, 4.2.2, 4.7.5]
---

# research.accept_brief.v1 Gate profile

PRD: 3.2.7, 4.2.1, 4.2.2, 4.7.5

> Answers: Which checks decide whether a Research Brief is accepted?

This is a pinned profile for the shared `research.verifier`, not a separate [capsule kind](../capsule/capsule.md#term-capsule-kind). The [Brief](../types/research-brief.md#term-research-brief) objective faithfully states the user's request without selecting a solution or expanding scope. [Tier 1](../verification.md#term-tier-1) verifies evidence spans, whitelisted defaults, paired metric fields and the generated schema.

The [Gate host](../capsule/gate-host.md) evaluates `gate(obs_ref) -> GateResult` (the [Binder](../system/planner.md#term-binder) pins the profile and builds the [evidence_bundle](../types/evidence-bundle.md#term-evidence-bundle)). The [frozen](../system/lifecycle.md#term-freeze) bound plan sets `gate_capsule_name: research.verifier` and this profile's immutable reference. Referee rubrics are trusted profile assets with exact hashes, independently authored from work-capsule prompts and excluded from [RSI](../rsi.md#term-rsi) mutation. Missing/unknown evidence [halts](../system/lifecycle.md#term-halt); failed persistence cannot release the next step. Output is a durable [Verification](../schemas/verification-record.md#term-verification), while the verifier itself returns [verifier_assessment](../types/verifier-assessment.md#term-verifier-assessment).

## Criteria

Tier 1 [checks](../capsule/fields.md#term-check) are in the paragraph above. The judged criterion and its rubric follow.

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
name: research.verifier
---
You judge a Research Brief: the contract every later research step reads. When a criterion looks at inputs, the
user's request is the intake's "prompt" in the bundle's inputs. Follow the judging instructions, and each
criterion's rubric.
```

## Existing code it touches

None directly. It [runs](../system/lifecycle.md#term-run) as a skill through the runner and M05.

## Tests

Three [test cases](../schemas/checks.md#term-test-case), one per pattern check. Each input is a bundle built from a requirement [capsule](../capsule/capsule.md#term-capability-capsule) fixture: a faithful Brief, and one whose objective names a solution. Each has `model_replies` and its expected assessment.

## Acceptance seeds

These rows seed the spec AC table. Each is derived from the behavior on this page; the coding spec sets final thresholds and [fixtures](../system/test-surfaces.md#term-fixture). Level is [BLOCK](../v-model.md#term-block), [BOUNDARY](../v-model.md#term-boundary) or [SYSTEM](../v-model.md#term-system).

| AC ID | Source | Observable criterion | Level |
|---|---|---|---|
| cap.brief-gate.AC-01 | G_req | A faithful Brief gives PASS on brief_objective_faithful with a recorded judge reply. | BLOCK |
| cap.brief-gate.AC-02 | G_req, US-04 | A Brief whose objective names a method, model or technique the prompt did not name gives FAIL with a quote from the prompt and one from the Brief. | BLOCK |
| cap.brief-gate.AC-03 | G_req | A prompt too vague to judge gives unknown, so the [Gate](../verification.md#term-gate) verdict is INCONCLUSIVE and the run halts. | BLOCK |
| cap.brief-gate.AC-04 | G_req | Tier 1 failures (evidence spans, whitelisted defaults, paired metric fields, generated schema) yield FAIL with 0 verifier calls. | BLOCK |
| cap.brief-gate.AC-05 | G_req | The Verification is committed before release; a failed save [releases](../system/lifecycle.md#term-release) nothing and the planner does not start. | BOUNDARY |
| cap.brief-gate.AC-06 | G_req, N_plan | After a failed Brief Gate, 0 planner requests are made. | SYSTEM |
