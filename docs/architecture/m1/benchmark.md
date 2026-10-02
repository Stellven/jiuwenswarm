---
type: design
status: blackbox
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt]
provides: [research.run_benchmark]
consumes: [cc.type.poc_bundle, cc.type.hypothesis_blueprint, cc.type.benchmark_payload]
depends_on: [pipeline.md, ../types/benchmark-payload.md, ../capsule/process-boundary.md]
tags: [m1, blackbox]
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
| **Effect class** | Provisional `idempotent` only if the process boundary confines writes to the run's POC workspace and throwaway venv and denies undeclared effects. If it cannot establish that boundary, do not run the benchmark (issue 54); do not silently fall back to an attended execution. |
| **Gate capsule** | `research.accept_benchmark`: judged criteria, intended: both runs completed, and the values trace to the raw output. Never whether the claim held: that is evaluation's job |

## Known from the PRD

- An install failure ends the run, to human triage (3.7.1). A missing or broken wheelhouse is `ENVIRONMENT_BLOCKED`; a package the bundle names that the wheelhouse lacks is caught earlier, at the 3.6 gate (item 43).
- One harness execution produces both runs (3.7.2), under the same hardware, configuration, data and seed policy.
- Raw stdout, stderr and traces go to Data Foundation run bundles; memory keeps summaries only (3.7.3).
- The CC runner runs this capsule, like every other (4.1.4; item 42); this capsule calls the distinct process boundary for the generated program.
- It collects numbers, never interprets them (3.7.3, 3.7.4).

## Assumptions

- The process boundary is mandatory; an attended run or jiuwenbox is not a substitute under the current PRD. Items 40, 42 and 43 resolve identity/oracle, capsule-versus-program roles, and offline package provisioning before this design can be checked.
- The 1800 s policy cap may be below a long benchmark. The Brief's `runtime_limit_s` may need a higher cap for this step.

## Waits on, and revise when

- Resolve [open issues](../open-issues.md) 40, 42, 43 and 54; validate the effective restricted identity, oracle isolation, package-source rule, and boundary pre-check. Runtime provisioning of the unprivileged identity and local wheelhouse are prerequisites, not capsule schema fields.

## Coding handoff contracts

Code/process placement is [modules](../system/modules.md). Shared request, deadline, duplicate and cancellation semantics are [runner](../capsule/runner.md) and [lifecycle](../system/lifecycle.md); storage owns all publication and recovery. This stage emits no successful output for missing required inputs, mismatched pins, invalid schema or failed mandatory capture. The supervisor owns halt and explicit human restart. Each attempt retains its evidence under the same run identity; changed frozen inputs require a new run.

The owning output type page defines fields and cross-input checks. [Measurement protocol](measurement-protocol.md) defines methods, samples, transforms and compiler evidence. [Research gates](research-gates.md) defines this stage's acceptance API and criteria. No local copy of a shared schema is authoritative. [Verification](../system/verification.md) gives independently callable entry points, expected observations and injectable failures; runtime acceptance results belong to coding work.

Invoke execute_poc first with poc_setup, then benchmark: a single harness execution emits both arms for every repeat. Use only preinstalled or approved wheelhouse packages under issue 43. The process service owns unpacking, child deadlines and tree termination. Parse raw capture with the trusted protocol parser, derive raw deltas, store empirical_results.json and complete capture, then return benchmark_payload v2. Never ask a model to parse or grade results. Nonzero exit/timeout or malformed required stream preserves logs and halts; unavailable isolation is an environment failure.
