---
id: cap.op-assess-dependency
type: module
status: draft
version: 1
sources: [../types/dependency-requirement.md, ../types/dependency-assessment.md, ../schemas/policy.md]
provides: [op.assess_dependency]
consumes: [cc.type.dependency_requirement]
depends_on: [../types/dependency-requirement.md, ../types/dependency-assessment.md, ../schemas/policy.md]
tags: [module, m1, operator, screening]
level: detail
prd: [3.4.6]
---

# Ordinary module contract: `op.assess_dependency`: deterministic dependency policy

PRD: 3.4.6

> Answers: How does a dependency requirement become a compatible, conflict or unknown assessment under the frozen registry?

## What it does

> Module API names below retain their op.* namespace for callable interfaces. They are not separately admitted [capsule](../capsule/capsule.md#term-capability-capsule) identities; code is pinned through its work capability/profile. Screening [RSI](../rsi.md#term-rsi) evaluates helper candidates offline and activation replaces the capsule version, preserving runtime ranking [checks](../capsule/fields.md#term-check).

A pure [operator](README.md#term-operator) that maps one [`dependency_requirement`](../types/dependency-requirement.md) to one [`dependency_assessment`](../types/dependency-assessment.md) under the [frozen](../system/lifecycle.md#term-freeze) policy registry. The caller supplies no registry path or policy override; its [Binding](../schemas/binding.md#term-binding) pins the registry hash.

Screening's author kit materializes those exact immutable registry bytes into its protected body reference file. Admission/freeze require its hash to equal the registry selected by the accepted [policy epoch](../schemas/policy.md#term-epoch); the helper reads that verified view. This is content materialization of one authority, not a second registry definition. Changed registry facts require a new capsule version/run, while RSI cannot mutate the reference file.

## Interface (contract)

`assess_dependency(requirement: dependency_requirement) -> dependency_assessment`

Registry entries are `{kind, identifier, versions, availability, license_status, evidence_ref}`. `availability` is `bound_local`, `public_but_unbound`, or `unavailable`; `license_status` is `permitted`, `prohibited`, or `unknown`.

- `compatible`: exact version matches, availability is `bound_local`, and license is `permitted`.
- `conflict`: a matching entry demonstrates unavailable/unbound content, prohibited license, or version mismatch.
- `unknown`: identity is absent or ambiguous, or license/availability evidence is missing.

Only `compatible` preserves Screening eligibility. The operator has no model, network, filesystem write or failure mode beyond ordinary type/policy/store errors. New registry facts change the pinned registry hash. Changed assessment semantics require a new operator/profile version.

## Tests

Independent [test cases](../schemas/checks.md#term-test-case) cover the three outcomes (`compatible`, `conflict`, `unknown`) against the pinned registry. Entry points and injectable failures: [test surfaces](../system/test-surfaces.md).

## Acceptance seeds

These rows seed the spec AC table. Each is derived from the behavior on this page; the coding spec sets final thresholds and [fixtures](../system/test-surfaces.md#term-fixture). Level is [BLOCK](../v-model.md#term-block), [BOUNDARY](../v-model.md#term-boundary) or [SYSTEM](../v-model.md#term-system).

| AC ID | Source | Observable criterion | Level |
|---|---|---|---|
| cap.op-assess-dependency.AC-01 | PRD 3.4.6 | Exact version, bound_local availability and permitted license give compatible. | BLOCK |
| cap.op-assess-dependency.AC-02 | PRD 3.4.6 | Unavailable or unbound content, prohibited license or version mismatch gives conflict. | BLOCK |
| cap.op-assess-dependency.AC-03 | PRD 3.4.6 | Absent or ambiguous identity, or missing license or availability evidence, gives unknown. | BLOCK |
| cap.op-assess-dependency.AC-04 | N_node | Only compatible preserves Screening eligibility; conflict and unknown are ineligible. | BLOCK |
| cap.op-assess-dependency.AC-05 | N_node | The operator makes no model, network or filesystem write call and accepts no registry path or override from the caller. | BLOCK |
| cap.op-assess-dependency.AC-06 | N_node | A changed registry changes the pinned registry hash; a hash mismatch refuses the call. | BOUNDARY |
