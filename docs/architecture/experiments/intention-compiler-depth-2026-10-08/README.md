# Intention Compiler: full/cut-detail × Spec Kit/direct

**Evaluator material: keep outside participant workspaces.** Four architecture inputs are delivered; no implementation trial has run and no winner is assumed.

| Architecture | Coding method | Branch |
|---|---|---|
| Full | Spec Kit | `ai4r_test_with_spec_kit` |
| Full | Direct | `ai4r_test_without_spec_kit` |
| Cut-detail | Spec Kit | `ai4r_test_with_spec_kit_cut_detail` |
| Cut-detail | Direct | `ai4r_test_without_spec_kit_cut_detail` |

## Participant locations

All four use the same paths relative to `jiuwenswarm`:

- Main: `docs/code/Missions/M0/source/Architecture_main_body/Architecture_main_body.md`.
- Context: `docs/code/Missions/M0/source/Architecture_context/Architecture_context.md`.
- Supporting knowledge: `docs/code/Missions/M0/source/Architecture_context/design-package/`.
- Verification route: `docs/code/Missions/M0/source/Verification/README.md`.

Main assigns the complete Intention Compiler and required foundations through accepted Research Brief or attributable halt. Context links fields, contracts, examples and explanations. Intent IR alone is incomplete. The PRD remains outside the architecture package. The prompt and usage template belong to the coding experiment owner; this delivery does not prescribe a replacement prompt.

[Delivery receipts](deliveries.json) pin commits and files. Both depths retain identical contracts, examples, decisions, scope and build entrypoints: 177 shared files match exactly. Full has 255 files/26 views; cut-detail has 223 files/10 views. Across the same 20 explanatory documents, full has 25,066 words versus 15,961: **36.32% less explanation**, not a measured token saving. Maintained originals and earlier frozen experiments remain unchanged.

## Fair enough to answer both questions

1. Use fresh isolated agent contexts with the same starting scaffolding/tooling, model/settings, resources, endpoint, Docker environment and equal time/call limits. Branch application histories differ: do not evaluate their existing implementations. Default common tooling-source pin is `5839177533f6266871f3c8ab96eba3425f7a10e6`. Existing application implementations, alternate architecture and peer outputs must be unavailable to participants.
2. The prompt owner substitutes these identical file locations and selects Spec Kit versus direct coding in the appropriate cells. Keep the assignment, verification instructions and accounting rules otherwise matched. A copied no-Spec-Kit directive in a Spec Kit cell invalidates that method comparison; the owner must select the actual workflow before running. Use the same installed tools/templates; direct cells override any repository instruction mandating Spec Kit.
3. Randomize/counterbalance order; never transfer fixes, summaries or assistance between cells. Blind assessors to condition labels. Record clarifications, interventions and uncontrolled versions/seeds. A changed common requirement invalidates the block. Repeat fresh four-cell blocks if resources permit; one block is descriptive, not statistical proof.
4. Freeze candidates before independent assessment using the same [criteria](criteria.md), [40 cases](cases.csv), [review questions](review.md), [fixtures](fixtures/actionable.txt) and [result template](case-results.template.csv). Preserve exact commands, inputs, candidate identity, expected/observed results and evidence. Participant tests and evaluator challenges are distinct.

Require positive configured-model Brief completion and mandatory foundations; a mock, Intent-only result, passing JSON or valid halt alone is insufficient. Critical authority/integrity failures disqualify acceptance. Report major defects, false acceptance and false refusal separately; group failures by root defect. BLOCKED, NOT_RUN and stale evidence are not passes. Fix common setup equally. Compare cost/time/effort only alongside comparable correctness; report tradeoffs or no clear winner.

Compare full versus cut-detail **within each method**, and Spec Kit versus direct **within each depth**. Report interactions: a diagonal comparison cannot isolate either effect. This tests the compiler and its foundations, not full-M1 sufficiency.

## Measurement and checks

Use [the manifest](trial-manifest.template.json). Capture all task calls from first reading through final response, including tests, fixes and retries. Attribute calls once to Preparation or Implementation; Spec Kit artifact generation belongs to Preparation. Compare End-to-End totals so preparation is not hidden. Direct preparation is zero only after verified absence. Reading is attributed to its actual phase consistently. Evaluator/harness calls and architecture authoring are outside participant usage.

Input includes cached input; output includes reasoning subsets. Record provider/model, call count, measurement source, currency and actual billed cost. Inaccessible usage/cost is Unavailable, not estimated exact usage. Close telemetry after the final response. Track time to first accepted Brief, final completion, interventions and correction cycles. Keep separately measured later repairs distinct from original results.

Run `python validate_inputs.py` to verify the committed deliveries, exported portable packages, contracts/examples, entrypoint links and case templates. Documentation checks establish consistent inputs, not runtime behavior. Participant trials and human domain review remain unperformed.
