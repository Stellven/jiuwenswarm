---
type: design
status: draft
version: 1
owner: muk
sources: [../types/dependency-requirement.md, ../types/dependency-assessment.md, ../schemas/policy.md]
provides: [op.assess_dependency]
consumes: [cc.type.dependency_requirement]
depends_on: [../types/dependency-requirement.md, ../types/dependency-assessment.md, ../schemas/policy.md]
tags: [module, m1, operator, screening]
---

# Ordinary module contract: `op.assess_dependency`: deterministic dependency policy

> Module API names below retain their op.* namespace for callable interfaces. They are not separately admitted capsule identities; code is pinned through its owning work capability/profile. Screening RSI evaluates helper candidates offline and activation replaces the owner version, preserving runtime ranking checks.

A pure operator that maps one [`dependency_requirement`](../types/dependency-requirement.md) to one [`dependency_assessment`](../types/dependency-assessment.md) under the frozen policy registry. The caller supplies no registry path or policy override; its Binding pins the registry hash.

## Contract

`assess_dependency(requirement: dependency_requirement) -> dependency_assessment`

Registry entries are `{kind, identifier, versions, availability, license_status, evidence_ref}`. `availability` is `bound_local`, `public_but_unbound`, or `unavailable`; `license_status` is `permitted`, `prohibited`, or `unknown`.

- `compatible`: exact version matches, availability is `bound_local`, and license is `permitted`.
- `conflict`: a matching entry demonstrates unavailable/unbound content, prohibited license, or version mismatch.
- `unknown`: identity is absent or ambiguous, or license/availability evidence is missing.

Only `compatible` preserves Screening eligibility. The operator has no model, network, filesystem write or failure mode beyond ordinary type/policy/store errors. New registry facts change the pinned registry hash. Changed assessment semantics require a new operator/profile version.
