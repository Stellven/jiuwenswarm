---
id: cap.poc
type: capability
status: draft
version: 1
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [research.build_poc]
consumes: [cc.type.hypothesis_blueprint, cc.type.research_brief, cc.type.intake, cc.type.poc_bundle]
depends_on: [README.md, ../types/poc-bundle.md, op-codesearch.md, op-workspace-io.md]
tags: [m1, contract]
level: detail
prd: [3.6.1, 3.6.2, 3.6.3, 3.6.4, 3.6.5, 4.9.4]
---

Bundle v2 and the shared measurement protocol define assembly. Execution readiness still depends on the validated security profile.

# `poc_capsule`: `research.build_poc` (PRD 3.6)

PRD: 3.6.1, 3.6.2, 3.6.3, 3.6.4, 3.6.5, 4.9.4

> Answers: How does the POC capsule build one patch and one harness, syntax-checked, from the frozen blueprint?

## What it does

It maps the ingested files and the dataset into `/workspace/poc/`, writes a static `requirements.txt` from the [Brief](../types/research-brief.md#term-research-brief)'s frameworks, finds the change site with `op.codesearch`, writes one patch file and one harness that [runs](../system/lifecycle.md#term-run) the baseline then the treatment, syntax-checks both, and bundles them (3.6.1 to 3.6.5).

## Where it sits

| | |
|---|---|
| <a id="term-flow-position"></a>**Flow position** | Planned node in the research chain template (see [capabilities](README.md)); the planner binds its inputs when it composes the DAG. |
| <a id="term-work-capsule"></a>**Work capsule** | `research.build_poc`, a `tool` with at most two scheduled generation calls under the [bounded generation design](#bounded-generation-design) |
| <a id="term-inputs"></a>**Inputs** | [`hypothesis_blueprint`](../types/hypothesis-blueprint.md) from `hypothesis`; [`research_brief`](../types/research-brief.md); [`intake`](../types/intake.md) |
| <a id="term-outputs"></a>**Outputs** | [`poc_bundle`](../types/poc-bundle.md) |
| <a id="term-admitted-dependency"></a>**Admitted dependency** | [`op.codesearch`](op-codesearch.md) |
| <a id="term-ordinary-module-service-calls"></a>**Ordinary module/service calls** | [workspace read/write/list](op-workspace-io.md); trusted [syntax_check](measurement-protocol.md#syntax-checking). These are not independently admitted capsules |
| <a id="term-effect-class"></a>**Effect class** | `idempotent`, writing only `fs:workspace/poc/*`, so it is allowed unattended |
| <a id="term-gate-profile"></a>**Gate profile** | shared `research.verifier` + `research.accept_poc.v1`: judged criteria, intended: the patch implements the blueprint's mechanism and nothing else, and the harness measures exactly the blueprint's metrics |

## Known from the PRD

- One patch file, no multi-file refactor (3.6.2).
- The harness runs the unmodified baseline first, then the treatment (3.6.3).
- No pip at this stage; `requirements.txt` is static (3.6.1). The [Gate](../verification.md#term-gate) [checks](../capsule/fields.md#term-check) declared package compatibility without running generated setup/build hooks. An unavailable wheelhouse is ENVIRONMENT_BLOCKED; unsupported or undeclared requirements fail the bundle contract ([open issues](../decisions.md#open) 43).
- Generated code must not import `os`, `sys`, `subprocess`, `requests`, `urllib` or `shutil` (3.6.2, 4.2.5). This is a [Tier 1](../verification.md#term-tier-1) hygiene check. Stage 3.6 only writes and packages code; Stage 3.7 executes it through the separate [M1 process boundary](../capsule/process-boundary.md).
- The bundle's file list differs between 3.6.5 (adds "the environment configuration") and 4.9.4 (review A8). Ours: the four, with the configuration as one file.
- The Builder of 4.9 is this [capsule](../capsule/capsule.md#term-capability-capsule), run by the [CC runner](../capsule/runner.md#term-runner) (item 42).
- A failed syntax check goes to the gate, never to a repair loop (3.6.4).
- It must not alter the measurement functions or the thresholds (3.6.3).

## Assumptions

- The blueprint pins trusted measurement registry entries; [measurement authority](measurement-protocol.md#trusted-measurement-authority) is the home of production and independent evidence. Method availability remains registered method [fixtures](../system/test-surfaces.md#term-fixture).
- The harness forwards canonical BenchmarkSample records obtained from the trusted measurement service; [measurement protocol](measurement-protocol.md) defines their exact shape.

## Required validation

The registered method/hardware [adapters](../system/integration.md#term-adapter), generated-code isolation profile, offline wheelhouse and CodeSearch source pin require implementation fixtures. These are explicit prerequisites of affected calls, not missing architecture decisions. CodeSearch and workspace interfaces are pinned independently.

## Coding handoff contracts

Code/process placement is [modules](../system/modules.md). Shared request, deadline, duplicate and cancellation semantics are [runner](../capsule/runner.md) and [lifecycle](../system/lifecycle.md); storage is the home of all publication and recovery. This stage emits no successful output for missing required inputs, mismatched pins, invalid schema or failed mandatory capture. The supervisor is the home of halt and explicit human restart. Each attempt retains its evidence under the same run identity; changed [frozen](../system/lifecycle.md#term-freeze) inputs require a new run.

The output type page defines fields and cross-input checks. [Measurement protocol](measurement-protocol.md) defines methods, samples, transforms and compiler evidence. [Research gates](research-gates.md) defines this stage's acceptance API and criteria. No local copy of a shared schema is authoritative. [Verification](../system/test-surfaces.md) gives independently callable entry points, expected observations and injectable failures; runtime acceptance results belong to coding work.

Assembly order: map frozen resources read-only, generate static declared requirements and environment.json, locate the intervention, write one patch and one sequential harness, call op.syntax_check once, publish the four-role ZIP/manifest. Store syntax evidence as an Artifact; set syntax_check_ref to its returned Ref. No generated import or experiment runs at this stage. A compiler failure is recorded and routed to human triage without repairs. The harness uses registered measurement methods and BenchmarkSample stdout; it cannot supply replacements.

## Bounded generation design

The provisional M1 authoring budget is two brokered generation calls: first propose the one patch using the frozen mechanism and authorized code excerpts; then propose the one harness using that patch, frozen protocol and trusted measurement adapter instructions. Requirements/environment assembly is deterministic. A malformed patch reply stops before the harness call; a malformed harness or failed syntax check ends the attempt without repair. The second call is scheduled assembly, not a retry. The admitted wrapper and frozen per-call budget enforce this ceiling. No model-directed dependency loop or third call is permitted.

This is an architecture default, not a PRD-prescribed call count or demonstrated quality result. Separate typed component interfaces and implementation [steps](../system/nodes.md#term-step) follow [Kubeflow](https://www.kubeflow.org/docs/components/pipelines/reference/component-spec/); the [Codex adapter](../system/integration.md#term-codex-adapter) uses the explicit [turn](../system/model-bridge.md#term-model-turn) boundary documented by [OpenAI app-server](https://developers.openai.com/codex/app-server/). Compare one-pass and this bounded two-pass generation on paired visible fixtures before a manual version change; preserve the same public bundle, permissions and Gate criteria. Capsule-specific optimization and defect [families](../contracts/principles.md#term-message-family) are in the [capability guide](improvement.md).

## Declaration

No [Declaration](../capsule/fields.md#term-declaration) JSON is abridged on this page. The Work capsule, Admitted dependency and Effect class rows in Where it sits state the contract; the Declaration format is in [capsule fields](../capsule/fields.md).

## Checks

Tier 1 hygiene (prohibited imports, one patch file) and the syntax check are stated in Known from the PRD and Assembly order above. The Gate checks are in the `research.accept_poc` row of [research gates](research-gates.md).

## Tests

Independently callable entry points, expected observations and injectable failures: [test surfaces](../system/test-surfaces.md). Required fixtures are listed under Required validation above. Runtime acceptance results belong to coding work.

## Acceptance seeds

These rows seed the spec AC table. Each is derived from the behavior on this page; the coding spec sets final thresholds and fixtures. Level is [BLOCK](../v-model.md#term-block), [BOUNDARY](../v-model.md#term-boundary) or [SYSTEM](../v-model.md#term-system).

| AC ID | Source | Observable criterion | Level |
|---|---|---|---|
| cap.poc.AC-01 | PRD 3.6.2 | The bundle holds exactly 4 file roles (requirements, environment configuration, one patch, one harness) and the patch touches one file. | BLOCK |
| cap.poc.AC-02 | PRD 3.6.2, PRD 4.2.5 | A patch or harness importing os, sys, subprocess, requests, urllib or shutil fails the Tier 1 hygiene check. | BLOCK |
| cap.poc.AC-03 | PRD 3.6.3 | The harness runs the unmodified baseline first, then the treatment; measurement functions and thresholds are unchanged from the blueprint. | BLOCK |
| cap.poc.AC-04 | PRD 3.6.4 | A failed syntax_check ends the attempt with 0 repair calls and routes to human triage; syntax evidence is stored as an Artifact and referenced by syntax_check_ref. | BOUNDARY |
| cap.poc.AC-05 | PRD 3.6.1 | requirements.txt is static; no pip, generated import or experiment runs at this stage. | BLOCK |
| cap.poc.AC-06 | N_node | Generation uses at most 2 brokered calls (patch, then harness); a malformed patch reply stops before the harness call. | BLOCK |
| cap.poc.AC-07 | N_node | An unavailable wheelhouse yields ENVIRONMENT_BLOCKED; an undeclared or unsupported requirement fails the bundle contract. | BOUNDARY |
| cap.poc.AC-08 | G_node | The POC Gate fails a bundle whose harness measures a metric not in the blueprint; no benchmark call starts. | SYSTEM |
