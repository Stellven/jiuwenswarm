---
id: cap.hypothesis
type: capability
status: draft
version: 1
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [research.form_hypothesis]
consumes: [cc.type.opportunity_card, cc.type.research_brief, cc.type.intake, cc.type.hypothesis_blueprint]
depends_on: [README.md, ../types/hypothesis-blueprint.md, op-codesearch.md]
tags: [m1, contract]
level: detail
prd: [3.5.1, 3.5.2, 3.5.3, 3.5.4, 3.5.5]
---

Missing methods or resources block only the affected experiments. The frozen PRD determines preregistration.

# `hypothesis_capsule`: `research.form_hypothesis` (PRD 3.5)

PRD: 3.5.1, 3.5.2, 3.5.3, 3.5.4, 3.5.5

> Answers: How does the hypothesis capsule freeze one testable claim, with thresholds, before any code is written?

## What it does

It turns the chosen opportunity into one testable claim: what changes, what is measured, the baseline, the locked dataset, the mechanism (to a file and line when it can), and the pre-registered thresholds, [frozen](../system/lifecycle.md#term-freeze) before any code is written (3.5.1 to 3.5.5).

## Where it sits

| | |
|---|---|
| <a id="term-flow-position"></a>**Flow position** | Planned node in the research chain template (see [capabilities](README.md)); the planner binds its inputs when it composes the DAG. |
| <a id="term-work-capsule"></a>**Work capsule** | `research.form_hypothesis`, a `tool` with one bounded model turn that pins `op.codesearch` and uses ordinary resource-freezing services |
| <a id="term-inputs"></a>**Inputs** | [`opportunity_card`](../types/opportunity-card.md) from `screening`; [`research_brief`](../types/research-brief.md); [`intake`](../types/intake.md) (project_asset and validation_data resources, not text documents) |
| <a id="term-outputs"></a>**Outputs** | [`hypothesis_blueprint`](../types/hypothesis-blueprint.md) |
| <a id="term-operators-it-pins"></a>**Operators it pins** | [`op.codesearch`](op-codesearch.md), to locate the mechanism; [`freeze_resources`](measurement-protocol.md#frozen-methods), to publish immutable resource/config snapshots |
| <a id="term-effect-class"></a>**Effect class** | `idempotent`, snapshot publication only under `fs:workspace/.cc/snapshots/*`; broker narrows this to the current run |
| <a id="term-gate-profile"></a>**Gate profile** | shared `research.verifier` + `research.accept_hypothesis.v1`: judged criteria, intended: the claim is falsifiable by the thresholds, the dataset is ingested and not synthesized, the Brief target is preserved and claim/falsification predicates are separately pre-registered |

## Known from the PRD

- One claim, one path (3.5.1).
- The claim and the falsification threshold are two numbers (3.5.1, 3.5.4).
- No synthetic data (3.5.2).
- The blueprint is immutable downstream (3.5.5).

## Assumptions

- Each mandatory [Brief](../types/research-brief.md#term-research-brief) metric has a blueprint entry referring to its id, with acceptance target preserved separately from claim and falsification predicates (frozen PRD 3.5.4).
- A deterministic [Tier 1](../verification.md#term-tier-1) check: every mandatory Brief metric is in the blueprint, at least as strict.
- Each metric declares its direction, unit (absolute, relative or points), success target, falsification threshold and any guard, and the blueprint declares the repeat count (frozen before results).
- The dataset is a supplied `validation_data` resource, or a declared, pre-installed standard one (3.5.2, the intake resource contract).

## Replacement boundary

Methods/configuration use versioned trusted [adapters](../system/integration.md#term-adapter); resource changes require a new [snapshot](../capsule/library.md#term-library-snapshot) and run. middle_zone_classification defaults to INCONCLUSIVE and is frozen before POC generation. This is a sourced default.

## Coding handoff contracts

Code/process placement is [modules](../system/modules.md). Shared request, deadline, duplicate and cancellation semantics are [runner](../capsule/runner.md) and [lifecycle](../system/lifecycle.md); storage is the home of all publication and recovery. This stage emits no successful output for missing required inputs, mismatched pins, invalid schema or failed mandatory capture. The supervisor is the home of halt and explicit human restart. Each attempt retains its evidence under the same run identity; changed frozen inputs require a new run.

The output type page defines fields and cross-input [checks](../capsule/fields.md#term-check). [Measurement protocol](measurement-protocol.md) defines methods, samples, transforms and compiler evidence. [Research gates](research-gates.md) defines this stage's acceptance API and criteria. No local copy of a shared schema is authoritative. [Verification](../system/test-surfaces.md) gives independently callable entry points, expected observations and injectable failures; runtime acceptance results belong to coding work.

Freeze resource snapshots and method/config hashes before returning the blueprint; the [Gate](../verification.md#term-gate) must confirm this publication before POC is invoked. Missing baseline/dataset/method/hardware [blocks](../system/modules.md#term-block) scientific readiness here; it does not [turn](../system/model-bridge.md#term-model-turn) initial raw intake qualification into a dataset requirement. CodeSearch works on that snapshot only. The model proposes one claim; deterministic code validates all predicates, mandatory Brief metrics and repeat/seed settings. There is no code generation at this stage.

## Declaration

No [Declaration](../capsule/fields.md#term-declaration) JSON is abridged on this page. The Work [capsule](../capsule/capsule.md#term-capability-capsule), Operators and Effect class rows in Where it sits state the contract; the Declaration format is in [capsule fields](../capsule/fields.md).

## Checks

The deterministic Tier 1 check is stated in Assumptions above (every mandatory Brief metric is in the blueprint, at least as strict). The Gate checks are in the `research.accept_hypothesis` row of [research gates](research-gates.md).

## Tests

Independently callable entry points, expected observations and injectable failures: [test surfaces](../system/test-surfaces.md). Runtime acceptance results belong to coding work.

## Acceptance seeds

These rows seed the spec AC table. Each is derived from the behavior on this page; the coding spec sets final thresholds and [fixtures](../system/test-surfaces.md#term-fixture). Level is BLOCK, [BOUNDARY](../v-model.md#term-boundary) or [SYSTEM](../v-model.md#term-system).

| AC ID | Source | Observable criterion | Level |
|---|---|---|---|
| cap.hypothesis.AC-01 | PRD 3.5.1 | The blueprint holds one claim with success and falsification thresholds as two separate predicates. | BLOCK |
| cap.hypothesis.AC-02 | PRD 3.5.4 | Every mandatory Brief metric appears in the blueprint with a threshold at least as strict as the Brief target (deterministic Tier 1 check). | BLOCK |
| cap.hypothesis.AC-03 | PRD 3.5.2 | A dataset that is not a supplied validation_data resource or a declared pre-installed standard set is rejected; no synthetic data is accepted. | BLOCK |
| cap.hypothesis.AC-04 | PRD 3.5.5 | Resource snapshots and method/config hashes are published in one [batch](../system/storage.md#term-commit-batch) before the blueprint is returned; a missing resource rejects before POC generation. | BOUNDARY |
| cap.hypothesis.AC-05 | PRD 3.5.4 | middle_zone_classification defaults to INCONCLUSIVE and is frozen before POC generation; CONDITIONALLY_ACCEPTABLE appears only if preregistered. | BLOCK |
| cap.hypothesis.AC-06 | N_node | Each metric declares direction, unit, target, falsification threshold, guard and repeat count; a missing field rejects the output. | BLOCK |
| cap.hypothesis.AC-07 | N_node | op.codesearch returning empty hits records an unresolved mechanism limitation and no fabricated code location. | BOUNDARY |
| cap.hypothesis.AC-08 | G_node | A blueprint whose claim is not falsifiable by its thresholds fails the hypothesis Gate and no POC call starts. | SYSTEM |
