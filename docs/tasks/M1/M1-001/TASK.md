# TASK: M1-001 - Codex CLI adapter

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-001 / r1 / 2026-10-01 |
| Parent TASKS | [M1](../TASKS.md) |
| Executor / collaborators | UNASSIGNED for implementation; Codex prepares documents at the user's request |
| Requested outcome and instruction/source | Prepare English TASK/Spec Kit documents from PRD Full. Current action scope: documentation only; no application changes, runtime tests or commits. Future product outcome: Inspect and stabilize the existing Codex CLI adapter, preserve native invocation/response compatibility, secure local IPC and expose a reusable Python provider endpoint. |
| Included scope / exclusions | Included: Inspect and stabilize the existing Codex CLI adapter, preserve native invocation/response compatibility, secure local IPC and expose a reusable Python provider endpoint. Excluded: No custom proxy from scratch, complex multi-turn conversational streaming, enterprise API-key prerequisite or dynamic-router integration on the Phase 1 path. Future endpoint-of-last-resort registration is an abstraction goal, not live heterogeneous routing. |
| PRD clause and architecture node references | [Registered PRD](../sources/PRD-Full.r1.txt): PRD r1 (2026-10-01), SHA256 2F689644EF9517378F5CF16B28FA372F011811B9F9095AA0CA6996A6A10B13D9, 177840 bytes; §3.0, §3.0.1, §3.0.2; sequencing §6.3; global §1.3–§1.6 and §2.1–§2.12 apply. Architecture PENDING_SOURCE; architecture nodes are not invented. |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / a8f36245a83358a606bf00f83a64b3353a41c4cd; existing checkout; no tested runtime candidate prepared |
| Affected code/document paths | docs/tasks/M1/M1-001/TASK.md; specs/M1-001-codex-adapter/spec.md, plan.md, tasks.md. Application/test/configuration paths PENDING_DESIGN after architecture and existing-code inspection. |

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | specs/M1-001-codex-adapter/ relative to repository root | Exactly one feature for this TASK |
| spec.md | [spec](../../../../specs/M1-001-codex-adapter/spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](../../../../specs/M1-001-codex-adapter/plan.md) | Behavior blocks, future design and verification procedures |
| tasks.md | [tasks](../../../../specs/M1-001-codex-adapter/tasks.md) | Work, progress and acceptance/evidence correspondence |
| evidence/ | specs/M1-001-codex-adapter/evidence/ (create on actual verification) | Actual candidate run records/raw artifacts; none generated during preparation |
| Supporting artifacts | None | No parallel cards or invented schemas; future support remains subordinate |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [M1-002](../M1-002/TASK.md) / M1-IF-002@r0 | Minimum configuration and permitted local security/IPC boundary | Definition before transport design; runtime before secure invocation | B01–B03; T001 and applicable boundary work |
| [M1-004](../M1-004/TASK.md) / M1-IF-004@r0 | Static provider caller expectations | Definition and real boundary wiring only; not whole routing-task completion | B01/B03; T001 and applicable boundary work |
| [M1-005](../M1-005/TASK.md) / M1-IF-005@r0 | Timeout/authentication-drop telemetry sink | Definition before logging design; actual sink before V90 | B03; T001 and applicable boundary work |
| Master architecture / PENDING_SOURCE | Actual technical boundaries and implementation/check paths | Required only before affected implementation/real boundary checks; independent PRD preparation continues | T001 and unresolved technical work |
| [M1-SYSTEM](../M1-SYSTEM/TASK.md) | Candidate-wide journey verification | Final integration; not a prerequisite for block definitions or isolated checks | System contribution work in tasks.md |

Definition dependencies do not require a fully VERIFIED peer TASK. Define capsule/provider/evidence/gate semantics first; connect their implemented blocks later. This avoids treating runner -> Gate -> reviewer -> capsule as a circular sequence of whole-task completion.

## 4. Embedded cross-module agreements
### M1-IF-001 at r0
**Provisional PRD-semantic agreement.** This is not a final architecture, API or schema. Fields and rules explicitly present in the PRD are retained; unspecified technical details remain PENDING_DESIGN.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provider: M1-001. Consumers: M1-004, M1-006, M1-SYSTEM. |
| Purpose / source requirement | Inspect and stabilize the existing Codex CLI adapter, preserve native invocation/response compatibility, secure local IPC and expose a reusable Python provider endpoint. Source: §3.0, §3.0.1, §3.0.2; sequencing §6.3. |
| Inputs: fields, types, units, required/optional, validation | Native OpenJiuwen completion requests and active local execution context; synchronous single-turn request. An ephemeral adapter credential binds each request to its active JiuwenSwarm session. Native payload conversion and Python signature PENDING_DESIGN. Exact field types/requiredness/units not stated by PRD remain PENDING_DESIGN. |
| Outputs: fields, types, units, semantics, guarantees | Parsed native-format completion, standardized Python provider endpoint, and timeout/authentication-drop run-tree events. The PRD specifies the Codex CLI route, not an underlying model identifier. |
| States and invariants | Use only local Unix Domain Socket on POSIX or equivalent named pipe where required, restrictive permissions (example 0600), ephemeral session credentials and no adapter TCP listener; preserve existing subscription-backed invocation. |
| Errors, timeout, retry, cancellation | Timeout/authentication loss are recorded and not fabricated as success. Exact exception classes, cancellation and configured timeout values PENDING_DESIGN; no new autonomous retry/repair loop. |
| Side effects and idempotency | Calls active Codex CLI and writes attributable runtime telemetry. Model calls may differ and consume calls; no invocation idempotency guarantee is invented. Session lifecycle/cleanup are architecture inputs. |
| Compatibility and migration | Initial r0. Architecture may refine technical representation without altering product behavior. Material changes update this owner, parent allocation and affected consumers and invalidate corresponding boundary/system evidence. |
| Machine-readable schema / source path | None created; PENDING_DESIGN. Future generated representations implement this agreement and carry its effective IF revision. |
| Provider/consumer verification responsibilities | M1-001/V01–V04 cover source criteria; M1-001/V90 connects actual peers. Consumers provide actual inputs/state and their matching boundary evidence. M1-SYSTEM owns complete journeys. |
| Open agreement questions | Locate existing adapter/callers/tests before deciding changes; architecture must bind native payload conversion, local transport implementation, credential lifecycle, timeout/cancellation and telemetry hooks. Actual account availability is untested. |

Consumed agreements: [M1-IF-002@r0](../M1-002/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements). Definition-time and runtime usage differ as recorded in Section 3; reciprocal semantic dependencies are not full-task completion prerequisites.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| D01 / 2026-10-01 | Initial PRD r1 allocation; Architecture PENDING_SOURCE; user requests document preparation only | All native records; M1-IF-001@r0 | No runtime evidence exists; affected implementation and checks cannot pass before their definitions exist | UNASSIGNED; register architecture and inspect existing code before binding technical paths |
| D02 / 2026-10-01 | Locate existing adapter/callers/tests before deciding changes; architecture must bind native payload conversion, local transport implementation, credential lifecycle, timeout/cancellation and telemetry hooks. Actual account availability is untested. | plan.md unresolved decisions; T001; relevant AC/V rows | Only dependent work is constrained; independent source/fixture preparation continues | UNASSIGNED; resolve from architecture or registered capsule/product policy, not guessed requirements |

Progress is in tasks.md. No separate approval, review, handoff or implementation-checklist card is introduced.
