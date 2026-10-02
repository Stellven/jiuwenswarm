# Feature Specification: M1-017 - Installable local workstation and operational surfaces

**TASK**: [TASK](../../docs/tasks/M1/M1-017/TASK.md)
**Parent TASKS**: [M1 TASKS](../../docs/tasks/M1/TASKS.md)
**Revision / date**: r1 / 2026-10-01
**Feature Branch**: NOT_STARTED for implementation; documentation uses the existing checkout.
**Input**: [registered PRD r1](../../docs/tasks/M1/sources/PRD-Full.r1.txt), §5.1, §5.2, §5.3, §5.5; global §§1–2, §6. Architecture PENDING_SOURCE.
**Status**: Preparing; source-derived requirements populated, architecture-dependent contracts pending.

## User Scenarios & Testing

### User Story 1 - Installable local workstation and operational surfaces (Priority: P1)

Packaging/bootstrap, native CLI/Web/TUI, local trace and artifact access, static telemetry displays and tmux-based local session operation.

**Independent Test**: Exercise the source-defined behavior with controlled inputs, then connect its real providers/consumers; procedures and retained observations are in plan.md.

**Acceptance Scenarios**:

1. Given the prerequisites for AC-001, when its planned action is exercised, then the observable result must satisfy AC-001. Procedure: Drive a real small governed workflow through pass and blocking outcomes; compare displayed transitions and normalized labels with canonical harness/gate records.
2. Given the prerequisites for AC-002, when its planned action is exercised, then the observable result must satisfy AC-002. Procedure: Produce two distinguishable local runs and inspect their files/scorecards through the shell. Check attributable run/capsule references against the evidence provider rather than recomputing a second authoritative record.
3. Given the prerequisites for AC-003, when its planned action is exercised, then the observable result must satisfy AC-003. Procedure: Exercise one run with usage telemetry and one without reliable token/cost fields; inspect displayed values and completion behavior against the source-defined best-effort policy.
4. Given the prerequisites for AC-004, when its planned action is exercised, then the observable result must satisfy AC-004. Procedure: Inspect profiling events and active telemetry hooks during a run; distinguish prohibited continuous host sampling from declared experimental benchmark measurements.
5. Given the prerequisites for AC-005, when its planned action is exercised, then the observable result must satisfy AC-005. Procedure: On a fresh supported disposable workstation, execute the source-defined install/start entry points after binding real package and commands in plan; inspect directories, registry, doctor failures and one topic handoff. No package installation is executed during document preparation.
6. Given the prerequisites for AC-006, when its planned action is exercised, then the observable result must satisfy AC-006. Procedure: Prepare the source-required fixture inputs, run actual installer provisioning and inspect external-to-repository fixture placement and permission enforcement with the restricted runner. Optimization itself is not a prerequisite for this check.
7. Given the prerequisites for AC-007, when its planned action is exercised, then the observable result must satisfy AC-007. Procedure: Start the real local web service with a disposable session, submit a topic, follow canonical state changes and open the resulting report; exercise unauthorized access through M1-002 boundary checks.
8. Given the prerequisites for AC-008, when its planned action is exercised, then the observable result must satisfy AC-008. Procedure: Use a successful run and a deliberately invalid POC artifact, capture stdout and exit status; exact critical-fault code taxonomy is PENDING_DESIGN and must not be fabricated.
9. Given the prerequisites for AC-009, when its planned action is exercised, then the observable result must satisfy AC-009. Procedure: Exercise the native workbench on a real connected candidate, verify supplied branding assets and delivered Markdown, and inspect enabled controls for prohibited live mutation. Record UI evidence after applicable frontend instructions are read.
10. Given the prerequisites for AC-010, when its planned action is exercised, then the observable result must satisfy AC-010. Procedure: Inject a benchmark fault, enter the real native human session, inspect logs and explicitly abort/restart as supported; verify the prior failed record remains preserved.
11. Given the prerequisites for AC-011, when its planned action is exercised, then the observable result must satisfy AC-011. Procedure: Launch a test workflow/service in the actual supported tmux setup, detach and reattach, and observe continued attributable logs. Lack of tmux on a candidate is not a passing stub result.
12. Given the prerequisites for AC-012, when its planned action is exercised, then the observable result must satisfy AC-012. Procedure: Inspect built entry points, active listeners and enabled channels; confirm the source-blacklisted integrations are disabled and absent from release prerequisites.

### Edge Cases

Applicable rejection, unavailable-dependency, security, governance and phase-isolation cases are included in the ACs below. Do not assert unsupported recovery, arbitrary retry, unprovided numeric defaults or product behavior. Pending cases are recorded in Scope and Assumptions; unrelated preparation continues.

## Requirements

### Functional Requirements

- **FR-001** (§5.1.1): Native run-tree and terminal/local web views show actual node transitions, gate verdicts and halts without becoming authoritative state owners.
- **FR-002** (§5.1.2): Users can inspect append-only records, isolated run bundles and capsule Markdown/JSON scorecards produced through Data Foundations; no separate interactive trace database is required.
- **FR-003** (§5.1.3): Visibility exposes configured time/call limits and observed usage; unavailable token/cost telemetry is shown as unavailable and does not fail the run.
- **FR-004** (§5.1.4): Host profiling captures static OS/CPU-count/GPU facts once at run start, with no continuous host CPU/GPU/RAM sampling introduced by the shell.
- **FR-005** (§5.2.1): On source-supported macOS/Linux environments, package/bootstrap initializes input/POC/records locations, deploys admitted capsules and configures telemetry. Doctor checks provider authentication, paths and static DAG readiness; topic input reaches intake.
- **FR-006** (§5.2.1): Installer integration provisions the RSI workspace and hidden fixture sets using the canonical RSI policy and security boundary; restricted workflow execution cannot read hidden fixtures.
- **FR-007** (§5.2.2): Startup serves the native local web/status surface at the PRD loopback binding, initializes the local authenticated session and connects intake, live progress and final report access.
- **FR-008** (§5.3.1): CLI submits the user research string, displays node/tool/gate events and returns 0 for normal completion with defined non-success behavior on critical faults.
- **FR-009** (§5.3.2): Native web widgets provide intake, run observation and Markdown report retrieval with static AI4Research branding; users cannot edit the live DAG or scientific thresholds through this surface.
- **FR-010** (§5.3.3): Native TUI exposes failure inspection through human_session, with explicit human abort/correction/restart behavior and no automatic repair or silent resume.
- **FR-011** (§5.5.1): Local tmux sessions/panes support attach/detach and inspection of background workflow/services without remote session forwarding.
- **FR-012** (§5.1, §5.2.3, §5.3, §5.5.2): The delivered shell respects M1 exclusions: no bespoke interactive dashboard/workflow builder, desktop executable packaging, external chat/webhook listener, cloud portal or remote terminal synchronization.

### Key Entities

Research requests, effective configuration, local-session authorization, authoritative workflow events, trace bundles, reports, admitted capsule registry and RSI fixture setup inputs. Local workstation entry points, observable workflow/gate state, retrievable reports and evidence, package/bootstrap/doctor outcome; technical service APIs and routes beyond PRD examples await Architecture. Exact cross-module semantics are owned by [M1-017 / M1-IF-017@r0](../../docs/tasks/M1/M1-017/TASK.md#4-embedded-cross-module-agreements).

## Success Criteria

### Measurable Outcomes

| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | §5.1.1 / FR-001 / US1 | Native run-tree and terminal/local web views show actual node transitions, gate verdicts and halts without becoming authoritative state owners. | BLOCK, BOUNDARY |
| AC-002 | §5.1.2 / FR-002 / US1 | Users can inspect append-only records, isolated run bundles and capsule Markdown/JSON scorecards produced through Data Foundations; no separate interactive trace database is required. | BLOCK, BOUNDARY |
| AC-003 | §5.1.3 / FR-003 / US1 | Visibility exposes configured time/call limits and observed usage; unavailable token/cost telemetry is shown as unavailable and does not fail the run. | BLOCK, BOUNDARY |
| AC-004 | §5.1.4 / FR-004 / US1 | Host profiling captures static OS/CPU-count/GPU facts once at run start, with no continuous host CPU/GPU/RAM sampling introduced by the shell. | BLOCK, BOUNDARY |
| AC-005 | §5.2.1 / FR-005 / US1 | On source-supported macOS/Linux environments, package/bootstrap initializes input/POC/records locations, deploys admitted capsules and configures telemetry. Doctor checks provider authentication, paths and static DAG readiness; topic input reaches intake. | BLOCK, BOUNDARY |
| AC-006 | §5.2.1 / FR-006 / US1 | Installer integration provisions the RSI workspace and hidden fixture sets using the canonical RSI policy and security boundary; restricted workflow execution cannot read hidden fixtures. | BOUNDARY |
| AC-007 | §5.2.2 / FR-007 / US1 | Startup serves the native local web/status surface at the PRD loopback binding, initializes the local authenticated session and connects intake, live progress and final report access. | BLOCK, BOUNDARY |
| AC-008 | §5.3.1 / FR-008 / US1 | CLI submits the user research string, displays node/tool/gate events and returns 0 for normal completion with defined non-success behavior on critical faults. | BLOCK, BOUNDARY |
| AC-009 | §5.3.2 / FR-009 / US1 | Native web widgets provide intake, run observation and Markdown report retrieval with static AI4Research branding; users cannot edit the live DAG or scientific thresholds through this surface. | BLOCK, BOUNDARY |
| AC-010 | §5.3.3 / FR-010 / US1 | Native TUI exposes failure inspection through human_session, with explicit human abort/correction/restart behavior and no automatic repair or silent resume. | BLOCK, BOUNDARY |
| AC-011 | §5.5.1 / FR-011 / US1 | Local tmux sessions/panes support attach/detach and inspection of background workflow/services without remote session forwarding. | BLOCK, BOUNDARY |
| AC-012 | §5.1, §5.2.3, §5.3, §5.5.2 / FR-012 / US1 | The delivered shell respects M1 exclusions: no bespoke interactive dashboard/workflow builder, desktop executable packaging, external chat/webhook listener, cloud portal or remote terminal synchronization. | BLOCK |

Thresholds are the source-defined rules or explicitly supplied run/configuration values; example numbers are not new release targets. A check's test settings are not global product requirements.

## Scope and Assumptions

- Included: Packaging/bootstrap, native CLI/Web/TUI, local trace and artifact access, static telemetry displays and tmux-based local session operation.
- Excluded: Custom application dashboards/widgets, desktop binaries, cloud portals, continuous host sampling, external messaging adapters and distributed terminal management.
- Consumed TASK agreements: [M1-IF-001@r0](../../docs/tasks/M1/M1-001/TASK.md#4-embedded-cross-module-agreements); [M1-IF-002@r0](../../docs/tasks/M1/M1-002/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../../docs/tasks/M1/M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../../docs/tasks/M1/M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../../docs/tasks/M1/M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../../docs/tasks/M1/M1-007/TASK.md#4-embedded-cross-module-agreements); [M1-IF-008@r0](../../docs/tasks/M1/M1-008/TASK.md#4-embedded-cross-module-agreements); [M1-IF-016@r0](../../docs/tasks/M1/M1-016/TASK.md#4-embedded-cross-module-agreements); [M1-IF-018@r0](../../docs/tasks/M1/M1-018/TASK.md#4-embedded-cross-module-agreements).
- Permitted models: Phase 1 uses the registered Codex CLI endpoint; an exact underlying model/version is captured when available from the actual configured service. No model family or proprietary version is invented. Phase 2 model candidates, where applicable, remain separately sourced.
- Architecture-dependent fields/interfaces/runtime paths: PENDING_DESIGN until Architecture is registered; source technical examples are constraints/inputs, not validated feasibility claims.
- Unresolved: ARCH-017: Confirm existing native UI/TUI/CLI and packaging entry points, supported OS/runtime matrix, startup wiring and actual code/test paths before implementation.
- Unresolved: DESIGN-017: Branding asset sources, supported Linux versions and exact fault exit-code mapping are not supplied here; retain source-required behavior without inventing assets or numeric error codes.
- Unresolved: IF-017: Fixture provisioning belongs to installation integration using M1-018 requirements and M1-002 protection; do not require completed RSI optimization to define startup wiring.
- System contribution: [M1-SYSTEM](../M1-SYSTEM-governed-research/spec.md) owns whole-system journeys. This spec retains its feature acceptance authority.

This file owns acceptance; plan.md owns implementation and verification methods, tasks.md owns progress and evidence.

