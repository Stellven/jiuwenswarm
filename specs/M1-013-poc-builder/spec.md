# Feature Specification: M1-013 - Bounded POC construction and Builder
**TASK**: [M1-013](../../docs/tasks/M1/M1-013/TASK.md)
**Parent TASKS**: [M1](../../docs/tasks/M1/TASKS.md)
**Revision / date**: r1 / 2026-10-01
**Feature Branch**: ai4r_xiaoyang (document-preparation checkout; no feature branch created)
**Input**: [PRD-Full.r1](../../docs/tasks/M1/sources/PRD-Full.r1.txt), §3.6 (all), §4.9 introduction and Phase 1/Future scope in §§4.9.1–4.9.5; §4.9.1/.2 Phase 2 allocated to M1-019; sequencing §6.7; shared §§1–2; architecture PENDING_SOURCE.
**Status**: Preparing — PRD-derived requirements populated; architecture binding pending, runtime NOT_RUN.
Local IDs are qualified by M1-013; this is the only AC authority for this task.

## User Scenarios & Testing
### User Story 1 - Bounded POC construction and Builder (Priority: P1)
A researcher supplies an admitted immutable blueprint and local assets; Builder returns bounded executable artifacts and mechanical evidence for the Gate before empirical execution.
**Independent Test**: Given an admitted blueprint and present local assets, when the POC capsule constructs a bundle, then the package implements the fixed experiment without running scientific evaluation or altering its criteria. Given a mechanical failure, record it and stop for the governed human-intervention path rather than repair automatically.
**Acceptance Scenarios**:
1. Given source-conforming inputs and ready declared dependencies, when this bounded capability executes, then its artifacts and observable effects satisfy the ACs below and remain attributable to the run/capsule.
2. Given a prohibited action, invalid contract/evidence or source-defined failure, when execution or verification detects it, then preserve the failure and follow the shared halt/non-admission behavior; do not silently report completion or repair autonomously.
3. Given a connected consumer, when the provider submits an artifact/candidate, then respect the owning interface, governance boundary and version identity rather than infer success from a model response.

### Edge Cases
- Use supplied and missing baseline/data fixtures; inspect mapped paths and requirements; observe a missing-asset failure without downloading or inventing replacements. Inspect that generation does not autonomously install packages.
- Provide a bounded repository and an intervention target; capture actual CodeSearch calls and patch artifact. Exercise a requested forbidden import/out-of-scope edit and confirm rejection or recorded non-admissibility through shared governance.
- Compare generated harness intent/artifacts against frozen protocol and baseline snapshot; submit threshold/data replacement variants and check they cannot be admitted. Empirical comparison itself belongs to M1-014.
- Compile a valid harness and a syntax-invalid harness; separately inspect output-format validation using non-scientific fixtures. Assert no scientific metric run during assembly and no autonomous retry/patch loop after failure.
- Inspect archive membership and evidence; connect a valid and an invalid bundle to the actual Gate and benchmark consumer, proving execution starts only after a durable advancing decision.
- Submit unauthorized analytical-rewrite/training/deployment requests and inspect tool/write traces plus artifact changes; ensure only source-authorized build outputs exist and prohibited actions are rejected or stopped by shared governance.
Architecture supplies representation, timeout/cancellation and recovery details; there is no assumed retry or resume mechanism. Source-specific numerical limits are listed in ACs only. No real-service claim is established by fixtures or stubs.

## Requirements
### Functional Requirements
- **FR-001** (§3.6.1; §4.9.1 Phase 1): Map supplied local baseline/workspace and fixed validation assets into the bounded POC workspace; verify their presence and generate static requirements from Research Brief framework constraints. Preserve §3.6.1's exclusion of autonomous runtime package installation; reconcile its scope with §3.7.1 before dependent integration.
- **FR-002** (§3.6.2; §4.9.2 Phase 1): Use permitted local CodeSearch navigation/chunking and file/line references to produce standalone poc_patch.py implementing the blueprint. Exclude autonomous multi-file production refactoring and the listed OS/network modules (os, sys, subprocess, requests, urllib, shutil).
- **FR-003** (§3.6.3; §4.9.2 Phase 1): Generate run_benchmark.py to execute the unmodified baseline followed by the patch under the same fixed evaluation data and declared seed policy; preserve preregistered measurement functions and acceptance thresholds.
- **FR-004** (§3.6.4; §4.9.4 Smoke Validation; §4.9.5 Defect Repair): Perform mechanical syntax/readiness and logging-format validation; capture failures without scientific scoring or automatic iterative repair. A compilation/execution failure preserves its trace and enters the shared halt/human_session path.
- **FR-005** (§3.6.5; §4.9.4 Artifact Bundle; §6.7): Package requirements.txt, poc_patch.py, run_benchmark.py and environment configuration into POC_Artifact_Bundle.zip with build evidence. Submit to Gate before M1-014 execution; no external cloud deployment or generated container/wheel/service release.
- **FR-006** (§4.9 introduction; §4.9.3; §4.9.5; §3.6 blacklists; §§1.3,2.2–2.12): Limit Builder to inference/scripting and executable build metadata; do not create or semantically rewrite Opportunity_Card.json, Hypothesis_Blueprint.json, Evaluation_Verdict.json or research_report.md. Exclude neural weight/LoRA/statistical-checkpoint construction, autonomous self-repair, arbitrary product integration, containers/cloud services and generalized analytical document synthesis.
### Key Entities
Immutable Hypothesis Blueprint; Research Brief; bounded POC workspace; requirements.txt; poc_patch.py; run_benchmark.py; POC_Artifact_Bundle.zip and mechanical build evidence. Names are source-defined artifacts, not final field schemas. See [M1-IF-013@r0](../../docs/tasks/M1/M1-013/TASK.md#4-embedded-cross-module-agreements) for canonical preliminary semantic handoff; exact schemas are PENDING_DESIGN.

## Success Criteria
### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD r1 §3.6.1; §4.9.1 Phase 1 / FR-001 / US1 | Map supplied local baseline/workspace and fixed validation assets into the bounded POC workspace; verify their presence and generate static requirements from Research Brief framework constraints. Preserve §3.6.1's exclusion of autonomous runtime package installation; reconcile its scope with §3.7.1 before dependent integration. | BLOCK |
| AC-002 | PRD r1 §3.6.2; §4.9.2 Phase 1 / FR-002 / US1 | Use permitted local CodeSearch navigation/chunking and file/line references to produce standalone poc_patch.py implementing the blueprint. Exclude autonomous multi-file production refactoring and the listed OS/network modules (os, sys, subprocess, requests, urllib, shutil). | BLOCK |
| AC-003 | PRD r1 §3.6.3; §4.9.2 Phase 1 / FR-003 / US1 | Generate run_benchmark.py to execute the unmodified baseline followed by the patch under the same fixed evaluation data and declared seed policy; preserve preregistered measurement functions and acceptance thresholds. | BLOCK |
| AC-004 | PRD r1 §3.6.4; §4.9.4 Smoke Validation; §4.9.5 Defect Repair / FR-004 / US1 | Perform mechanical syntax/readiness and logging-format validation; capture failures without scientific scoring or automatic iterative repair. A compilation/execution failure preserves its trace and enters the shared halt/human_session path. | BLOCK |
| AC-005 | PRD r1 §3.6.5; §4.9.4 Artifact Bundle; §6.7 / FR-005 / US1 | Package requirements.txt, poc_patch.py, run_benchmark.py and environment configuration into POC_Artifact_Bundle.zip with build evidence. Submit to Gate before M1-014 execution; no external cloud deployment or generated container/wheel/service release. | BLOCK, BOUNDARY |
| AC-006 | PRD r1 §4.9 introduction; §4.9.3; §4.9.5; §3.6 blacklists; §§1.3,2.2–2.12 / FR-006 / US1 | Limit Builder to inference/scripting and executable build metadata; do not create or semantically rewrite Opportunity_Card.json, Hypothesis_Blueprint.json, Evaluation_Verdict.json or research_report.md. Exclude neural weight/LoRA/statistical-checkpoint construction, autonomous self-repair, arbitrary product integration, containers/cloud services and generalized analytical document synthesis. | BLOCK |
System-level end-to-end acceptance is owned by M1-SYSTEM, not copied into this task. Every row has block/check/work correspondence in plan.md and tasks.md; no runtime result is implied.

## Scope and Assumptions
- Included / excluded scope: Phase 1 blueprint-to-POC assembly, local scaffolding, CodeSearch-assisted single-file patch, harness, mechanical checks and bundle. §4.9.1/.2 Phase 2 Code Mode experiment acceptance is owned by M1-019, excluded from this task's required ACs. Excludes autonomous repair, training/fine-tuning/checkpoints, production multi-file refactoring, analytical-output ownership, cloud deliverables and M2+ product integration.
- Shared boundaries: local single-user scientific lane; fixed Phase 1 DAG and authorized tools/resources; frozen scientific protocol; separate scientific result and infrastructure release; authoritative system evidence; no automatic repair, live RSI, model training, external publication or distributed/cloud baseline execution (§§1–2). Shared enforcement ACs belong to their owning tasks; this task's observable compliance is covered above.
- Consumed TASK agreements: [M1-IF-012@r0](../../docs/tasks/M1/M1-012/TASK.md#4-embedded-cross-module-agreements); [M1-IF-008@r0](../../docs/tasks/M1/M1-008/TASK.md#4-embedded-cross-module-agreements); [M1-IF-009@r0](../../docs/tasks/M1/M1-009/TASK.md#4-embedded-cross-module-agreements); [M1-IF-002@r0](../../docs/tasks/M1/M1-002/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../../docs/tasks/M1/M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../../docs/tasks/M1/M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../../docs/tasks/M1/M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../../docs/tasks/M1/M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../../docs/tasks/M1/M1-007/TASK.md#4-embedded-cross-module-agreements).
- Permitted models: Phase 1 uses the single static Codex CLI route through M1-001/M1-004; role/consumer needs do not authorize a new model pool. Record actual provider/model/version when available; no guessed model identifier.
- Assumptions and unresolved source inputs: M1-013-Q01: Architecture is PENDING_SOURCE; exact schemas, operator ports, source paths, sandbox realization and command entry points are PENDING_DESIGN. Resolution: Register architecture and bind affected design; independent PRD/spec preparation continues. M1-013-Q02: §3.6.1 assumes preinstalled packages and excludes autonomous runtime pip; §3.7.1 requires installation from requirements. Preserve both source clauses; do not choose a policy silently. Resolution: Confirm whether generation-only prohibition versus executor-controlled installation is intended; update affected source/spec/IF if necessary.
- Architecture boundary: exact payload types, APIs, IPC, class/module design, process topology, storage paths and security realization remain PENDING_DESIGN pending the architecture source. Source-given names/constraints above are requirements, not proof of implementation.
- System tasks: [M1-SYSTEM](../../docs/tasks/M1/M1-SYSTEM/TASK.md) consumes this task's current candidate, block/boundary evidence and source constraints for complete journeys; its acceptance remains separate.

This is the AC authority. Technical realization stays in plan.md; progress/results stay in tasks.md.

