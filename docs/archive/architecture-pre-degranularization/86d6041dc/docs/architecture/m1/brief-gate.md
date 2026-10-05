---
type: design
status: draft
version: 2
owner: muk
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [research.accept_brief]
consumes: [cc.type.evidence_bundle, cc.type.verifier_assessment]
depends_on: [../capsule/gate-host.md, pipeline.md]
tags: [m1, gate, profile]
---

# research.accept_brief.v1 Gate profile

This is a pinned profile for the shared `research.verifier`, not a separate capsule Declaration. The Brief objective faithfully states the user's request without selecting a solution or expanding scope. Tier 1 verifies evidence spans, whitelisted defaults, paired metric fields and the generated schema.

The owning [Gate host](../capsule/gate-host.md) evaluates `evaluate(evidence_bundle_ref, gate_profile_ref, request_id) -> verification_ref`. The run plan sets `gate_capsule_name: research.verifier` and this profile's immutable reference. Referee rubrics are trusted profile assets with exact hashes, independently authored from work-capsule prompts and excluded from RSI mutation. Missing/unknown evidence halts; failed persistence cannot release the next step. Output is a durable Verification, while the verifier itself returns verifier_assessment.

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

None directly. It runs as a skill through the runner and M05.

## Tests

Three test cases, one per pattern check. Each input is a bundle built from a requirement capsule fixture: a faithful Brief, and one whose objective names a solution. Each has `model_replies` and its expected assessment.
