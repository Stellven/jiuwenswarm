# TASK: M1-014 - Scientific baseline and treatment execution
PRD-derived preparation. This task records the requested initial document breakdown; it does not authorize or claim an implemented runtime. Read the complete registered source, not this extraction alone.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-014 / r2 / 2026-10-02 |
| Parent TASKS | [M1](../TASKS.md) |
| Executor / collaborators | Implementation executor UNASSIGNED; document preparation by Codex |
| Requested outcome and instruction/source | User request dated 2026-10-02: update existing TASK and Spec Kit documents from the latest attached PRD under Code SOP v2, filling source-supported content while reserving architecture decisions. Bounded product outcome: A researcher receives actual comparative measurements from the fixed experiment rather than model-invented results. |
| Included scope / exclusions | Execute the admitted POC locally, collect comparable live baseline/treatment measurements and preserve raw evidence. Excludes isolated treatment-only scoring, dependency-conflict repair, scientific verdict assignment, external cloud execution and undeclared dataset acquisition. |
| PRD clause and architecture node references | [PRD-Full.r2](../sources/PRD-Full.r2.txt): §3.7 (all); sequencing §6.8; shared §§1–2. Baseline r2 / 2026-10-02 / 200082 bytes / SHA256 44928035205BDEBAE205D2B458BD438C2C6E0103E4EB2D834C6A93E1CFA37294. Architecture source/node IDs: PENDING_SOURCE. |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / d9fe483ea64c273ef831886bfa83819f6d5bb21c observed for document preparation; dirty-tree status is not an executable candidate identity |
| Affected code/document paths | This TASK and specs/M1-014-scientific-benchmarking/{spec.md,plan.md,tasks.md}; actual implementation/test/configuration paths PENDING_DESIGN |

No separate authorization/review/handoff card is created. Implementation and execution have not been performed by this document-preparation task.

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | specs/M1-014-scientific-benchmarking/ | One registered directory for this TASK |
| spec.md | [spec](../../../../specs/M1-014-scientific-benchmarking/spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](../../../../specs/M1-014-scientific-benchmarking/plan.md) | Behavior blocks, pending technical decisions and verification design |
| tasks.md | [tasks](../../../../specs/M1-014-scientific-benchmarking/tasks.md) | Work, progress and AC-to-evidence correspondence |
| evidence/ | specs/M1-014-scientific-benchmarking/evidence/ (create actual run records when checks execute) | Actual run records/raw artifacts; none yet |
| Supporting artifacts | None generated; schemas/research/data models PENDING_DESIGN only if needed | Subordinate to TASK/spec/plan authorities |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [M1-013](../M1-013/TASK.md); [M1-IF-013@r0](../M1-013/TASK.md#4-embedded-cross-module-agreements) | Admitted POC bundle and build evidence | Definition before payload binding; actual gate-admitted bundle before empirical execution | B01–B03; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-012](../M1-012/TASK.md); [M1-IF-012@r0](../M1-012/TASK.md#4-embedded-cross-module-agreements) | Frozen baseline/data/variables/procedure/threshold contract | Definition before configuration binding; immutable active-run protocol before execution | B02; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-002](../M1-002/TASK.md); [M1-IF-002@r0](../M1-002/TASK.md#4-embedded-cross-module-agreements) | Local authorized unprivileged runtime and resource boundary | Architecture before environment implementation; verified actual boundary before generated-code execution | B01–B02; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-003](../M1-003/TASK.md); [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements) | Admitted eligible capsule/runner semantics and pinned identity | Contract definition before binding; actual admitted capsule before governed invocation | All blocks; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-004](../M1-004/TASK.md); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements) | Static Phase 1 Codex execution route and independent reviewer provision | Route definition before model binding; real configured endpoint before live model evidence | Model-dependent blocks; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-005](../M1-005/TASK.md); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements) | Stage Evidence Bundle and durable run-bundle recording | Definition before evidence binding; actual store before boundary checks | All blocks; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-006](../M1-006/TASK.md); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements) | Bounded governed execution and halt/advance/human-session path | Definition before runner integration; connected runtime before boundary checks, not whole system completion | All blocks; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-007](../M1-007/TASK.md); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements) | Independent infrastructure admissibility and durable advancing decisions | Definition before handoff; actual Gate before connected release tests | Handoff and failure blocks; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-SYSTEM](../M1-SYSTEM/TASK.md) | Integrated candidate and complete research/required offline journeys | Final system verification follows relevant block and boundary readiness; full system acceptance is not a prerequisite for independent block preparation | T010; system contribution |

Definition-time agreements are needed before dependent design; runtime provider/consumer readiness is needed before real boundary checks. Neither means waiting for every provider task's final acceptance. r0 agreements remain preliminary until architecture binds them.

## 4. Embedded cross-module agreements

All seven [minimum architecture inputs](../ARCHITECTURE_MINIMUM_INPUTS.txt) remain reserved for Architecture. Source acceptance stays in spec.md; this section records provisional document allocation and leaves technical design unfilled.

### M1-IF-014 at r0
This is a **preliminary PRD semantic agreement**, not a finalized schema, API or architecture contract. Architecture source is PENDING_SOURCE; representation and implementation are PENDING_DESIGN. Advancing the IF revision must update affected consumers.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provisional document allocation: provider M1-014; consumers M1-007, M1-015, M1-016, M1-SYSTEM. Actual module/process/API topology is PENDING_DESIGN (minimum inputs 1–2). |
| Purpose / source requirement | §3.7 (all); sequencing §6.8; shared §§1–2; bounded scientific baseline and treatment execution handoff |
| Inputs: fields, types, units, required/optional, validation | PENDING_DESIGN — Architecture owns payloads, types, validation, units and API/IPC handoff (minimum inputs 1–2). Product input obligations remain in spec.md. |
| Outputs: fields, types, units, semantics, guarantees | PENDING_DESIGN — Architecture owns concrete outputs and technical guarantees (minimum inputs 2 and 4). Source-defined observable results remain in spec.md. |
| States and invariants | PENDING_DESIGN — Architecture owns runtime state, transitions and coordination (minimum inputs 1–3). Product invariants remain in spec.md. |
| Errors, timeout, retry, cancellation | PENDING_DESIGN — Architecture owns error structures, propagation, timeout/cancellation and duplicate handling (minimum inputs 2–3). Source failure/restart rules remain in spec.md. |
| Side effects and idempotency | PENDING_DESIGN — Architecture owns effect enforcement, writes, partial-write recovery and repeated-call mechanics (minimum inputs 2–5). Source effect restrictions remain in spec.md. |
| Compatibility and migration | Provisional r0 identity retained. PENDING_DESIGN — Architecture owns compatibility/migration representation (minimum inputs 1–2). Source acceptance is unchanged by realization choices; update consumers and invalidate affected evidence on material revision. |
| Machine-readable schema / source path | PENDING_DESIGN — No schema or application path is supplied. Architecture binds locations, schemas and environments (minimum inputs 1–2 and 6). |
| Provider/consumer verification responsibilities | PENDING_DESIGN — Architecture owns actual check entry points and fault-injection seams (minimum input 7). Required behavioral AC/V intent and evidence mapping remain in native plan.md/tasks.md; no executed result is claimed. |
| Open agreement questions | M1-014-Q01, M1-014-Q02 in section 5; field-level schema/API/code paths remain explicitly pending. |

Consumed agreements: [M1-IF-013@r0](../M1-013/TASK.md#4-embedded-cross-module-agreements); [M1-IF-012@r0](../M1-012/TASK.md#4-embedded-cross-module-agreements); [M1-IF-002@r0](../M1-002/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements). Registry admission/manual activation and shared infrastructure policies stay with their owning tasks.

Architecture reservation: [minimum inputs](../ARCHITECTURE_MINIMUM_INPUTS.txt), items 1-7, owns actual modules/code/processes, typed payload/API/error contracts, runtime coordination, storage/durability, security isolation, configuration realization and executable test entry points. These remain PENDING_DESIGN; no implementation mechanism is selected by this PRD r2 update.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| M1-014-Q01 / 2026-10-01 | Architecture, exact metric/payload schemas, unprivileged execution realization and entry points are pending. | All blocks/checks and M1-IF-014 | Only affected bindings/implementation/checks; any changed source/IF invalidates affected rows and downstream evidence | UNASSIGNED; Register architecture; bind implementations and fixture versions before dependent execution. |
| M1-014-Q02 / 2026-10-01 | RESOLVED BY PRD r2 §§3.6.1/3.7.1: Builder freezes declarations; Stage 3.7 installs only the unchanged set. | AC-001, B01, M1-IF-013/014 | Only affected bindings/implementation/checks; any changed source/IF invalidates affected rows and downstream evidence | UNASSIGNED; Source distinction is resolved; bind unprivileged provisioning through Architecture without changing declarations. |
| PRD-R2 / 2026-10-02 | §3.7.1, §4.6.4. Resolves r1 installation question and forbids dependency-set mutation. | AC-001; native plan/tasks correspondence; M1-IF-014@r0 | Invalidate affected earlier evidence if any; current candidate NOT_BUILT and runtime NOT_RUN. | UNASSIGNED; complete Architecture-dependent definitions before affected implementation. |

Progress belongs in native tasks.md. Register material source/IF changes in the parent allocation/index and affected native artifacts; there is currently no runtime evidence to invalidate.
