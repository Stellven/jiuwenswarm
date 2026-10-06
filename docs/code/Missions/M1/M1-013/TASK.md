# TASK: M1-013 - Bounded POC construction and Builder

**Current baseline (2026-10-06):** [Latest verbatim PRD](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt) and [architecture decisions D1–D15](../../../../architecture/build-package/principles.md#decisions-and-source-amendments) apply to this task. Preserve existing AC/IF/work IDs; coding agents choose detailed schemas, APIs, code paths and checks in the native records. Delivery Phase 1 is the research baseline, Phase 2 is required offline RSI, and Phase 3 is expected dynamic integration: attempt available capabilities and record BLOCKED/INCOMPLETE dependencies; core-demo success does not complete all M1 work. Account identity/profile lifetime is distinct from local execution/workspace lifetime. Runtime evidence remains NOT_RUN.

PRD-derived preparation. This task records the requested initial document breakdown; it does not authorize or claim an implemented runtime. Read the complete registered source, not this extraction alone.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-013 / r3 / 2026-10-06 |
| Parent TASKS | [M1](../TASKS.md) |
| Executor / collaborators | Implementation executor UNASSIGNED; document preparation by Codex |
| Requested outcome and instruction/source | User request dated 2026-10-02: update existing TASK and Spec Kit documents from the latest attached PRD under Code SOP v2, filling source-supported content while reserving architecture decisions. Bounded product outcome: A researcher supplies an admitted immutable blueprint and local assets; Builder returns bounded executable artifacts and mechanical evidence for the Gate before empirical execution. |
| Included scope / exclusions | Phase 1 blueprint-to-POC assembly, local scaffolding, CodeSearch-assisted single-file patch, harness, mechanical checks and bundle. §4.9.1/.2 Phase 3 Code Mode experiment acceptance is owned by M1-019, excluded from this task's required ACs. Excludes autonomous repair, training/fine-tuning/checkpoints, production multi-file refactoring, analytical-output ownership, cloud deliverables and M2+ product integration. |
| PRD clause and architecture node references | [Current PRD](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt): §3.6 (all), §4.9 introduction and Phase 1/Future scope in §§4.9.1–4.9.5; §4.9.1/.2 Phase 3 allocated to M1-019; sequencing §6.7; shared §§1–2. Baseline r3 / 2026-10-06 / 232489 bytes / SHA256 6bd528778f0fd362eeff8bdbc76e60ae202fbe99cb879dd7fe24fd3b41762839. Architecture supplied in the current build package; detailed task bindings remain coding-agent work. |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / d9fe483ea64c273ef831886bfa83819f6d5bb21c observed for document preparation; dirty-tree status is not an executable candidate identity |
| Affected code/document paths | This TASK and docs/code/Missions/M1/M1-013/{spec.md,plan.md,tasks.md}; actual implementation/test/configuration paths PENDING_DESIGN |

No separate authorization/review/handoff card is created. Implementation and execution have not been performed by this document-preparation task.

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/M1/M1-013/ | One registered directory for this TASK |
| spec.md | [spec](spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](plan.md) | Behavior blocks, pending technical decisions and verification design |
| tasks.md | [tasks](tasks.md) | Work, progress and AC-to-evidence correspondence |
| evidence/ | docs/code/Missions/M1/M1-013/evidence/ (create actual run records when checks execute) | Actual run records/raw artifacts; none yet |
| Supporting artifacts | None generated; schemas/research/data models PENDING_DESIGN only if needed | Subordinate to TASK/spec/plan authorities |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [M1-012](../M1-012/TASK.md); [M1-IF-012@r0](../M1-012/TASK.md#4-embedded-cross-module-agreements) | Admitted immutable hypothesis, protocol and acceptance criteria | Definition before contract binding; actual admitted output before real construction | B01–B04; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-008](../M1-008/TASK.md); [M1-IF-008@r0](../M1-008/TASK.md#4-embedded-cross-module-agreements) | Explicitly supplied baseline, local workspace and validation resources | Local-real resources before workspace readiness and boundary verification | B01; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-009](../M1-009/TASK.md); [M1-IF-009@r0](../M1-009/TASK.md#4-embedded-cross-module-agreements) | Research Brief framework and runtime constraints | Definition before requirements generation; pinned run brief before execution | B01–B02; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-002](../M1-002/TASK.md); [M1-IF-002@r0](../M1-002/TASK.md#4-embedded-cross-module-agreements) | Authorized local workspace/environment and untrusted-code boundary | Architecture definition before path/sandbox binding; real environment before checks | B01–B04; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-003](../M1-003/TASK.md); [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements) | Admitted eligible capsule/runner semantics and pinned identity | Contract definition before binding; actual admitted capsule before governed invocation | All blocks; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-004](../M1-004/TASK.md); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements) | Static Phase 1 Codex execution route and independent reviewer provision | Route definition before model binding; real configured endpoint before live model evidence | Model-dependent blocks; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-005](../M1-005/TASK.md); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements) | Stage Evidence Bundle and durable run-bundle recording | Definition before evidence binding; actual store before boundary checks | All blocks; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-006](../M1-006/TASK.md); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements) | Bounded governed execution and halt/advance/human-session path | Definition before runner integration; connected runtime before boundary checks, not whole system completion | All blocks; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-007](../M1-007/TASK.md); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements) | Independent infrastructure admissibility and durable advancing decisions | Definition before handoff; actual Gate before connected release tests | Handoff and failure blocks; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-SYSTEM](../M1-SYSTEM/TASK.md) | Integrated candidate and complete research/required offline journeys | Final system verification follows relevant block and boundary readiness; full system acceptance is not a prerequisite for independent block preparation | T012; system contribution |

Definition-time agreements are needed before dependent design; runtime provider/consumer readiness is needed before real boundary checks. Neither means waiting for every provider task's final acceptance. r0 agreements remain preliminary until architecture binds them.

## 4. Embedded cross-module agreements

All seven [minimum architecture inputs](../ARCHITECTURE_MINIMUM_INPUTS.txt) remain reserved for task-level coding design. Source acceptance stays in spec.md; this section records provisional document allocation and leaves technical design unfilled.

### M1-IF-013 at r0
This is a **preliminary PRD semantic agreement**, not a finalized schema, API or architecture contract. Architecture supplied; task-level realization remains with the coding agent; representation and implementation are PENDING_DESIGN. Advancing the IF revision must update affected consumers.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provisional document allocation: provider M1-013; consumers M1-007, M1-014, M1-016, M1-SYSTEM. Actual module/process/API topology is PENDING_DESIGN (minimum inputs 1–2). |
| Purpose / source requirement | §3.6 (all), §4.9 introduction and Phase 1/Future scope in §§4.9.1–4.9.5; §4.9.1/.2 Phase 3 allocated to M1-019; sequencing §6.7; shared §§1–2; bounded bounded poc construction and builder handoff |
| Inputs: fields, types, units, required/optional, validation | PENDING_DESIGN — The coding agent defines payloads, types, validation, units and API/IPC handoff (minimum inputs 1–2). Product input obligations remain in spec.md. |
| Outputs: fields, types, units, semantics, guarantees | PENDING_DESIGN — The coding agent defines concrete outputs and technical guarantees (minimum inputs 2 and 4). Source-defined observable results remain in spec.md. |
| States and invariants | PENDING_DESIGN — The coding agent defines runtime state, transitions and coordination (minimum inputs 1–3). Product invariants remain in spec.md. |
| Errors, timeout, retry, cancellation | PENDING_DESIGN — The coding agent defines error structures, propagation, timeout/cancellation and duplicate handling (minimum inputs 2–3). Source failure/restart rules remain in spec.md. |
| Side effects and idempotency | PENDING_DESIGN — The coding agent defines effect enforcement, writes, partial-write recovery and repeated-call mechanics (minimum inputs 2–5). Source effect restrictions remain in spec.md. |
| Compatibility and migration | Provisional r0 identity retained. PENDING_DESIGN — The coding agent defines compatibility/migration representation (minimum inputs 1–2). Source acceptance is unchanged by realization choices; update consumers and invalidate affected evidence on material revision. |
| Machine-readable schema / source path | PENDING_DESIGN — No schema or application path is supplied. Architecture binds locations, schemas and environments (minimum inputs 1–2 and 6). |
| Provider/consumer verification responsibilities | PENDING_DESIGN — The coding agent defines actual check entry points and fault-injection seams (minimum input 7). Required behavioral AC/V intent and evidence mapping remain in native plan.md/tasks.md; no executed result is claimed. |
| Open agreement questions | M1-013-Q01, M1-013-Q02 in section 5; field-level schema/API/code paths remain explicitly pending. |

Consumed agreements: [M1-IF-012@r0](../M1-012/TASK.md#4-embedded-cross-module-agreements); [M1-IF-008@r0](../M1-008/TASK.md#4-embedded-cross-module-agreements); [M1-IF-009@r0](../M1-009/TASK.md#4-embedded-cross-module-agreements); [M1-IF-002@r0](../M1-002/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements). Registry admission/manual activation and shared infrastructure policies stay with their owning tasks.

Architecture reservation: [minimum inputs](../ARCHITECTURE_MINIMUM_INPUTS.txt), items 1-7, owns actual modules/code/processes, typed payload/API/error contracts, runtime coordination, storage/durability, security isolation, configuration realization and executable test entry points. These remain PENDING_DESIGN; no implementation mechanism is selected by this current PRD update.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| M1-013-Q01 / 2026-10-01 | Architecture is supplied in [the current design](../../../../architecture/build-package/README.md); exact schemas, operator ports, source paths, sandbox realization and command entry points are PENDING_DESIGN. | All blocks/checks and M1-IF-013 | Only affected bindings/implementation/checks; any changed source/IF invalidates affected rows and downstream evidence | UNASSIGNED; Register architecture and bind affected design; independent PRD/spec preparation continues. |
| M1-013-Q02 / 2026-10-01 | RESOLVED BY current PRD §§3.6.1/3.7.1: Builder declares/fixes dependencies without installing/discovering; Stage 3.7 installs only the frozen declaration. | AC-001/AC-005, B01/B04, M1-IF-013 and M1-014 provisioning | Only affected bindings/implementation/checks; any changed source/IF invalidates affected rows and downstream evidence | UNASSIGNED; Source distinction is resolved; Architecture binds provisioning without changing frozen dependencies. |
| PRD-R2 / 2026-10-02 | §3.6.1, §3.7.1, §4.6.4. Resolves dependency-stage ownership and applies mode-appropriate failure handling. | AC-001, AC-004; native plan/tasks correspondence; M1-IF-013@r0 | Invalidate affected earlier evidence if any; current candidate NOT_BUILT and runtime NOT_RUN. | UNASSIGNED; complete Implementation-dependent definitions before affected implementation. |

Progress belongs in native tasks.md. Register material source/IF changes in the parent allocation/index and affected native artifacts; there is currently no runtime evidence to invalidate.
