# Full-M1 design-depth experiment

**Evaluator guidance, not participant input.** The original pair is [full baseline](m1-full-baseline/README.md) and [original compact](m1-cut-down/README.md); both retain original input hashes. The [October 8 pair](m1-contract-review-2026-10-08/README.md) separately includes current contract/reading repairs. Assign a pair/version explicitly. The maintained design is [design package](../design-package/README.md). The [cut-down snapshot](m1-cut-down/README.md) covers the same full M1 scope with identical reference contracts, schemas, examples, CC field inventory, PRD and source decisions. The historical [very-condensed design](../very-condensed-design.md) remains unchanged and is not this experiment's input.

## Hypothesis and controlled difference

Can agents produce equally compatible, faithful specifications and implementations from less explanatory architecture? Both inputs retain the whole system. The immediate assignment can be one slice, but its result cannot establish sufficiency for all M1.

The cut-down input shortens component explanation, rationale, walkthroughs and native reuse discussion. It retains full research ports, data ownership, component obligations, stage exits, integration table and reference material. It includes two system/deployment diagrams instead of the full diagram collection. Legacy fragment aliases resolve to condensed topic views, not the original detailed sections. Historical sources remain pinned bibliography. Optional tooling internals are excluded from assignments in both conditions. Reference examples stay identical: the independent variable is explanatory depth and presentation, not contract content or example coverage.

[Comparison manifest](m1-comparison.json) records per-file identities, explanatory word counts, retained groups and omissions. Its full condition is the final frozen copy of the maintained package, not an earlier checkpoint. Do not silently use subsequently edited canonical files as the pinned full input.

## Before a paired trial

1. Verify both input snapshots with `validate_comparison.py`; copy each into a separate participant workspace and verify its file identities again. Full input must match the manifest. Use a clean identical implementation base and preserve unrelated work separately.
2. Give each participant only its assigned design snapshot, the identical PRD, repository coding rules and the exact same bounded assignment. Prohibit access to the other design, historical architecture and evaluator guidance. Remove cross-condition paths from the workspace; enforce isolation through the harness, not only a prompt.
3. Freeze the model/version/settings, tooling/dependency pins, credentials/capabilities, initial implementation tree, assignment, time/call budget, seed support and evaluator criteria. Record unavailable provider identities or seed control. Use equal limits, not an assumption of deterministic model output.
4. Predeclare which stage is measured: specification-only, implementation, or both. Both conditions use the same native specification workflow. Use separate fresh contexts; no shared summaries, memories or cross-condition reviewer feedback.
5. Pre-register evaluator cases and severity rules, including held-out cases not given to participants. Evaluate anonymized outputs against the same PRD/architecture intent and authoritative contracts. The evaluator may use the full design; participants may not consult it across conditions.

No participant trials are included in this documentation work.

## Assignment and evaluation

Use this common assignment template:

> Starting from the supplied implementation base, specify [and implement, if assigned] the named bounded M1 component or connected slice using the provided design snapshot, PRD and native repository workflow. Preserve its authority, shared fields, failure behavior and phase limits. Record material ambiguities, decisions, concrete checks and evidence. Consult no alternate architecture or historical design. Do not commit, push or broaden the assignment. A missing mandatory prerequisite is a blocker, not permission to fabricate successful evidence.

| Measure | What to record |
|---|---|
| Shared representation | Invented/missing/incompatible fields, ports, versions and record relationships; distinguish permitted private implementation choices |
| Responsibility and authority | Omitted consumers, checks, evidence, permission boundaries, routing/RSI/deployment connections; producer/verifier/gate confusion |
| Clarification | Material questions, wrong assumptions and changes required before compatible specification; identical answer policy in both conditions |
| Specification fidelity | Traceable obligations, usable intermediates, exclusions, architectural test intent and feasibility |
| Connected implementation | Real downstream use, rejected invalid output, persisted decisions, bounded effects and correct visible failures |
| Evidence quality | Exact tested candidate/configuration, commands, observed outcomes, missing prerequisites, stale or unrun cases |
| Efficiency | Input/output tokens where reliable, elapsed time, calls, retries, human correction effort and review findings |

Clarification answers must come from the frozen common requirements, be recorded, and be supplied equivalently if applicable. If an answer changes a material requirement, invalidate that paired comparison and revise both inputs before a new trial. Do not reward hallucinated certainty or penalize truthful blocked evidence as if it were an implementation failure.

A **critical** defect permits unauthorized release/effects, breaks a shared contract, fabricates scientific evidence, changes frozen criteria or defeats custody. A **material** defect prevents the declared consumer/phase obligation or requires architectural redesign. Presentation-only issues are **minor** when meaning and usability remain correct. Record each finding, affected obligation, evidence and repair effort; do not conceal critical errors inside a mean score.

## Scope of conclusions

Evaluate representative connected boundaries across M1: Intent/Requirements; planning/binding/execution; research artifacts and scientific-negative delivery; packaging/IPC/isolation and persistence; clients/inspection; library/RSI custody/activation; applicable Phase 3 integration. Pair each assignment independently. Use the same declared repetition count and alternate condition order to reduce sequencing effects. A single run is descriptive only; report model nondeterminism and sample size rather than claiming statistical equivalence.

Confounders include model/backend changes, unequal tool access, existing implementation scaffolding, leaked architecture, asymmetric human answers, differing budgets and evaluator familiarity. Log them and limit affected conclusions. The copied PRD and historical bibliography dominate total package size; report explanatory words separately from immutable source and contract bytes. Smaller input is not inherently better. Judge whether omitted explanation increases consequential ambiguity or implementation error.

## Maintenance

This is a pinned experiment, not a second maintained design. If canonical meaning changes, preserve these snapshots and create a new explicitly identified comparison; do not quietly update one condition. Existing coding identities and governance remain unchanged. Human design review and runtime acceptance are not established by this protocol or its mechanical checks.

## Prepared input measurements and checks

| Measure | Full | Cut-down |
|---|---:|---:|
| Explanatory words across the same 20 documents | 23,882 | 7,693 |
| Five-document immediate route words | 4,370 | 1,973 |
| Rendered maintained diagrams | 26 | 2 |
| Critical schemas plus shared definitions | 6 + 1 | 6 + 1 |
| Indexed example/context records | 34 | 34 |

Explanatory reduction: **67.79%**. Count whitespace-delimited words, including Mermaid text; exclude immutable source receipts, reference contracts/examples, glossary/index, governance/review and generated projections. All 65 reference/source/inventory files match bytes; eight core tables and two system/deployment diagram definitions match meaning. Portable validators, exact identities, reference/span/gate checks and six negative manifest/inventory checks pass on standalone copies. The full reviewer record is [coverage](../design-package/coverage.md#full-m1-design-integrity-review--october-7-2026).

Human review and paired agent trials have not been run. These are prepared inputs and documentation checks, not evidence that compression preserves implementation quality.

## Renamed full and compact delivery

The user-selected [full design-package](../design-package/README.md) and [design-package-compact](../design-package-compact/README.md) are matched sibling outputs. The [delivery receipt and checks](design-package-delivery-2026-10-08/README.md) record current schema/navigation/authority refinements. Earlier frozen inputs are unchanged; do not mix versions in trials.
