# Feature Specification: M1-002 - Local configuration, identity and execution boundaries

**TASK**: [TASK](../../docs/tasks/M1/M1-002/TASK.md)
**Parent TASKS**: [M1 TASKS](../../docs/tasks/M1/TASKS.md)
**Revision / date**: r2 / 2026-10-02
**Feature Branch**: NOT_STARTED for implementation; documentation uses the existing checkout.
**Input**: [registered PRD r2](../../docs/tasks/M1/sources/PRD-Full.r2.txt), §5.4, §5.6; global §§1–2, §6. Architecture PENDING_SOURCE.
**Status**: Preparing; source-derived requirements populated, architecture-dependent contracts pending.

## User Scenarios & Testing

### User Story 1 - Local configuration, identity and execution boundaries (Priority: P1)

Local single-user settings, source-defined configuration precedence, static endpoint aliases, local-session authentication, restricted execution requirements and budget configuration.

**Independent Test**: Exercise the source-defined behavior with controlled inputs, then connect its real providers/consumers; procedures and retained observations are in plan.md.

**Acceptance Scenarios**:

1. Given the prerequisites for AC-001, when its planned action is exercised, then the observable result must satisfy AC-001. Procedure: Initialize a temporary local profile and supply a research prompt with domain constraints; inspect stored settings and intake context, and confirm no account-creation dependency.
2. Given the prerequisites for AC-002, when its planned action is exercised, then the observable result must satisfy AC-002. Procedure: With a real local service, send authenticated and missing/invalid-token requests and attempt access from a non-loopback test client; retain binding, access-decision and permission evidence. Execute hostile cases only in an isolated test workspace.
3. Given the prerequisites for AC-003, when its planned action is exercised, then the observable result must satisfy AC-003. Procedure: Prepare harmless protected sentinel files and controlled network targets in a disposable environment; run permitted and forbidden actions with the actual restricted identity, inspect IPC listeners and inject a degraded fixture permission. Retain denied/allowed observations and startup decision.
4. Given the prerequisites for AC-004, when its planned action is exercised, then the observable result must satisfy AC-004. Procedure: Use disposable run data to inspect and copy local files, then delete only the disposable data; verify product access reflects the deletion and no cloud sync is required.
5. Given the prerequisites for AC-005, when its planned action is exercised, then the observable result must satisfy AC-005. Procedure: Load a configured Codex baseline and Searcher/Builder/Verifier aliases; inspect effective routing inputs and normal Codex aliases and access-gated experimental definitions against registered approval state. Redact credentials in retained evidence.
6. Given the prerequisites for AC-006, when its planned action is exercised, then the observable result must satisfy AC-006. Procedure: Set conflicting global/project values and observe the effective value used by real intake/runner consumers. Use explicitly supplied test settings, not product defaults invented by the test.
7. Given the prerequisites for AC-007, when its planned action is exercised, then the observable result must satisfy AC-007. Procedure: Supply an explicit finite test time/call limit, exercise below-bound and over-bound cases through the runner, and inspect the resulting stop event and recorded limit. Actual release configuration values remain separately registered.
8. Given the prerequisites for AC-008, when its planned action is exercised, then the observable result must satisfy AC-008. Procedure: Inspect effective configuration, startup dependencies and exposed services of the candidate; confirm excluded controls are not prerequisites or active Phase 1 features.
9. Given a declared profile and a configuration edit after run start, when consumers execute, then AC-009 preserves resolved components and records actual state; given a pre-declared Gate-disabled ablation, then AC-010 requires an evaluation label and excludes product acceptance/automatic standing changes.

### Edge Cases

Applicable rejection, unavailable-dependency, security, governance and phase-isolation cases are included in the ACs below. Do not assert unsupported recovery, arbitrary retry, unprovided numeric defaults or product behavior. Pending cases are recorded in Scope and Assumptions; unrelated preparation continues.

## Requirements

### Functional Requirements

- **FR-001** (§5.4.1): Local identity and preferences use the OS identity and local config.yaml; explicit domain expertise comes from intake. No sign-up service or persistent profile database is introduced.
- **FR-002** (§5.4.2): Local web/backend access is limited to loopback and requires the source-defined random session token; token storage follows the PRD permission requirement. Unauthorized requests are rejected.
- **FR-003** (§5.4.3 (lines 2144-2152); §2.9; §4.4.9 (lines 1678-1703)): Generated POC executes under a restricted unprivileged identity confined to authorized workspace/resources; forbidden host files, undeclared network/system effects and hidden fixtures remain inaccessible. Codex bridge uses source-required secured local IPC and no adapter TCP listener. Preserve POSIX hidden-fixture isolation: startup checks that the active Swarmflow runner cannot read the protected folder and halts on degraded boundaries. Actual identities, permission/custody/isolation mechanisms and checks remain PENDING_DESIGN.
- **FR-004** (§5.4.4): Settings, inputs and raw traces remain accessible through the local filesystem; manual inspection/export/deletion needs no cloud service or additional UI workflow.
- **FR-005** (§5.6 (lines 2188-2194); §5.6.1 (lines 2195-2203)): Declare Codex CLI and static role aliases in local configuration. Non-Codex endpoints/credential references are restricted to explicit development/evaluation profiles after approved access; before approval, definitions are mocked or non-executable. Experiments cannot change normal Phase 1 aliases or provision unapproved keys.
- **FR-006** (§5.6.2): Project-local settings override global defaults for the same configured setting; configured workspace paths, hardware constraints and supported document extensions are passed to consumers.
- **FR-007** (§5.6.3): Configured capsule time limits and invocation limits are enforced through connected runner/harness controls; a breached bound halts execution. Token/cost availability does not introduce mandatory monetary accounting.
- **FR-008** (§5.4.1, §5.4.2, §5.4.3, §5.4.4, §5.6.1, §5.6.2, §5.6.3, §5.6.4): The delivered configuration/security scope excludes the future capabilities listed in the source, including remote cluster configuration and cloud profile/security administration.

- **FR-009** (§5.6.5 (lines 2228-2248); §5.6 (lines 2188-2194)): An explicit development/evaluation profile selects or pins approved capsule versions/library snapshots, routing, Evaluator state, RSI participation, seed where supported and other approved evaluation controls. Resolve and freeze effective configuration at run start; later file changes cannot silently change active components. Supply actual effective state to the Run Bundle owned by M1-005.

- **FR-010** (§5.6.5 (lines 2228-2248)): Only pre-declared approved ablations may disable or replace approved components. A run replacing mandatory controls is explicitly marked development/evaluation or ablation, cannot qualify as a valid Phase 1 product run or M1 Definition-of-Done evidence, and cannot automatically change production capsule standing/activation. No end-user safety-control disabling, arbitrary component loading or dynamic active-production reconfiguration.

### Key Entities

Project/global configuration, local OS identity, authenticated session requests, declared execution permissions and configured capsule limits. Effective local configuration, authenticated local access and an execution boundary satisfying PRD permissions; schema, API, process and enforcement design PENDING_DESIGN. Exact cross-module semantics are owned by [M1-002 / M1-IF-002@r0](../../docs/tasks/M1/M1-002/TASK.md#4-embedded-cross-module-agreements).

## Success Criteria

### Measurable Outcomes

| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | §5.4.1 / FR-001 / US1 | Local identity and preferences use the OS identity and local config.yaml; explicit domain expertise comes from intake. No sign-up service or persistent profile database is introduced. | BLOCK |
| AC-002 | §5.4.2 / FR-002 / US1 | Local web/backend access is limited to loopback and requires the source-defined random session token; token storage follows the PRD permission requirement. Unauthorized requests are rejected. | BLOCK, BOUNDARY |
| AC-003 | PRD r2 §5.4.3 (lines 2144-2152); §2.9; §4.4.9 (lines 1678-1703) / FR-003 / US1 | Generated POC executes under a restricted unprivileged identity confined to authorized workspace/resources; forbidden host files, undeclared network/system effects and hidden fixtures remain inaccessible. Codex bridge uses source-required secured local IPC and no adapter TCP listener. Preserve POSIX hidden-fixture isolation: startup checks that the active Swarmflow runner cannot read the protected folder and halts on degraded boundaries. Actual identities, permission/custody/isolation mechanisms and checks remain PENDING_DESIGN. | BLOCK, BOUNDARY |
| AC-004 | §5.4.4 / FR-004 / US1 | Settings, inputs and raw traces remain accessible through the local filesystem; manual inspection/export/deletion needs no cloud service or additional UI workflow. | BLOCK |
| AC-005 | PRD r2 §5.6 (lines 2188-2194); §5.6.1 (lines 2195-2203) / FR-005 / US1 | Declare Codex CLI and static role aliases in local configuration. Non-Codex endpoints/credential references are restricted to explicit development/evaluation profiles after approved access; before approval, definitions are mocked or non-executable. Experiments cannot change normal Phase 1 aliases or provision unapproved keys. | BLOCK, BOUNDARY |
| AC-006 | §5.6.2 / FR-006 / US1 | Project-local settings override global defaults for the same configured setting; configured workspace paths, hardware constraints and supported document extensions are passed to consumers. | BLOCK, BOUNDARY |
| AC-007 | §5.6.3 / FR-007 / US1 | Configured capsule time limits and invocation limits are enforced through connected runner/harness controls; a breached bound halts execution. Token/cost availability does not introduce mandatory monetary accounting. | BLOCK, BOUNDARY |
| AC-008 | §5.4.1, §5.4.2, §5.4.3, §5.4.4, §5.6.1, §5.6.2, §5.6.3, §5.6.4 / FR-008 / US1 | The delivered configuration/security scope excludes the future capabilities listed in the source, including remote cluster configuration and cloud profile/security administration. | BLOCK |
| AC-009 | PRD r2 §5.6.5 (lines 2228-2248); §5.6 (lines 2188-2194) / FR-009 / US1 | An explicit development/evaluation profile selects or pins approved capsule versions/library snapshots, routing, Evaluator state, RSI participation, seed where supported and other approved evaluation controls. Resolve and freeze effective configuration at run start; later file changes cannot silently change active components. Supply actual effective state to the Run Bundle owned by M1-005. | BLOCK, BOUNDARY |
| AC-010 | PRD r2 §5.6.5 (lines 2228-2248) / FR-010 / US1 | Only pre-declared approved ablations may disable or replace approved components. A run replacing mandatory controls is explicitly marked development/evaluation or ablation, cannot qualify as a valid Phase 1 product run or M1 Definition-of-Done evidence, and cannot automatically change production capsule standing/activation. No end-user safety-control disabling, arbitrary component loading or dynamic active-production reconfiguration. | BLOCK, BOUNDARY |

Thresholds are the source-defined rules or explicitly supplied run/configuration values; example numbers are not new release targets. A check's test settings are not global product requirements.

## Scope and Assumptions

- Architecture reservation: [minimum inputs](../../docs/tasks/M1/ARCHITECTURE_MINIMUM_INPUTS.txt), items 1-7. Actual code/module/process boundaries, typed payloads/APIs/errors, coordination, storage/durability, security/settings mechanisms and executable test entry points remain PENDING_DESIGN; this spec states product outcomes only.

- Included: Local single-user settings, source-defined configuration precedence, static endpoint aliases, local-session authentication, restricted execution requirements and budget configuration.
- Excluded: Enterprise identity, multi-user profiles, cloud configuration/secrets, remote cluster declarations, dynamic billing and heavy container/hypervisor orchestration are outside this M1 scope.
- Consumed TASK agreements: [M1-IF-001@r0](../../docs/tasks/M1/M1-001/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../../docs/tasks/M1/M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../../docs/tasks/M1/M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../../docs/tasks/M1/M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../../docs/tasks/M1/M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-017@r0](../../docs/tasks/M1/M1-017/TASK.md#4-embedded-cross-module-agreements); [M1-IF-018@r0](../../docs/tasks/M1/M1-018/TASK.md#4-embedded-cross-module-agreements).
- Permitted models: Phase 1 uses the registered Codex CLI endpoint; an exact underlying model/version is captured when available from the actual configured service. No model family or proprietary version is invented. Phase 2 model candidates, where applicable, remain separately sourced.
- Architecture-dependent fields/interfaces/runtime paths: PENDING_DESIGN until Architecture is registered; source technical examples are constraints/inputs, not validated feasibility claims.
- Unresolved: ARCH-002: Architecture must define effective configuration schema, run-start resolution and frozen-configuration implementation, platform mapping, privilege boundaries and IPC/authentication mechanisms. Do not claim that a venv or privilege drop alone proves filesystem/network confinement.
- Unresolved: POLICY-002: Budget values and any unspecified defaults come from registered product/configuration inputs; no universal numeric thresholds are invented.
- Unresolved: IF-002: Fixture-isolation startup behavior must be connected with M1-018 provisioning and M1-017 startup; definition-time coordination is required before dependent checks, not completion of the entire RSI loop.
- System contribution: [M1-SYSTEM](../M1-SYSTEM-governed-research/spec.md) owns whole-system journeys. This spec retains its feature acceptance authority.

This file owns acceptance; plan.md owns implementation and verification methods, tasks.md owns progress and evidence.
