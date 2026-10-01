# Feature Specification: M1-016 - Research report and local lifecycle delivery
**TASK**: [M1-016](../../docs/tasks/M1/M1-016/TASK.md)
**Parent TASKS**: [M1](../../docs/tasks/M1/TASKS.md)
**Revision / date**: r1 / 2026-10-01
**Feature Branch**: ai4r_xiaoyang (document-preparation checkout; no feature branch created)
**Input**: [PRD-Full.r1](../../docs/tasks/M1/sources/PRD-Full.r1.txt), §3.9 (all); sequencing §6.9; shared §§1–2; architecture PENDING_SOURCE.
**Status**: Preparing — PRD-derived requirements populated; architecture binding pending, runtime NOT_RUN.
Local IDs are qualified by M1-016; this is the only AC authority for this task.

## User Scenarios & Testing
### User Story 1 - Research report and local lifecycle delivery (Priority: P1)
A researcher receives a local report and reproducible supporting artifacts, including a correctly executed experiment whose hypothesis failed.
**Independent Test**: Given an admitted scientific evaluation and its verified benchmark evidence, when report generation completes, then preserve the scientific conclusion, include methodology/results/limitations, package assets locally and expose the result through a supported local interface with a closed run trace.
**Acceptance Scenarios**:
1. Given source-conforming inputs and ready declared dependencies, when this bounded capability executes, then its artifacts and observable effects satisfy the ACs below and remain attributable to the run/capsule.
2. Given a prohibited action, invalid contract/evidence or source-defined failure, when execution or verification detects it, then preserve the failure and follow the shared halt/non-admission behavior; do not silently report completion or repair autonomously.
3. Given a connected consumer, when the provider submits an artifact/candidate, then respect the owning interface, governance boundary and version identity rather than infer success from a model response.

### Edge Cases
- Provide admitted positive and negative scientific results; inspect capsule/template and input binding. Confirm inadmissible evaluation cannot be used for normal delivery and audience requests do not cause custom format invention.
- Generate reports from positive and scientifically negative fixtures; compare every material statement and citation to frozen input evidence and inspect required sections. Check that no new experiment or excluded-format artifact was produced.
- Inspect output membership and references against source artifacts; verify that a missing required artifact remains a visible failure under shared governance and no external publication call occurs.
- Connect actual report/package, Harness, Data Foundations and one supported local display; observe readable artifacts and persisted completion. Exercise a delivery/persistence failure and verify no unsupported completed-success claim; inspect absence of external messages.
Architecture supplies representation, timeout/cancellation and recovery details; there is no assumed retry or resume mechanism. Source-specific numerical limits are listed in ACs only. No real-service claim is established by fixtures or stubs.

## Requirements
### Functional Requirements
- **FR-001** (§3.9 introduction; §3.9.1): Use report_capsule.md and the static sciencediscovery/report-writer Markdown structure to bind admitted Evaluation Verdict, verified Benchmark Payload and original Brief. Do not invent audience-specific structures or replace the scientific verdict with the Gate's infrastructure judgement.
- **FR-002** (§3.9.2; §§1.4,2.5): Produce structured Markdown with findings, empirical results and verified citations, explicitly including methodology, benchmark analysis and documented limitations. Preserve a valid negative scientific result. Do not generate new unsupported scientific claims, execute more experiments or emit excluded LaTeX/slides/interactive dashboards.
- **FR-003** (§3.9.3; §2.12): Consolidate Markdown report, POC scripts, environment configuration and raw empirical data into a single clean user output directory. Do not automatically publish to external repositories or community registries.
- **FR-004** (§3.9.4; §6.9; §§1.4,2.3,2.10): Transfer artifacts only to the sandboxed local user workspace, display the report through the supported native Web UI or TUI, and persist the completed execution trace in /swarmflows monitoring. Maintain governed lifecycle closure; no external channel notifications or attachments.
### Key Entities
Evaluation_Verdict.json; Benchmark_Payload.json; Research_Brief.json; static report-writer Markdown template; research_report.md; POC/environment/raw-data artifact package; completed run trace. See [M1-IF-016@r0](../../docs/tasks/M1/M1-016/TASK.md#4-embedded-cross-module-agreements) for canonical preliminary semantic handoff; exact schemas are PENDING_DESIGN.

## Success Criteria
### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | PRD r1 §3.9 introduction; §3.9.1 / FR-001 / US1 | Use report_capsule.md and the static sciencediscovery/report-writer Markdown structure to bind admitted Evaluation Verdict, verified Benchmark Payload and original Brief. Do not invent audience-specific structures or replace the scientific verdict with the Gate's infrastructure judgement. | BLOCK |
| AC-002 | PRD r1 §3.9.2; §§1.4,2.5 / FR-002 / US1 | Produce structured Markdown with findings, empirical results and verified citations, explicitly including methodology, benchmark analysis and documented limitations. Preserve a valid negative scientific result. Do not generate new unsupported scientific claims, execute more experiments or emit excluded LaTeX/slides/interactive dashboards. | BLOCK |
| AC-003 | PRD r1 §3.9.3; §2.12 / FR-003 / US1 | Consolidate Markdown report, POC scripts, environment configuration and raw empirical data into a single clean user output directory. Do not automatically publish to external repositories or community registries. | BLOCK |
| AC-004 | PRD r1 §3.9.4; §6.9; §§1.4,2.3,2.10 / FR-004 / US1 | Transfer artifacts only to the sandboxed local user workspace, display the report through the supported native Web UI or TUI, and persist the completed execution trace in /swarmflows monitoring. Maintain governed lifecycle closure; no external channel notifications or attachments. | BLOCK, BOUNDARY |
System-level end-to-end acceptance is owned by M1-SYSTEM, not copied into this task. Every row has block/check/work correspondence in plan.md and tasks.md; no runtime result is implied.

## Scope and Assumptions
- Included / excluded scope: Produce a standardized Markdown report from admitted scientific findings and verified evidence, package local artifacts and close the observed lifecycle. Excludes new scientific claims, code execution, dynamic audience profiling, alternate publishing formats, cloud/external publication and outbound notifications.
- Shared boundaries: local single-user scientific lane; fixed Phase 1 DAG and authorized tools/resources; frozen scientific protocol; separate scientific result and infrastructure release; authoritative system evidence; no automatic repair, live RSI, model training, external publication or distributed/cloud baseline execution (§§1–2). Shared enforcement ACs belong to their owning tasks; this task's observable compliance is covered above.
- Consumed TASK agreements: [M1-IF-015@r0](../../docs/tasks/M1/M1-015/TASK.md#4-embedded-cross-module-agreements); [M1-IF-014@r0](../../docs/tasks/M1/M1-014/TASK.md#4-embedded-cross-module-agreements); [M1-IF-009@r0](../../docs/tasks/M1/M1-009/TASK.md#4-embedded-cross-module-agreements); [M1-IF-013@r0](../../docs/tasks/M1/M1-013/TASK.md#4-embedded-cross-module-agreements); [M1-IF-017@r0](../../docs/tasks/M1/M1-017/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../../docs/tasks/M1/M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../../docs/tasks/M1/M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../../docs/tasks/M1/M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../../docs/tasks/M1/M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../../docs/tasks/M1/M1-007/TASK.md#4-embedded-cross-module-agreements).
- Permitted models: Phase 1 uses the single static Codex CLI route through M1-001/M1-004; role/consumer needs do not authorize a new model pool. Record actual provider/model/version when available; no guessed model identifier.
- Assumptions and unresolved source inputs: M1-016-Q01: Architecture is PENDING_SOURCE; report template port/version, output-path mapping, local-surface API, final gate/closure wiring and repeat-delivery semantics are PENDING_DESIGN. Resolution: Bind exact architecture/components without changing report scope or gate invariants; independent PRD preparation continues.
- Architecture boundary: exact payload types, APIs, IPC, class/module design, process topology, storage paths and security realization remain PENDING_DESIGN pending the architecture source. Source-given names/constraints above are requirements, not proof of implementation.
- System tasks: [M1-SYSTEM](../../docs/tasks/M1/M1-SYSTEM/TASK.md) consumes this task's current candidate, block/boundary evidence and source constraints for complete journeys; its acceptance remains separate.

This is the AC authority. Technical realization stays in plan.md; progress/results stay in tasks.md.

