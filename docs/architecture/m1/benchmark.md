---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [research.run_benchmark]
consumes: [cc.type.poc_bundle, cc.type.hypothesis_blueprint, cc.type.benchmark_payload]
depends_on: [pipeline.md, ../types/benchmark-payload.md, ../capsule/process-boundary.md]
tags: [m1, contract]
---

> **Provisional security dependency.** The empirical protocol is defined; execution remains unavailable until its platform profile passes mandatory checks.

# `benchmark_capsule`: `research.run_benchmark` (PRD 3.7)

## What it does

It requests the separate process service to provision the bundle in a POC-scoped venv and run the harness under the restricted identity (baseline, then treatment, same seed policy, the blueprint's repeat count). It captures stdout, stderr and measured values, then computes the deltas. It collects; it never grades (3.7.1 to 3.7.4). The capsule call itself still goes through the CC runner.

## Provisional interface

| | |
|---|---|
| **Step id** | `benchmark` |
| **Work capsule** | `research.run_benchmark`, a `tool`, no model |
| **Inputs** | [`poc_bundle`](../types/poc-bundle.md) from `poc`; [`hypothesis_blueprint`](../types/hypothesis-blueprint.md) |
| **Outputs** | [`benchmark_payload`](../types/benchmark-payload.md) |
| **Execution boundary** | [`PocExecutionRequest` / `PocExecutionResult`](../capsule/process-boundary.md#provisional-api); generated program execution is not the CC capsule-call runner |
| **Effect class** | `nonrepeatable_effect`: pinned policy, gated inputs and the exact durable dispatch reservation authorize the first bounded empirical execution after predecessor release. Measurements are never repeated automatically. Stable request identity returns the original result/in-progress state; explicit human-reviewed restart allocates a new reserved attempt. The validated process profile bounds all effects. |
| **Gate profile** | shared `research.verifier` + `research.accept_benchmark.v1`: judged criteria, intended: both runs completed, and the values trace to the raw output. Never whether the claim held: that is evaluation's job |

## Known from the PRD

- An install failure ends the run, to human triage (3.7.1). A missing or broken wheelhouse is `ENVIRONMENT_BLOCKED`; a package the bundle names that the wheelhouse lacks is caught earlier, at the 3.6 gate (item 43).
- One harness execution produces both runs (3.7.2), under the same hardware, configuration, data and seed policy.
- Raw stdout, stderr and traces go to Data Foundation run bundles; memory keeps summaries only (3.7.3).
- The CC runner runs this capsule, like every other (4.1.4; item 42); this capsule calls the distinct process boundary for the generated program.
- It collects numbers, never interprets them (3.7.3, 3.7.4).

## Startup and required validation

The restricted process profile, separate oracle identity and offline wheelhouse are mandatory prerequisites. Startup fails closed if their checks fail. Effective deadline is the frozen minimum of Brief runtime_limit_s and policy cap; a declared experiment that cannot fit is rejected before freeze with BUDGET_EXCEEDED. The process service owns cancellation and process-tree termination. No attended or unconstrained fallback is available.

## Coding handoff contracts

Code/process placement is [modules](../system/modules.md). Shared request, deadline, duplicate and cancellation semantics are [runner](../capsule/runner.md) and [lifecycle](../system/lifecycle.md); storage owns all publication and recovery. This stage emits no successful output for missing required inputs, mismatched pins, invalid schema or failed mandatory capture. The supervisor owns halt and explicit human restart. Each attempt retains its evidence under the same run identity; changed frozen inputs require a new run.

The owning output type page defines fields and cross-input checks. [Measurement protocol](measurement-protocol.md) defines methods, samples, transforms and compiler evidence. [Research gates](research-gates.md) defines this stage's acceptance API and criteria. No local copy of a shared schema is authoritative. [Verification](../system/verification.md) gives independently callable entry points, expected observations and injectable failures; runtime acceptance results belong to coding work.

Invoke execute_poc first with poc_setup, then benchmark: a single harness execution emits both arms for every repeat. Use only preinstalled or approved wheelhouse packages under the frozen package-source profile. The process service owns unpacking, child deadlines and tree termination. Parse raw capture with the trusted protocol parser, derive raw deltas, store empirical_results.json and complete capture, then return benchmark_payload v2. Never ask a model to parse or grade results. Nonzero exit/timeout or malformed required stream preserves logs and halts; unavailable isolation is an environment failure.
