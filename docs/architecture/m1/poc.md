---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt]
provides: [research.build_poc]
consumes: [cc.type.hypothesis_blueprint, cc.type.research_brief, cc.type.intake, cc.type.poc_bundle]
depends_on: [pipeline.md, ../types/poc-bundle.md, op-codesearch.md, op-workspace-io.md]
tags: [m1, blackbox]
---

> **Draft contract.** Bundle v2 and the shared measurement protocol define assembly. Execution readiness still depends on the security profile and owner readings.

# `poc_capsule`: `research.build_poc` (PRD 3.6)

## What it does

It maps the ingested files and the dataset into `/workspace/poc/`, writes a static `requirements.txt` from the Brief's frameworks, finds the change site with `op.codesearch`, writes one patch file and one harness that runs the baseline then the treatment, syntax-checks both, and bundles them (3.6.1 to 3.6.5).

## Provisional interface

| | |
|---|---|
| **Step id** | `poc` |
| **Work capsule** | `research.build_poc`, a `tool` with model turns |
| **Inputs** | [`hypothesis_blueprint`](../types/hypothesis-blueprint.md) from `hypothesis`; [`research_brief`](../types/research-brief.md); [`intake`](../types/intake.md) |
| **Outputs** | [`poc_bundle`](../types/poc-bundle.md) |
| **Operators it pins** | [`op.codesearch`](op-codesearch.md); [`op.workspace_read`, `op.workspace_write`, `op.workspace_list`](op-workspace-io.md); [`op.syntax_check`](measurement-protocol.md#syntax-checking) |
| **Effect class** | `idempotent`, writing only `fs:workspace/poc/*`, so it is allowed unattended |
| **Gate capsule** | `research.accept_poc`: judged criteria, intended: the patch implements the blueprint's mechanism and nothing else, and the harness measures exactly the blueprint's metrics |

## Known from the PRD

- One patch file, no multi-file refactor (3.6.2).
- The harness runs the unmodified baseline first, then the treatment (3.6.3).
- No pip at this stage; `requirements.txt` is static (3.6.1). The Gate checks declared package compatibility without running generated setup/build hooks. An unavailable wheelhouse is ENVIRONMENT_BLOCKED; unsupported or undeclared requirements fail the bundle contract ([open issues](../open-issues.md) 43).
- Generated code must not import `os`, `sys`, `subprocess`, `requests`, `urllib` or `shutil` (3.6.2, 4.2.5). This is a Tier 1 hygiene check. Stage 3.6 only writes and packages code; Stage 3.7 executes it through the separate [M1 process boundary](../capsule/process-boundary.md).
- The bundle's file list differs between 3.6.5 (adds "the environment configuration") and 4.9.4 ([review](../prd/prd-m1-full-review.md) A8). Ours: the four, with the configuration as one file.
- The Builder of 4.9 is this capsule, run by the CC runner (item 42).
- A failed syntax check goes to the gate, never to a repair loop (3.6.4).
- It must not alter the measurement functions or the thresholds (3.6.3).

## Assumptions

- The blueprint pins trusted measurement registry entries; [measurement authority](measurement-protocol.md#trusted-measurement-authority) owns production and independent evidence. Method availability remains issue 58.
- The harness forwards canonical BenchmarkSample records obtained from the trusted measurement service; [measurement protocol](measurement-protocol.md) owns their exact shape.

## Waits on, and revise when

- The published BenchmarkSample protocol is now fixed; its producer/consumer seam is checked separately.
- Registered measurement implementation/hardware coverage remains issue 58.
- [Open issues](../open-issues.md) 42, 43 and 57 (supported confinement), [`op.codesearch`](op-codesearch.md), [`op.workspace_io`](op-workspace-io.md).

## Coding handoff contracts

Code/process placement is [modules](../system/modules.md). Shared request, deadline, duplicate and cancellation semantics are [runner](../capsule/runner.md) and [lifecycle](../system/lifecycle.md); storage owns all publication and recovery. This stage emits no successful output for missing required inputs, mismatched pins, invalid schema or failed mandatory capture. The supervisor owns halt and explicit human restart. Each attempt retains its evidence under the same run identity; changed frozen inputs require a new run.

The owning output type page defines fields and cross-input checks. [Measurement protocol](measurement-protocol.md) defines methods, samples, transforms and compiler evidence. [Research gates](research-gates.md) defines this stage's acceptance API and criteria. No local copy of a shared schema is authoritative. [Verification](../system/verification.md) gives independently callable entry points, expected observations and injectable failures; runtime acceptance results belong to coding work.

Assembly order: map frozen resources read-only, generate static declared requirements and environment.json, locate the intervention, write one patch and one sequential harness, call op.syntax_check once, publish the four-role ZIP/manifest. Store syntax evidence as an Artifact; set syntax_check_ref to its returned Ref. No generated import or experiment runs at this stage. A compiler failure is recorded and routed to human triage without repairs. The harness uses registered measurement methods and BenchmarkSample stdout; it cannot supply replacements.
