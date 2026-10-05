---
id: cap.benchmark
type: capability
status: draft
version: 1
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [research.run_benchmark]
consumes: [cc.type.poc_bundle, cc.type.hypothesis_blueprint, cc.type.benchmark_payload]
depends_on: [README.md, ../types/benchmark-payload.md, ../capsule/process-boundary.md]
tags: [m1, contract]
level: detail
prd: [3.7.1, 3.7.2, 3.7.3, 3.7.4]
---

Execution depends on the validated process security profile (see Startup below); the empirical protocol itself is defined.

# `benchmark_capsule`: `research.run_benchmark` (PRD 3.7)

PRD: 3.7.1, 3.7.2, 3.7.3, 3.7.4

> Answers: How does the benchmark capsule run the baseline and treatment and collect raw measurements without grading them?

## What it does

It requests the separate process service to provision the bundle in a POC-scoped venv and run the harness under the restricted identity (baseline, then treatment, same seed policy, the blueprint's repeat count). It captures stdout, stderr and measured values, then computes the deltas. It collects; it never grades (3.7.1 to 3.7.4). The [capsule](../capsule/capsule.md#term-capability-capsule) call itself still goes through the [CC runner](../capsule/runner.md#term-runner).

## Where it sits

| | |
|---|---|
| <a id="term-flow-position"></a>**Flow position** | Planned node in the research chain template (see [capabilities](README.md)); the planner binds its inputs when it composes the DAG. |
| <a id="term-work-capsule"></a>**Work capsule** | `research.run_benchmark`, a `tool`, no model |
| <a id="term-inputs"></a>**Inputs** | [`poc_bundle`](../types/poc-bundle.md) from `poc`; [`hypothesis_blueprint`](../types/hypothesis-blueprint.md) |
| <a id="term-outputs"></a>**Outputs** | [`benchmark_payload`](../types/benchmark-payload.md) |
| <a id="term-execution-boundary"></a>**Execution boundary** | [`PocExecutionRequest` / `PocExecutionResult`](../capsule/process-boundary.md#interface-provisional-api) (Schema: `library-rsi-v1.schema.json#poc_execute_request` / `library-rsi-v1.schema.json#poc_execute_result`); generated program execution is not the CC capsule-call runner |
| <a id="term-effect-class"></a>**Effect class** | `nonrepeatable_effect`: pinned policy, gated inputs and the exact durable dispatch reservation authorize the first bounded empirical execution after predecessor release. Measurements are never repeated automatically. Stable request identity returns the original result/in-progress state; explicit human-reviewed restart allocates a new reserved attempt. The validated process profile bounds all effects. |
| <a id="term-gate-profile"></a>**Gate profile** | shared `research.verifier` + `research.accept_benchmark.v1`: judged criteria, intended: both runs completed, and the values trace to the raw output. Never whether the claim held: that is evaluation's job |

## Known from the PRD

- An install failure ends the run, to human triage (3.7.1). A missing or broken wheelhouse is `ENVIRONMENT_BLOCKED`; a package the bundle names that the wheelhouse lacks is caught earlier, at the 3.6 gate (item 43).
- One harness execution produces both [runs](../system/lifecycle.md#term-run) (3.7.2), under the same hardware, configuration, data and seed policy.
- Raw stdout, stderr and traces go to [Data Foundation](../system/storage.md#term-data-foundation) run bundles; memory keeps summaries only (3.7.3).
- The CC runner runs this capsule, like every other (4.1.4; item 42); this capsule calls the distinct process boundary for the generated program.
- It collects numbers, never interprets them (3.7.3, 3.7.4).

## Startup and required validation

The restricted process profile, separate oracle identity and offline wheelhouse are mandatory prerequisites. Startup fails closed if their [checks](../capsule/fields.md#term-check) fail. Effective deadline is the [frozen](../system/lifecycle.md#term-freeze) minimum of [Brief](../types/research-brief.md#term-research-brief) runtime_limit_s and policy cap; a declared experiment that cannot fit is rejected before freeze with BUDGET_EXCEEDED. Cancellation and process-tree termination are done by the process service. No attended or unconstrained fallback is available.

## Coding handoff contracts

Code/process placement is [modules](../system/modules.md). Shared request, deadline, duplicate and cancellation semantics are [runner](../capsule/runner.md) and [lifecycle](../system/lifecycle.md); storage is the home of all publication and recovery. This stage emits no successful output for missing required inputs, mismatched pins, invalid schema or failed mandatory capture. The supervisor is the home of halt and explicit human restart. Each attempt retains its evidence under the same run identity; changed frozen inputs require a new run.

The output type page defines fields and cross-input checks. [Measurement protocol](measurement-protocol.md) defines methods, samples, transforms and compiler evidence. [Research gates](research-gates.md) defines this stage's acceptance API and criteria. No local copy of a shared schema is authoritative. [Verification](../system/test-surfaces.md) gives independently callable entry points, expected observations and injectable failures; runtime acceptance results belong to coding work.

Invoke execute_poc first with poc_setup, then benchmark: a single harness execution emits both arms for every repeat. Use only preinstalled or approved wheelhouse packages under the frozen package-source profile. The process service does the unpacking, child deadlines and tree termination. Parse raw capture with the trusted protocol parser, derive raw deltas, store empirical_results.json and complete capture, then return [benchmark_payload](../types/benchmark-payload.md#term-benchmark-payload) v2. Never ask a model to parse or grade results. Nonzero exit/timeout or malformed required stream preserves logs and [halts](../system/lifecycle.md#term-halt); unavailable isolation is an environment failure.

## Declaration

No [Declaration](../capsule/fields.md#term-declaration) JSON is abridged on this page. The Work capsule row and Effect class row in Where it sits state the contract; the Declaration format is in [capsule fields](../capsule/fields.md).

## Checks

The startup checks are in Startup and required validation above. The [Gate](../verification.md#term-gate) checks are in the `research.accept_benchmark` row of [research gates](research-gates.md).

## Tests

Independently callable entry points, expected observations and injectable failures: [test surfaces](../system/test-surfaces.md). Runtime acceptance results belong to coding work.

## Acceptance seeds

These rows seed the spec AC table. Each is derived from the behavior on this page; the coding spec sets final thresholds and [fixtures](../system/test-surfaces.md#term-fixture). Level is [BLOCK](../v-model.md#term-block), [BOUNDARY](../v-model.md#term-boundary) or [SYSTEM](../v-model.md#term-system).

| AC ID | Source | Observable criterion | Level |
|---|---|---|---|
| cap.benchmark.AC-01 | PRD 3.7.2 | One harness execution emits exactly 2 x repeats samples, ordered baseline(0), treatment(0), baseline(1), ...; both arms use the same data, configuration and device. | BOUNDARY |
| cap.benchmark.AC-02 | PRD 3.7.1 | A missing or broken wheelhouse yields ENVIRONMENT_BLOCKED and the run halts to human triage. | BOUNDARY |
| cap.benchmark.AC-03 | PRD 3.7.3 | Raw stdout, stderr and traces are stored in the run bundle; benchmark_payload carries references and raw deltas only; no model parses or grades results. | BLOCK |
| cap.benchmark.AC-04 | N_node | A nonzero exit, timeout or malformed required stream preserves logs and halts; no benchmark_payload is emitted. | BOUNDARY |
| cap.benchmark.AC-05 | N_node | Startup fails closed when the restricted process profile, oracle identity separation or offline wheelhouse check fails; there is no unconstrained fallback. | SYSTEM |
| cap.benchmark.AC-06 | N_node | A duplicate request id returns the original result or in-progress state; a new execution requires explicit human-reviewed restart with a newly reserved attempt. | BOUNDARY |
| cap.benchmark.AC-07 | PRD 3.7.4 | A declared experiment that cannot fit min(runtime_limit_s, policy cap) is rejected before freeze with BUDGET_EXCEEDED. | BOUNDARY |
| cap.benchmark.AC-08 | US-09 | A scientifically negative but valid run produces a benchmark_payload and continues to evaluation. | SYSTEM |
