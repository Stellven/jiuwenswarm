# TASK: M1-016 - Research report and local lifecycle delivery
PRD-derived preparation. This task records the requested initial document breakdown; it does not authorize or claim an implemented runtime. Read the complete registered source, not this extraction alone.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-016 / r2 / 2026-10-02 |
| Parent TASKS | [M1](../TASKS.md) |
| Executor / collaborators | Implementation executor UNASSIGNED; document preparation by Codex |
| Requested outcome and instruction/source | User request: build initial TASK and Spec Kit documents from PRD Full under Code SOP v2, filling source-supported content while reserving architecture decisions. Bounded product outcome: A researcher receives a local report and reproducible supporting artifacts, including a correctly executed experiment whose hypothesis failed. |
| Included scope / exclusions | Produce a standardized Markdown report from admitted scientific findings and verified evidence, package local artifacts and close the observed lifecycle. Excludes new scientific claims, code execution, dynamic audience profiling, alternate publishing formats, cloud/external publication and outbound notifications. |
| PRD clause and architecture node references | [PRD-Full.r2](../sources/PRD-Full.r2.txt): §3.9 (all); sequencing §6.9; shared §§1–2. Baseline r1 / 2026-10-01 / 200082 bytes / SHA256 44928035205BDEBAE205D2B458BD438C2C6E0103E4EB2D834C6A93E1CFA37294. Architecture source/node IDs: PENDING_SOURCE. |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / d9fe483ea64c273ef831886bfa83819f6d5bb21c observed for document preparation; dirty-tree status is not an executable candidate identity |
| Affected code/document paths | This TASK and docs/code/Missions/M1/M1-016/{spec.md,plan.md,tasks.md}; actual implementation/test/configuration paths PENDING_DESIGN |

No separate authorization/review/handoff card is created. Implementation and execution have not been performed by this document-preparation task.

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/M1/M1-016/ | One registered directory for this TASK |
| spec.md | [spec](spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](plan.md) | Behavior blocks, pending technical decisions and verification design |
| tasks.md | [tasks](tasks.md) | Work, progress and AC-to-evidence correspondence |
| evidence/ | docs/code/Missions/M1/M1-016/evidence/ (create actual run records when checks execute) | Actual run records/raw artifacts; none yet |
| Supporting artifacts | None generated; schemas/research/data models PENDING_DESIGN only if needed | Subordinate to TASK/spec/plan authorities |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [M1-015](../M1-015/TASK.md); [M1-IF-015@r0](../M1-015/TASK.md#4-embedded-cross-module-agreements) | Admitted scientific verdict with constraints and follow-ups | Actual admitted output before report synthesis; definition before fixture binding | B01–B03; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-014](../M1-014/TASK.md); [M1-IF-014@r0](../M1-014/TASK.md#4-embedded-cross-module-agreements) | Verified benchmark payload and raw data | Actual run evidence before report analysis and packaging | B01–B02; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-009](../M1-009/TASK.md); [M1-IF-009@r0](../M1-009/TASK.md#4-embedded-cross-module-agreements) | Original Research Brief | Pinned run brief before synthesis | B01; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-013](../M1-013/TASK.md); [M1-IF-013@r0](../M1-013/TASK.md#4-embedded-cross-module-agreements) | POC scripts and environment configuration | Actual artifact bundle before deliverable packaging | B02; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-017](../M1-017/TASK.md); [M1-IF-017@r0](../M1-017/TASK.md#4-embedded-cross-module-agreements) | Supported local result display/access surface | Surface agreement for boundary definition; minimal actual surface before display verification, not whole shell completion | B03; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-003](../M1-003/TASK.md); [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements) | Admitted eligible capsule/runner semantics and pinned identity | Contract definition before binding; actual admitted capsule before governed invocation | All blocks; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-004](../M1-004/TASK.md); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements) | Static Phase 1 Codex execution route and independent reviewer provision | Route definition before model binding; real configured endpoint before live model evidence | Model-dependent blocks; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-005](../M1-005/TASK.md); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements) | Stage Evidence Bundle and durable run-bundle recording | Definition before evidence binding; actual store before boundary checks | All blocks; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-006](../M1-006/TASK.md); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements) | Bounded governed execution and halt/advance/human-session path | Definition before runner integration; connected runtime before boundary checks, not whole system completion | All blocks; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-007](../M1-007/TASK.md); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements) | Independent infrastructure admissibility and durable advancing decisions | Definition before handoff; actual Gate before connected release tests | Handoff and failure blocks; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-SYSTEM](../M1-SYSTEM/TASK.md) | Integrated candidate and complete research/required offline journeys | Final system verification follows relevant block and boundary readiness; full system acceptance is not a prerequisite for independent block preparation | T010; system contribution |

Definition-time agreements are needed before dependent design; runtime provider/consumer readiness is needed before real boundary checks. Neither means waiting for every provider task's final acceptance. r0 agreements remain preliminary until architecture binds them.

## 4. Embedded cross-module agreements

All seven [minimum architecture inputs](../ARCHITECTURE_MINIMUM_INPUTS.txt) remain reserved for Architecture. Source acceptance stays in spec.md; this section records provisional document allocation and leaves technical design unfilled.

### M1-IF-016 at r0
This is a **preliminary PRD semantic agreement**, not a finalized schema, API or architecture contract. Architecture source is PENDING_SOURCE; representation and implementation are PENDING_DESIGN. Advancing the IF revision must update affected consumers.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provisional document allocation: provider M1-016; consumers M1-017, M1-SYSTEM. Actual module/process/API topology is PENDING_DESIGN (minimum inputs 1–2). |
| Purpose / source requirement | §3.9 (all); sequencing §6.9; shared §§1–2; bounded research report and local lifecycle delivery handoff |
| Inputs: fields, types, units, required/optional, validation | PENDING_DESIGN — Architecture owns payloads, types, validation, units and API/IPC handoff (minimum inputs 1–2). Product input obligations remain in spec.md. |
| Outputs: fields, types, units, semantics, guarantees | PENDING_DESIGN — Architecture owns concrete outputs and technical guarantees (minimum inputs 2 and 4). Source-defined observable results remain in spec.md. |
| States and invariants | PENDING_DESIGN — Architecture owns runtime state, transitions and coordination (minimum inputs 1–3). Product invariants remain in spec.md. |
| Errors, timeout, retry, cancellation | PENDING_DESIGN — Architecture owns error structures, propagation, timeout/cancellation and duplicate handling (minimum inputs 2–3). Source failure/restart rules remain in spec.md. |
| Side effects and idempotency | PENDING_DESIGN — Architecture owns effect enforcement, writes, partial-write recovery and repeated-call mechanics (minimum inputs 2–5). Source effect restrictions remain in spec.md. |
| Compatibility and migration | Provisional r0 identity retained. PENDING_DESIGN — Architecture owns compatibility/migration representation (minimum inputs 1–2). Source acceptance is unchanged by realization choices; update consumers and invalidate affected evidence on material revision. |
| Machine-readable schema / source path | PENDING_DESIGN — No schema or application path is supplied. Architecture binds locations, schemas and environments (minimum inputs 1–2 and 6). |
| Provider/consumer verification responsibilities | PENDING_DESIGN — Architecture owns actual check entry points and fault-injection seams (minimum input 7). Required behavioral AC/V intent and evidence mapping remain in native plan.md/tasks.md; no executed result is claimed. |
| Open agreement questions | M1-016-Q01 in section 5; field-level schema/API/code paths remain explicitly pending. |

Consumed agreements: [M1-IF-015@r0](../M1-015/TASK.md#4-embedded-cross-module-agreements); [M1-IF-014@r0](../M1-014/TASK.md#4-embedded-cross-module-agreements); [M1-IF-009@r0](../M1-009/TASK.md#4-embedded-cross-module-agreements); [M1-IF-013@r0](../M1-013/TASK.md#4-embedded-cross-module-agreements); [M1-IF-017@r0](../M1-017/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements). Registry admission/manual activation and shared infrastructure policies stay with their owning tasks.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| M1-016-Q01 / 2026-10-01 | Architecture is PENDING_SOURCE; report template port/version, output-path mapping, local-surface API, final gate/closure wiring and repeat-delivery semantics are PENDING_DESIGN. | All blocks/checks and M1-IF-016 | Only affected bindings/implementation/checks; any changed source/IF invalidates affected rows and downstream evidence | UNASSIGNED; Bind exact architecture/components without changing report scope or gate invariants; independent PRD preparation continues. |
| DOC-R2 / 2026-10-02 | Latest PRD capture r2 replaces the active r1 product baseline. Rebase clauses and preserve stable AC/IF identities; all technical agreement fields remain reserved for Architecture. | spec/plan/tasks r2; provisional M1-IF-016@r0 | No runtime evidence exists; affected future checks remain NOT_RUN. | UNASSIGNED; bind Architecture only before dependent realization |

Progress belongs in native tasks.md. Register material source/IF changes in the parent allocation/index and affected native artifacts; there is currently no runtime evidence to invalidate.
