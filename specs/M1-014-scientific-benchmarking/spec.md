# Feature Specification: M1-014 - Scientific baseline and treatment execution
**TASK**: [M1-014](../../docs/tasks/M1/M1-014/TASK.md)
**Parent TASKS**: [M1](../../docs/tasks/M1/TASKS.md)
**Revision / date**: r1 / 2026-10-01
**Feature Branch**: ai4r_xiaoyang (document-preparation checkout; no feature branch created)
**Input**: [PRD-Full.r1](../../docs/tasks/M1/sources/PRD-Full.r1.txt), §3.7 (all); sequencing §6.8; shared §§1–2; architecture PENDING_SOURCE.
**Status**: Preparing — PRD-derived requirements populated; architecture binding pending, runtime NOT_RUN.
Local IDs are qualified by M1-014; this is the only AC authority for this task.

## User Scenarios & Testing
### User Story 1 - Scientific baseline and treatment execution (Priority: P1)
A researcher receives actual comparative measurements from the fixed experiment rather than model-invented results.
**Independent Test**: Given an admitted POC and frozen blueprint, when execution succeeds, then run the live baseline before the treatment under the same declared conditions and submit raw-backed measurements to the infrastructure Gate. Given environment construction failure, terminate for human triage without dependency repair.
**Acceptance Scenarios**:
1. Given source-conforming inputs and ready declared dependencies, when this bounded capability executes, then its artifacts and observable effects satisfy the ACs below and remain attributable to the run/capsule.
2. Given a prohibited action, invalid contract/evidence or source-defined failure, when execution or verification detects it, then preserve the failure and follow the shared halt/non-admission behavior; do not silently report completion or repair autonomously.
3. Given a connected consumer, when the provider submits an artifact/candidate, then respect the owning interface, governance boundary and version identity rather than infer success from a model response.

### Edge Cases
- Execute valid environment setup and missing/conflicting dependency cases; inspect venv ownership/scope and retained install logs. Observe failure termination without a repair loop. Verify unauthorized host/network effects are denied using the architecture-approved safe test boundary.
- Execute a versioned small fixture with independently specified measurements; capture ordered launches and actual settings. Exercise missing baseline and changed-data/configuration variants; verify they are not admitted as valid comparison.
- Execute known-output and malformed/missing-metric fixtures; trace each metric to raw evidence, inspect run-bundle retention and compact memory. Missing required data remains a visible evidence failure rather than a fabricated value.
- Submit conforming and invalid-protocol/evidence payloads through the real Gate to the scientific-evaluation consumer; observe durable admit-or-halt behavior without a benchmark-generated scientific verdict.
Architecture supplies representation, timeout/cancellation and recovery details; there is no assumed retry or resume mechanism. Source-specific numerical limits are listed in ACs only. No real-service claim is established by fixtures or stubs.

## Requirements
### Functional Requirements
- **FR-001** (§3.7.1): Unpack admitted POC artifacts into the active local workspace and provision the source-required unprivileged venv. Preserve the explicit requirements-installation step, subject to Q02. Environment-build failure terminates for human triage; no dynamic conflict resolution or autonomous debugging.
- **FR-002** (§3.7.2; §§1.4,2.5): Run the original unmodified baseline first, then the treatment using poc_patch.py, under the same declared hardware, benchmark configuration, validation data and seed policy. Treatment-only runs and post-hoc protocol changes cannot count as valid comparative evidence.
- **FR-003** (§3.7.3; §2.10): Capture stdout/stderr, telemetry and execution traces in the system Run Bundle; agent memory holds only compact summaries/references. Populate empirical_results.json with the dependent variables declared by the frozen blueprint and no model-invented measurements.
- **FR-004** (§3.7.4; §6.8; §§2.5,2.8): Bundle empirical results plus stdout/stderr into Benchmark_Payload.json and submit it for infrastructure verification. Release to scientific evaluation only after PASS or PASS_WITH_KNOWN_LIMITATIONS. Benchmarking itself does not apply falsifiability rules or assign scientific success.
### Key Entities
Admitted POC artifact; fixed experimental protocol; local execution environment; empirical_results.json; Benchmark_Payload.json; raw stdout/stderr and telemetry retained in the Run Bundle. See [M1-IF-014@r0](../../docs/tasks/M1/M1-014/TASK.md#4-embedded-cross-module-agreements) for canonical preliminary semantic handoff; exact schemas are PENDING_DESIGN.

## Success Criteria
### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD r1 §3.7.1 / FR-001 / US1 | Unpack admitted POC artifacts into the active local workspace and provision the source-required unprivileged venv. Preserve the explicit requirements-installation step, subject to Q02. Environment-build failure terminates for human triage; no dynamic conflict resolution or autonomous debugging. | BLOCK |
| AC-002 | PRD r1 §3.7.2; §§1.4,2.5 / FR-002 / US1 | Run the original unmodified baseline first, then the treatment using poc_patch.py, under the same declared hardware, benchmark configuration, validation data and seed policy. Treatment-only runs and post-hoc protocol changes cannot count as valid comparative evidence. | BLOCK |
| AC-003 | PRD r1 §3.7.3; §2.10 / FR-003 / US1 | Capture stdout/stderr, telemetry and execution traces in the system Run Bundle; agent memory holds only compact summaries/references. Populate empirical_results.json with the dependent variables declared by the frozen blueprint and no model-invented measurements. | BLOCK |
| AC-004 | PRD r1 §3.7.4; §6.8; §§2.5,2.8 / FR-004 / US1 | Bundle empirical results plus stdout/stderr into Benchmark_Payload.json and submit it for infrastructure verification. Release to scientific evaluation only after PASS or PASS_WITH_KNOWN_LIMITATIONS. Benchmarking itself does not apply falsifiability rules or assign scientific success. | BLOCK, BOUNDARY |
System-level end-to-end acceptance is owned by M1-SYSTEM, not copied into this task. Every row has block/check/work correspondence in plan.md and tasks.md; no runtime result is implied.

## Scope and Assumptions
- Included / excluded scope: Execute the admitted POC locally, collect comparable live baseline/treatment measurements and preserve raw evidence. Excludes isolated treatment-only scoring, dependency-conflict repair, scientific verdict assignment, external cloud execution and undeclared dataset acquisition.
- Shared boundaries: local single-user scientific lane; fixed Phase 1 DAG and authorized tools/resources; frozen scientific protocol; separate scientific result and infrastructure release; authoritative system evidence; no automatic repair, live RSI, model training, external publication or distributed/cloud baseline execution (§§1–2). Shared enforcement ACs belong to their owning tasks; this task's observable compliance is covered above.
- Consumed TASK agreements: [M1-IF-013@r0](../../docs/tasks/M1/M1-013/TASK.md#4-embedded-cross-module-agreements); [M1-IF-012@r0](../../docs/tasks/M1/M1-012/TASK.md#4-embedded-cross-module-agreements); [M1-IF-002@r0](../../docs/tasks/M1/M1-002/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../../docs/tasks/M1/M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../../docs/tasks/M1/M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../../docs/tasks/M1/M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../../docs/tasks/M1/M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../../docs/tasks/M1/M1-007/TASK.md#4-embedded-cross-module-agreements).
- Permitted models: Phase 1 uses the single static Codex CLI route through M1-001/M1-004; role/consumer needs do not authorize a new model pool. Record actual provider/model/version when available; no guessed model identifier.
- Assumptions and unresolved source inputs: M1-014-Q01: Architecture, exact metric/payload schemas, unprivileged execution realization and entry points are pending. Resolution: Register architecture; bind implementations and fixture versions before dependent execution. M1-014-Q02: The installation scope between §3.6.1 preinstalled environment and §3.7.1 explicit pip installation is not resolved by these documents. Resolution: Resolve product scope locally with M1-013; retain both source requirements pending clarification.
- Architecture boundary: exact payload types, APIs, IPC, class/module design, process topology, storage paths and security realization remain PENDING_DESIGN pending the architecture source. Source-given names/constraints above are requirements, not proof of implementation.
- System tasks: [M1-SYSTEM](../../docs/tasks/M1/M1-SYSTEM/TASK.md) consumes this task's current candidate, block/boundary evidence and source constraints for complete journeys; its acceptance remains separate.

This is the AC authority. Technical realization stays in plan.md; progress/results stay in tasks.md.

