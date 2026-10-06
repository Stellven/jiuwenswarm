# TASK: M1-001 - Codex CLI adapter

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-001 / r2 / 2026-10-02 |
| Parent TASKS | [M1](../TASKS.md) |
| Executor / collaborators | UNASSIGNED for implementation; Codex prepares documents at the user's request |
| Requested outcome and instruction/source | Prepare English TASK/Spec Kit documents from the latest PRD Full attachment (capture r2). Current action scope: documentation only; no application changes, runtime tests or commits. Future product outcome: Inspect and stabilize the existing Codex CLI adapter, preserve native invocation/response compatibility, secure local IPC and expose a reusable Python provider endpoint. |
| Included scope / exclusions | Included: Inspect and stabilize the existing Codex CLI adapter, preserve native invocation/response compatibility, secure local IPC and expose a reusable Python provider endpoint. Excluded: No custom proxy from scratch, complex multi-turn conversational streaming, enterprise API-key prerequisite or dynamic-router integration on the Phase 1 path. Future endpoint-of-last-resort registration is an abstraction goal, not live heterogeneous routing. |
| PRD clause and architecture node references | [Registered PRD](../sources/PRD-Full.r2.txt): capture baseline r2 (2026-10-02), SHA256 44928035205BDEBAE205D2B458BD438C2C6E0103E4EB2D834C6A93E1CFA37294, 200082 bytes; §3.0, §3.0.1, §3.0.2; consumed §4.3.3; sequencing §6.3; global §1.3–§1.6 and §2.1–§2.12 apply. Architecture PENDING_SOURCE; architecture nodes are not invented. |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / d9fe483ea64c273ef831886bfa83819f6d5bb21c; existing checkout; no tested runtime candidate prepared |
| Affected code/document paths | docs/code/Missions/M1/M1-001/TASK.md; docs/code/Missions/M1/M1-001/spec.md, plan.md, tasks.md. Application/test/configuration paths PENDING_DESIGN after architecture and existing-code inspection. |

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/M1/M1-001/ relative to repository root | Exactly one feature for this TASK |
| spec.md | [spec](spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](plan.md) | Behavior blocks, future design and verification procedures |
| tasks.md | [tasks](tasks.md) | Work, progress and acceptance/evidence correspondence |
| evidence/ | docs/code/Missions/M1/M1-001/evidence/ (create on actual verification) | Actual candidate run records/raw artifacts; none generated during preparation |
| Supporting artifacts | None | No parallel cards or invented schemas; future support remains subordinate |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [M1-002](../M1-002/TASK.md) / M1-IF-002@r0 | Minimum configuration and permitted local security/IPC boundary | Definition before transport design; runtime before secure invocation | B01–B03; T001 and applicable boundary work |
| [M1-004](../M1-004/TASK.md) / M1-IF-004@r0 | Static provider caller expectations and canonical audited model-call/provider-minimization behavior (§4.3.3) | Consume M1-004's canonical agreement; no duplicate audit schema; real boundary required for connected acceptance | AC-005; relevant native block/work/check mappings |
| [M1-005](../M1-005/TASK.md) / M1-IF-005@r0 | Timeout/authentication-drop telemetry sink | Definition before logging design; actual sink before V90 | B03; T001 and applicable boundary work |
| Master architecture / PENDING_SOURCE | Actual technical boundaries and implementation/check paths | Required only before affected implementation/real boundary checks; independent PRD preparation continues | T001 and unresolved technical work |
| [M1-SYSTEM](../M1-SYSTEM/TASK.md) | Candidate-wide journey verification | Final integration; not a prerequisite for block definitions or isolated checks | System contribution work in tasks.md |

Definition dependencies do not require a fully VERIFIED peer TASK. Define capsule/provider/evidence/gate semantics first; connect their implemented blocks later. This avoids treating runner -> Gate -> reviewer -> capsule as a circular sequence of whole-task completion.

## 4. Embedded cross-module agreements
### M1-IF-001 at r0
**Provisional document-allocation agreement at r0.** Technical design is intentionally blank pending Architecture. Product behavior/constraints remain in spec.md. The TASK allocation below is not a module/process/API topology. All seven [minimum architecture inputs](../ARCHITECTURE_MINIMUM_INPUTS.txt) are reserved for the Architecture author.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provisional document allocation: provider M1-001; consumers M1-002, M1-004, M1-017, M1-018, M1-019, M1-SYSTEM. Actual module/process/API topology is PENDING_DESIGN (minimum inputs 1–2). |
| Purpose / source requirement | Inspect and stabilize the existing Codex CLI adapter, preserve native invocation/response compatibility, secure local IPC and expose a reusable Python provider endpoint. Source: §3.0, §3.0.1, §3.0.2; consumed §4.3.3; sequencing §6.3. |
| Inputs: fields, types, units, required/optional, validation | PENDING_DESIGN — Architecture owns payloads, types, validation, units and API/IPC handoff (minimum inputs 1–2). Product input obligations remain in spec.md. |
| Outputs: fields, types, units, semantics, guarantees | PENDING_DESIGN — Architecture owns concrete outputs and technical guarantees (minimum inputs 2 and 4). Source-defined observable results remain in spec.md. |
| States and invariants | PENDING_DESIGN — Architecture owns runtime state, transitions and coordination (minimum inputs 1–3). Product invariants remain in spec.md. |
| Errors, timeout, retry, cancellation | PENDING_DESIGN — Architecture owns error structures, propagation, timeout/cancellation and duplicate handling (minimum inputs 2–3). Source failure/restart rules remain in spec.md. |
| Side effects and idempotency | PENDING_DESIGN — Architecture owns effect enforcement, writes, partial-write recovery and repeated-call mechanics (minimum inputs 2–5). Source effect restrictions remain in spec.md. |
| Compatibility and migration | Provisional r0 identity retained. PENDING_DESIGN — Architecture owns compatibility/migration representation (minimum inputs 1–2). Source acceptance is unchanged by realization choices; update consumers and invalidate affected evidence on material revision. |
| Machine-readable schema / source path | PENDING_DESIGN — No schema or application path is supplied. Architecture binds locations, schemas and environments (minimum inputs 1–2 and 6). |
| Provider/consumer verification responsibilities | PENDING_DESIGN — Architecture owns actual check entry points and fault-injection seams (minimum input 7). Required behavioral AC/V intent and evidence mapping remain in native plan.md/tasks.md; no executed result is claimed. |
| Open agreement questions | PENDING_DESIGN — Architecture fills all seven minimum-input categories, including secured IPC realization, native request conversion, credential lifecycle, audited routing handoff, local correlation and clean provider request construction. Product obligations are AC-001–005; canonical usage auditing remains owned by M1-004. |

Consumed agreements: [M1-IF-002@r0](../M1-002/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements). Definition-time and runtime usage differ as recorded in Section 3; reciprocal semantic dependencies are not full-task completion prerequisites.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| D01 / 2026-10-01 | Initial PRD r1 allocation; Architecture PENDING_SOURCE; user requests document preparation only | All native records; M1-IF-001@r0 | No runtime evidence exists; affected implementation and checks cannot pass before their definitions exist | UNASSIGNED; register architecture and inspect existing code before binding technical paths |
| D02 / 2026-10-01 | Locate existing adapter/callers/tests before deciding changes; architecture must bind native payload conversion, local transport implementation, credential lifecycle, timeout/cancellation and telemetry hooks. Actual account availability is untested. | plan.md unresolved decisions; T001; relevant AC/V rows | Only dependent work is constrained; independent source/fixture preparation continues | UNASSIGNED; resolve from architecture or registered capsule/product policy, not guessed requirements |
| D03 / 2026-10-02 | PRD r2 adds consumed M1-004 local model-call correlation, audited invocation and provider data-minimization obligations. AC-005 consumes the canonical audit boundary; no second audit payload format is defined. Architecture technical cells intentionally left PENDING_DESIGN at the user's request. | spec.md r2; affected plan/work mappings; stable provisional M1-IF-001@r0 | No runtime evidence exists; corresponding future checks remain NOT_RUN. Keep historical records and reassess any later evidence against r2. | UNASSIGNED; Architecture resolves the seven reserved categories before dependent implementation. |

Progress is in tasks.md. No separate approval, review, handoff or implementation-checklist card is introduced.
