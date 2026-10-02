---
type: design
status: blackbox
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt]
provides: [research.form_hypothesis]
consumes: [cc.type.opportunity_card, cc.type.research_brief, cc.type.intake, cc.type.hypothesis_blueprint]
depends_on: [pipeline.md, ../types/hypothesis-blueprint.md, op-codesearch.md]
tags: [m1, blackbox]
---

> **Provisional product semantics.** Canonical technical contracts are defined below; readings 41 and 44 and registered method availability remain explicit blockers.

# `hypothesis_capsule`: `research.form_hypothesis` (PRD 3.5)

## What it does

It turns the chosen opportunity into one testable claim: what changes, what is measured, the baseline, the locked dataset, the mechanism (to a file and line when it can), and the pre-registered thresholds, frozen before any code is written (3.5.1 to 3.5.5).

## Provisional interface

| | |
|---|---|
| **Step id** | `hypothesis` |
| **Work capsule** | `research.form_hypothesis`, a `tool` with one bounded model turn that pins `op.codesearch` and `op.freeze_resources` |
| **Inputs** | [`opportunity_card`](../types/opportunity-card.md) from `screening`; [`research_brief`](../types/research-brief.md); [`intake`](../types/intake.md) (project_asset and validation_data resources, not text documents) |
| **Outputs** | [`hypothesis_blueprint`](../types/hypothesis-blueprint.md) |
| **Operators it pins** | [`op.codesearch`](op-codesearch.md), to locate the mechanism; [`op.freeze_resources`](measurement-protocol.md#frozen-methods), to publish immutable resource/config snapshots |
| **Effect class** | `idempotent`, snapshot publication only under `fs:workspace/.cc/snapshots/*`; broker narrows this to the current run |
| **Gate capsule** | `research.accept_hypothesis`: judged criteria, intended: the claim is falsifiable by the thresholds, the dataset is ingested and not synthesized, the Brief target is preserved and claim/falsification predicates are separately pre-registered |

## Known from the PRD

- One claim, one path (3.5.1).
- The claim and the falsification threshold are two numbers (3.5.1, 3.5.4).
- No synthetic data (3.5.2).
- The blueprint is immutable downstream (3.5.5).

## Assumptions

- Each mandatory Brief metric has a blueprint entry referring to its id, with acceptance target preserved separately from claim and falsification predicates ([open issues](../open-issues.md) 41).
- A deterministic Tier 1 check: every mandatory Brief metric is in the blueprint, at least as strict.
- Each metric declares its direction, unit (absolute, relative or points), success target, falsification threshold and any guard, and the blueprint declares the repeat count (item 44).
- The dataset is a supplied `validation_data` resource, or a declared, pre-installed standard one (3.5.2, item 45).

## Waits on, and revise when

- [Open issues](../open-issues.md) 41 and 44, confirmed by Ramika: fix `expected` and `falsified_at`.
- Resource kinds and snapshot fields are designed in intake v2; unreadable or missing scientific resources block this experiment.
- CodeSearch's dependency compatibility remains issue 33; measurement method coverage is issue 58.

## Coding handoff contracts

Code/process placement is [modules](../system/modules.md). Shared request, deadline, duplicate and cancellation semantics are [runner](../capsule/runner.md) and [lifecycle](../system/lifecycle.md); storage owns all publication and recovery. This stage emits no successful output for missing required inputs, mismatched pins, invalid schema or failed mandatory capture. The supervisor owns halt and explicit human restart. Each attempt retains its evidence under the same run identity; changed frozen inputs require a new run.

The owning output type page defines fields and cross-input checks. [Measurement protocol](measurement-protocol.md) defines methods, samples, transforms and compiler evidence. [Research gates](research-gates.md) defines this stage's acceptance API and criteria. No local copy of a shared schema is authoritative. [Verification](../system/verification.md) gives independently callable entry points, expected observations and injectable failures; runtime acceptance results belong to coding work.

Freeze resource snapshots and method/config hashes before returning the blueprint; the Gate must confirm this publication before POC is invoked. Missing baseline/dataset/method/hardware blocks scientific readiness here; it does not turn initial raw intake qualification into a dataset requirement. CodeSearch works on that snapshot only. The model proposes one claim; deterministic code validates all predicates, mandatory Brief metrics and repeat/seed settings. There is no code generation at this stage.
