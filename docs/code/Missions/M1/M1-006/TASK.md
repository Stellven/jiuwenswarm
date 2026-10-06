# TASK: M1-006 - Governed harness and fixed research DAG

**Current baseline (2026-10-06):** [Latest verbatim PRD](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt) and [architecture decisions D1–D15](../../../../architecture/build-package/principles.md#decisions-and-source-amendments) apply to this task. Preserve existing AC/IF/work IDs; coding agents choose detailed schemas, APIs, code paths and checks in the native records. Delivery Phase 1 is the research baseline, Phase 2 is required offline RSI, and Phase 3 is expected dynamic integration: attempt available capabilities and record BLOCKED/INCOMPLETE dependencies; core-demo success does not complete all M1 work. Account identity/profile lifetime is distinct from local execution/workspace lifetime. Runtime evidence remains NOT_RUN.


## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-006 / r3 / 2026-10-06 |
| Parent TASKS | [M1](../TASKS.md) |
| Executor / collaborators | UNASSIGNED for implementation; Codex prepares documents at the user's request |
| Requested outcome and instruction/source | Prepare English TASK/Spec Kit documents from PRD Full. Current action scope: documentation only; no application changes, runtime tests or commits. Future product outcome: Use native Swarmflow for local lifecycle, immutable sequential scheduling, bounded runner subprocess dispatch, evidence handoff, gate-locked advancement and explicit human failure handling; inject Research_Brief parameters into the fixed DAG. |
| Included scope / exclusions | Included: Use native Swarmflow for local lifecycle, immutable sequential scheduling, bounded runner subprocess dispatch, evidence handoff, gate-locked advancement and explicit human failure handling; inject Research_Brief parameters into the fixed DAG. Excluded: No Auto Harness recursive sub-runs; autonomous decomposition, live graph restructuring, parallel hypotheses/batching, remote/cloud fleets or external container dispatch, message brokers/leases/quotas; no automatic repair/requeue or complex partial rewind. Isolated Cluster/Leader/dynamic-planning tracks belong to M1-019. |
| PRD clause and architecture node references | [Registered PRD](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt): current PRD (2026-10-02), SHA256 6bd528778f0fd362eeff8bdbc76e60ae202fbe99cb879dd7fe24fd3b41762839, 232489 bytes; §4.6, §4.6.1, §4.6.2 Phase 1, §4.6.3, §4.6.4; §4.6.5 excluded; §4.8, §4.8.1, §4.8.2, §4.8.3 Phase 1; sequencing §6.4–§6.5; global §1.3–§1.6 and §2.1–§2.12 apply. Architecture: [current design](../../../../architecture/build-package/README.md); detailed realization belongs to the coding agent; architecture nodes are not invented. |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / d9fe483ea64c273ef831886bfa83819f6d5bb21c; existing checkout; no tested runtime candidate prepared |
| Affected code/document paths | docs/code/Missions/M1/M1-006/TASK.md; docs/code/Missions/M1/M1-006/spec.md, plan.md, tasks.md. Application/test/configuration paths PENDING_DESIGN after architecture and existing-code inspection. |

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/M1/M1-006/ relative to repository root | Exactly one feature for this TASK |
| spec.md | [spec](spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](plan.md) | Behavior blocks, future design and verification procedures |
| tasks.md | [tasks](tasks.md) | Work, progress and acceptance/evidence correspondence |
| evidence/ | docs/code/Missions/M1/M1-006/evidence/ (create on actual verification) | Actual candidate run records/raw artifacts; none generated during preparation |
| Supporting artifacts | None | No parallel cards or invented schemas; future support remains subordinate |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [M1-003](../M1-003/TASK.md) / M1-IF-003@r0 | Named capsule contracts, admitted bindings and runner output/time observations | Definition first; actual runner before dispatch checks | B01–B04; T001 and applicable boundary work |
| [M1-005](../M1-005/TASK.md) / M1-IF-005@r0 | Run snapshots/evidence and durable decision visibility | Definition then actual persistence before gate-lock acceptance | B01/B03/B04; T001 and applicable boundary work |
| [M1-007](../M1-007/TASK.md) / M1-IF-007@r0 | Advancing/blocking verdict meanings and actual Gate | Definition before scheduling; real Gate before V90, not full Gate-task completion | B02–B04; T001 and applicable boundary work |
| [M1-009](../M1-009/TASK.md) / M1-IF-009@r0 | Validated Research_Brief objective/hardware/metric meaning | Definition before graph binding; real compiler for full journey, not minimal A/Gate/B | B05; T001 and applicable boundary work |
| [M1-002](../M1-002/TASK.md) / M1-IF-002@r0 | Local config and restricted execution context | Runtime before execution/security checks | B01/B03/B04; T001 and applicable boundary work |
| Master architecture / PENDING_SOURCE | Actual technical boundaries and implementation/check paths | Required only before affected implementation/real boundary checks; independent PRD preparation continues | T001 and unresolved technical work |
| [M1-SYSTEM](../M1-SYSTEM/TASK.md) | Candidate-wide journey verification | Final integration; not a prerequisite for block definitions or isolated checks | System contribution work in tasks.md |

Definition dependencies do not require a fully VERIFIED peer TASK. Define capsule/provider/evidence/gate semantics first; connect their implemented blocks later. This avoids treating runner -> Gate -> reviewer -> capsule as a circular sequence of whole-task completion.

## 4. Embedded cross-module agreements

All seven [minimum architecture inputs](../ARCHITECTURE_MINIMUM_INPUTS.txt) remain reserved for task-level coding design. Source acceptance stays in spec.md; this section records provisional document allocation and leaves technical design unfilled.

### M1-IF-006 at r0
**Provisional PRD-semantic agreement.** This is not a final architecture, API or schema. Fields and rules explicitly present in the PRD are retained; unspecified technical details remain PENDING_DESIGN.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provisional document allocation: provider M1-006; consumers M1-002, M1-003, M1-005, M1-007, M1-008, M1-009, M1-010, M1-011, M1-012, M1-013, M1-014, M1-015, M1-016, M1-017, M1-019, M1-SYSTEM. Actual module/process/API topology is PENDING_DESIGN (minimum inputs 1–2). |
| Purpose / source requirement | Use native Swarmflow for local lifecycle, immutable sequential scheduling, bounded runner subprocess dispatch, evidence handoff, gate-locked advancement and explicit human failure handling; inject Research_Brief parameters into the fixed DAG. Source: §4.6, §4.6.1, §4.6.2 Phase 1, §4.6.3, §4.6.4; §4.6.5 excluded; §4.8, §4.8.1, §4.8.2, §4.8.3 Phase 1; sequencing §6.4–§6.5. |
| Inputs: fields, types, units, required/optional, validation | PENDING_DESIGN — The coding agent defines payloads, types, validation, units and API/IPC handoff (minimum inputs 1–2). Product input obligations remain in spec.md. |
| Outputs: fields, types, units, semantics, guarantees | PENDING_DESIGN — The coding agent defines concrete outputs and technical guarantees (minimum inputs 2 and 4). Source-defined observable results remain in spec.md. |
| States and invariants | PENDING_DESIGN — The coding agent defines runtime state, transitions and coordination (minimum inputs 1–3). Product invariants remain in spec.md. |
| Errors, timeout, retry, cancellation | PENDING_DESIGN — The coding agent defines error structures, propagation, timeout/cancellation and duplicate handling (minimum inputs 2–3). Source failure/restart rules remain in spec.md. |
| Side effects and idempotency | PENDING_DESIGN — The coding agent defines effect enforcement, writes, partial-write recovery and repeated-call mechanics (minimum inputs 2–5). Source effect restrictions remain in spec.md. |
| Compatibility and migration | Provisional r0 identity retained. PENDING_DESIGN — The coding agent defines compatibility/migration representation (minimum inputs 1–2). Source acceptance is unchanged by realization choices; update consumers and invalidate affected evidence on material revision. |
| Machine-readable schema / source path | PENDING_DESIGN — No schema or application path is supplied. Architecture binds locations, schemas and environments (minimum inputs 1–2 and 6). |
| Provider/consumer verification responsibilities | PENDING_DESIGN — The coding agent defines actual check entry points and fault-injection seams (minimum input 7). Required behavioral AC/V intent and evidence mapping remain in native plan.md/tasks.md; no executed result is claimed. |
| Open agreement questions | Architecture must locate native Swarmflow integration and bind graph/runner/Gate bootstrap, state serialization, cancellation and human-session wiring. Graph definitions can use declared capsule contracts before all research stages are implemented; real integration cannot be claimed with placeholders. |

Consumed agreements: [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements); [M1-IF-009@r0](../M1-009/TASK.md#4-embedded-cross-module-agreements); [M1-IF-002@r0](../M1-002/TASK.md#4-embedded-cross-module-agreements). Definition-time and runtime usage differ as recorded in Section 3; reciprocal semantic dependencies are not full-task completion prerequisites.

Architecture reservation: [minimum inputs](../ARCHITECTURE_MINIMUM_INPUTS.txt), items 1-7, owns actual modules/code/processes, typed payload/API/error contracts, runtime coordination, storage/durability, security isolation, configuration realization and executable test entry points. These remain PENDING_DESIGN; no implementation mechanism is selected by this current PRD update.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| D01 / 2026-10-01 | Initial PRD r1 allocation; Architecture: [current design](../../../../architecture/build-package/README.md); detailed realization belongs to the coding agent; user requests document preparation only | All native records; M1-IF-006@r0 | No runtime evidence exists; affected implementation and checks cannot pass before their definitions exist | UNASSIGNED; register architecture and inspect existing code before binding technical paths |
| D02 / 2026-10-01 | Architecture must locate native Swarmflow integration and bind graph/runner/Gate bootstrap, state serialization, cancellation and human-session wiring. Graph definitions can use declared capsule contracts before all research stages are implemented; real integration cannot be claimed with placeholders. | plan.md unresolved decisions; T001; relevant AC/V rows | Only dependent work is constrained; independent source/fixture preparation continues | UNASSIGNED; resolve from architecture or registered capsule/product policy, not guessed requirements |
| PRD-R2 / 2026-10-02 | §4.6.4, §6.4. Adds headless halt while preserving Gate policy and durable progression. | AC-004, AC-008; native plan/tasks correspondence; M1-IF-006@r0 | Invalidate affected earlier evidence if any; current candidate NOT_BUILT and runtime NOT_RUN. | UNASSIGNED; complete Implementation-dependent definitions before affected implementation. |

Progress is in tasks.md. No separate approval, review, handoff or implementation-checklist card is introduced.
