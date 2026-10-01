# TASK: M1-006 - Governed harness and fixed research DAG

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-006 / r1 / 2026-10-01 |
| Parent TASKS | [M1](../TASKS.md) |
| Executor / collaborators | UNASSIGNED for implementation; Codex prepares documents at the user's request |
| Requested outcome and instruction/source | Prepare English TASK/Spec Kit documents from PRD Full. Current action scope: documentation only; no application changes, runtime tests or commits. Future product outcome: Use native Swarmflow for local lifecycle, immutable sequential scheduling, bounded runner subprocess dispatch, evidence handoff, gate-locked advancement and explicit human failure handling; inject Research_Brief parameters into the fixed DAG. |
| Included scope / exclusions | Included: Use native Swarmflow for local lifecycle, immutable sequential scheduling, bounded runner subprocess dispatch, evidence handoff, gate-locked advancement and explicit human failure handling; inject Research_Brief parameters into the fixed DAG. Excluded: No Auto Harness recursive sub-runs; autonomous decomposition, live graph restructuring, parallel hypotheses/batching, remote/cloud fleets or external container dispatch, message brokers/leases/quotas; no automatic repair/requeue or complex partial rewind. Isolated Cluster/Leader/dynamic-planning tracks belong to M1-019. |
| PRD clause and architecture node references | [Registered PRD](../sources/PRD-Full.r1.txt): PRD r1 (2026-10-01), SHA256 2F689644EF9517378F5CF16B28FA372F011811B9F9095AA0CA6996A6A10B13D9, 177840 bytes; §4.6, §4.6.1, §4.6.2 Phase 1, §4.6.3, §4.6.4; §4.6.5 excluded; §4.8, §4.8.1, §4.8.2, §4.8.3 Phase 1; sequencing §6.4–§6.5; global §1.3–§1.6 and §2.1–§2.12 apply. Architecture PENDING_SOURCE; architecture nodes are not invented. |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / a8f36245a83358a606bf00f83a64b3353a41c4cd; existing checkout; no tested runtime candidate prepared |
| Affected code/document paths | docs/tasks/M1/M1-006/TASK.md; specs/M1-006-governed-harness/spec.md, plan.md, tasks.md. Application/test/configuration paths PENDING_DESIGN after architecture and existing-code inspection. |

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | specs/M1-006-governed-harness/ relative to repository root | Exactly one feature for this TASK |
| spec.md | [spec](../../../../specs/M1-006-governed-harness/spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](../../../../specs/M1-006-governed-harness/plan.md) | Behavior blocks, future design and verification procedures |
| tasks.md | [tasks](../../../../specs/M1-006-governed-harness/tasks.md) | Work, progress and acceptance/evidence correspondence |
| evidence/ | specs/M1-006-governed-harness/evidence/ (create on actual verification) | Actual candidate run records/raw artifacts; none generated during preparation |
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
### M1-IF-006 at r0
**Provisional PRD-semantic agreement.** This is not a final architecture, API or schema. Fields and rules explicitly present in the PRD are retained; unspecified technical details remain PENDING_DESIGN.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provider: M1-006. Consumers: M1-003, M1-007, M1-008 through M1-017, M1-SYSTEM. |
| Purpose / source requirement | Use native Swarmflow for local lifecycle, immutable sequential scheduling, bounded runner subprocess dispatch, evidence handoff, gate-locked advancement and explicit human failure handling; inject Research_Brief parameters into the fixed DAG. Source: §4.6, §4.6.1, §4.6.2 Phase 1, §4.6.3, §4.6.4; §4.6.5 excluded; §4.8, §4.8.1, §4.8.2, §4.8.3 Phase 1; sequencing §6.4–§6.5. |
| Inputs: fields, types, units, required/optional, validation | Validated Research_Brief, fixed graph/named admitted bindings, local session config, accepted upstream artifacts, evidence/Gate results and durable-record visibility, explicit human actions. Exact field types/requiredness/units not stated by PRD remain PENDING_DESIGN. |
| Outputs: fields, types, units, semantics, guarantees | Native run identity and lifecycle snapshots, bounded runner calls, Stage Evidence Bundles to Gate, downstream dispatch only after durable advancing decisions, forensic failures/native human_session, safely concluded run. |
| States and invariants | Pending -> Running -> Evaluating -> Completed/Failed. Phase 1 stages 3.1–3.9 remain linear/immutable. Only durable PASS/PASS_WITH_KNOWN_LIMITATIONS releases downstream; valid scientific FAIL is not automatically a Harness failure. |
| Errors, timeout, retry, cancellation | Crash/syntax/time/gate faults halt autonomous execution, retain evidence and route to human_session. No auto retry/repair or replay after environment correction; explicit restart required. Exact cancellation/process cleanup/snapshot recovery PENDING_DESIGN. |
| Side effects and idempotency | Starts managed local runner subprocesses, persists states/evidence and prompts human triage. Explicit restarts preserve earlier failure records; identity/idempotency/exactly-once guarantees PENDING_DESIGN, not invented. |
| Compatibility and migration | Initial r0. Architecture may refine technical representation without altering product behavior. Material changes update this owner, parent allocation and affected consumers and invalidate corresponding boundary/system evidence. |
| Machine-readable schema / source path | None created; PENDING_DESIGN. Future generated representations implement this agreement and carry its effective IF revision. |
| Provider/consumer verification responsibilities | M1-006/V01–V07 cover source criteria; M1-006/V90 connects actual peers. Consumers provide actual inputs/state and their matching boundary evidence. M1-SYSTEM owns complete journeys. |
| Open agreement questions | Architecture must locate native Swarmflow integration and bind graph/runner/Gate bootstrap, state serialization, cancellation and human-session wiring. Graph definitions can use declared capsule contracts before all research stages are implemented; real integration cannot be claimed with placeholders. |

Consumed agreements: [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements); [M1-IF-009@r0](../M1-009/TASK.md#4-embedded-cross-module-agreements); [M1-IF-002@r0](../M1-002/TASK.md#4-embedded-cross-module-agreements). Definition-time and runtime usage differ as recorded in Section 3; reciprocal semantic dependencies are not full-task completion prerequisites.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| D01 / 2026-10-01 | Initial PRD r1 allocation; Architecture PENDING_SOURCE; user requests document preparation only | All native records; M1-IF-006@r0 | No runtime evidence exists; affected implementation and checks cannot pass before their definitions exist | UNASSIGNED; register architecture and inspect existing code before binding technical paths |
| D02 / 2026-10-01 | Architecture must locate native Swarmflow integration and bind graph/runner/Gate bootstrap, state serialization, cancellation and human-session wiring. Graph definitions can use declared capsule contracts before all research stages are implemented; real integration cannot be claimed with placeholders. | plan.md unresolved decisions; T001; relevant AC/V rows | Only dependent work is constrained; independent source/fixture preparation continues | UNASSIGNED; resolve from architecture or registered capsule/product policy, not guessed requirements |

Progress is in tasks.md. No separate approval, review, handoff or implementation-checklist card is introduced.
