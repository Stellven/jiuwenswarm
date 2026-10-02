---
type: design
status: blackbox
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt]
provides: [research.evaluate_results]
consumes: [cc.type.benchmark_payload, cc.type.hypothesis_blueprint, cc.type.research_brief, cc.type.evaluation_verdict]
depends_on: [pipeline.md, ../types/evaluation-verdict.md]
tags: [m1, blackbox]
---

> **Black box.** The full PRD puts 3.8 in its own `scientific_evaluator_capsule`, separate from the gate's `verifier_capsule` (L855), as designed here: a work capsule with its own gate, so that a scientific `FAIL` is data, never a halt. The classification rule waits on Ramika ([open issues](../open-issues.md) 44). Its interface is provisional: build against it, and expect it to be revised at integration ([black boxes](../system/blackboxes.md)).

# `evaluation`: `research.evaluate_results` (PRD 3.8)

## What it does

It binds the benchmark payload, the blueprint and the Brief, checks the evidence is complete and traceable to the logs, sanity-checks plausibility in one model turn, compares each delta against the frozen thresholds with fixed code, classifies the outcome, and records risks and follow-ups (3.8.1 to 3.8.6).

## Provisional interface

| | |
|---|---|
| **Step id** | `evaluation` |
| **Work capsule** | `research.evaluate_results`, a `tool`: one model turn and one pure helper |
| **Inputs** | [`benchmark_payload`](../types/benchmark-payload.md) from `benchmark`; [`hypothesis_blueprint`](../types/hypothesis-blueprint.md); [`research_brief`](../types/research-brief.md) |
| **Outputs** | [`evaluation_verdict`](../types/evaluation-verdict.md) |
| **Operators it pins** | `op.compare_to_thresholds`: a pure `tool` that computes each comparison's `outcome` (3.8.4), `evolution.rsi: none` |
| **Effect class** | `pure` |
| **Gate capsule** | `research.accept_evaluation`: judged criteria, intended: the evaluation was done properly (evidence traced, plausibility reasoned). criteria verify that `classification` matches the approved frozen rule, without requiring a successful scientific label |

## Known from the PRD

- A scientific `FAIL` is a valid outcome and goes on to Delivery (3.8.5).
- The comparison is deterministic, never re-judged (3.8.4).
- It is read-only: no patches, no reruns (3.8.6).

## Assumptions

- The classification is fixed code, by [open issue](../open-issues.md) 44: falsified, `fail`; claim met and guards hold, `pass`; a real effect short of the claim, `conditionally_acceptable`; evidence missing, null or flagged by 3.8.3, `inconclusive`. This replaces the earlier assumption that `between` maps to `inconclusive`.
- The Evaluator Gate never re-judges the science (4.2.6, 4.2.8): its infrastructure `PASS` lets every classification reach Delivery.

## Waits on, and revise when

- [Open issue](../open-issues.md) 44, confirmed by Ramika; units and repeat count declared in [`hypothesis_blueprint`](../types/hypothesis-blueprint.md).
- The independent Gate checks the approved rule's application; it never substitutes a new scientific judgement.

## Coding handoff contracts

Code/process placement is [modules](../system/modules.md). Shared request, deadline, duplicate and cancellation semantics are [runner](../capsule/runner.md) and [lifecycle](../system/lifecycle.md); storage owns all publication and recovery. This stage emits no successful output for missing required inputs, mismatched pins, invalid schema or failed mandatory capture. The supervisor owns halt and explicit human restart. Each attempt retains its evidence under the same run identity; changed frozen inputs require a new run.

The owning output type page defines fields and cross-input checks. [Measurement protocol](measurement-protocol.md) defines methods, samples, transforms and compiler evidence. [Research gates](research-gates.md) defines this stage's acceptance API and criteria. No local copy of a shared schema is authoritative. [Verification](../system/verification.md) gives independently callable entry points, expected observations and injectable failures; runtime acceptance results belong to coding work.

Resolve the raw capture through the trusted evidence broker; do not place full logs in model memory. Fixed code computes transformed values and separate claim/acceptance/falsification predicates. One bounded model turn evaluates plausibility from admitted values/evidence only. The approved frozen policy combines comparisons, guards, completeness and anomalies into a label. Policy absent means POLICY_UNRESOLVED; the provisional mapping above is not an executable default. No external fetch, repair or new benchmark is permitted.
