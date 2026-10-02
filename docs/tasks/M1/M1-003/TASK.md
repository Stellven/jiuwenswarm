# TASK: M1-003 - Capability capsules and admission

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-003 / r1 / 2026-10-01 |
| Parent TASKS | [M1](../TASKS.md) |
| Executor / collaborators | UNASSIGNED for implementation; Codex prepares documents at the user's request |
| Requested outcome and instruction/source | Prepare English TASK/Spec Kit documents from PRD Full. Current action scope: documentation only; no application changes, runtime tests or commits. Future product outcome: Define, admit, retain and execute fixed-schema capabilities with explicit permissions, version pins, static selection, time limits and manually activated implementation lineage. |
| Included scope / exclusions | Included: Define, admit, retain and execute fixed-schema capabilities with explicit permissions, version pins, static selection, time limits and manually activated implementation lineage. Excluded: No autonomous capsule generation, remote A2A/MCP imports, per-capsule package installation or model selection by capsules; no deletion, automatic librarian, external publishing or third-party certified trust; no dynamic production discovery/ranking, token/money enforcement, mid-run installation, repair/promotion, horizontal evolution, live RSI or verifier evolution. Phase 2 read-only catalogue/jiuwenbox work belongs to M1-019; offline optimization loop belongs to M1-018. |
| PRD clause and architecture node references | [Registered PRD](../sources/PRD-Full.r1.txt): PRD r1 (2026-10-01), SHA256 2F689644EF9517378F5CF16B28FA372F011811B9F9095AA0CA6996A6A10B13D9, 177840 bytes; §4.1, §4.1.1, §4.1.2, §4.1.3 Phase 1, §4.1.4, §4.1.5; sequencing §6.4; global §1.3–§1.6 and §2.1–§2.12 apply. Architecture PENDING_SOURCE; architecture nodes are not invented. |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / a8f36245a83358a606bf00f83a64b3353a41c4cd; existing checkout; no tested runtime candidate prepared |
| Affected code/document paths | docs/tasks/M1/M1-003/TASK.md; specs/M1-003-capability-capsules/spec.md, plan.md, tasks.md. Application/test/configuration paths PENDING_DESIGN after architecture and existing-code inspection. |

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | specs/M1-003-capability-capsules/ relative to repository root | Exactly one feature for this TASK |
| spec.md | [spec](../../../../specs/M1-003-capability-capsules/spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](../../../../specs/M1-003-capability-capsules/plan.md) | Behavior blocks, future design and verification procedures |
| tasks.md | [tasks](../../../../specs/M1-003-capability-capsules/tasks.md) | Work, progress and acceptance/evidence correspondence |
| evidence/ | specs/M1-003-capability-capsules/evidence/ (create on actual verification) | Actual candidate run records/raw artifacts; none generated during preparation |
| Supporting artifacts | None | No parallel cards or invented schemas; future support remains subordinate |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [M1-002](../M1-002/TASK.md) / M1-IF-002@r0 | Configured time limits and unprivileged execution/security policy | Definition before bounded execution design; real configuration before runner verification | B01/B04; T001 and applicable boundary work |
| [M1-004](../M1-004/TASK.md) / M1-IF-004@r0 | Separate model provisioning for designated capsule and role | Runtime provider before model-bearing invocation; contract definition proceeds independently | B04; T001 and applicable boundary work |
| [M1-005](../M1-005/TASK.md) / M1-IF-005@r0 | Persistent admission/version/run observations | Storage semantics first; real persistence before registry/run boundary acceptance | B02/B04; T001 and applicable boundary work |
| [M1-007](../M1-007/TASK.md) / M1-IF-007@r0 | Evidence intake and gate result meaning | Definition then runtime handoff; do not await full Gate completion for capsule contracts | B04; T001 and applicable boundary work |
| [M1-006](../M1-006/TASK.md) / M1-IF-006@r0 | Named graph bindings and runner-dispatch consumer | Definition then connected boundary; not entire Harness completion | B03/B04; T001 and applicable boundary work |
| [M1-018](../M1-018/TASK.md) / M1-IF-018@r0 | Implementation-only RSI candidate and hidden-fixture evaluation reference | Later admission boundary; ordinary hand-written capsule admission does not await the full optimizer | B05; T001 and applicable boundary work |
| Master architecture / PENDING_SOURCE | Actual technical boundaries and implementation/check paths | Required only before affected implementation/real boundary checks; independent PRD preparation continues | T001 and unresolved technical work |
| [M1-SYSTEM](../M1-SYSTEM/TASK.md) | Candidate-wide journey verification | Final integration; not a prerequisite for block definitions or isolated checks | System contribution work in tasks.md |

Definition dependencies do not require a fully VERIFIED peer TASK. Define capsule/provider/evidence/gate semantics first; connect their implemented blocks later. This avoids treating runner -> Gate -> reviewer -> capsule as a circular sequence of whole-task completion.

## 4. Embedded cross-module agreements
### M1-IF-003 at r0
**Provisional PRD-semantic agreement.** This is not a final architecture, API or schema. Fields and rules explicitly present in the PRD are retained; unspecified technical details remain PENDING_DESIGN.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provider: M1-003. Consumers: M1-004, M1-005, M1-006, M1-007, M1-008 through M1-018, M1-SYSTEM. |
| Purpose / source requirement | Define, admit, retain and execute fixed-schema capabilities with explicit permissions, version pins, static selection, time limits and manually activated implementation lineage. Source: §4.1, §4.1.1, §4.1.2, §4.1.3 Phase 1, §4.1.4, §4.1.5; sequencing §6.4. |
| Inputs: fields, types, units, required/optional, validation | Machine-checked capsule.json declares typed I/O, tools, mutation permissions, dependencies/resources and entry points; code/version hashes, named DAG binding, runtime inputs/time allowance and manual registry actions. Detailed schema/API PENDING_DESIGN. Exact field types/requiredness/units not stated by PRD remain PENDING_DESIGN. |
| Outputs: fields, types, units, semantics, guarantees | Derived make_capsule.md, written admission decision and provisional standing, append-only version history/manual active pointer, pinned eligible binding, captured runner output/observations and evidence for the Gate. |
| States and invariants | One runner; named admitted/current/unchanged/type-compatible capsules only; retained historical versions and explicit pins. Default-pointer changes are manual; exact used hash/version persists. RSI cannot alter schemas or evolve verifier. Governed outputs enter Gate before downstream release. |
| Errors, timeout, retry, cancellation | Changed-since-admission/ineligible/incompatible capsules refuse execution; time overrun is infrastructure fault; no automatic repair. Exact status APIs, timeout config, cancellation and interrupted-command recovery PENDING_DESIGN. |
| Side effects and idempotency | Writes admission/history/standing and runner observations; manual activation changes default pointer. Each run records its bound hash. Calls can have declared effects and are not presumed idempotent; command atomicity/repeated-call meaning PENDING_DESIGN. |
| Compatibility and migration | Initial r0. Architecture may refine technical representation without altering product behavior. Material changes update this owner, parent allocation and affected consumers and invalidate corresponding boundary/system evidence. |
| Machine-readable schema / source path | None created; PENDING_DESIGN. Future generated representations implement this agreement and carry its effective IF revision. |
| Provider/consumer verification responsibilities | M1-003/V01–V07 cover source criteria; M1-003/V90 connects actual peers. Consumers provide actual inputs/state and their matching boundary evidence. M1-SYSTEM owns complete journeys. |
| Open agreement questions | Architecture binds contract loader/schema, history/default storage, runner and Gate bootstrap. Latest optimized must preserve manual activation. Hidden-fixture evaluation is M1-018 and isolation policy M1-002; this task owns admission/manual activation semantics only. |

Consumed agreements: [M1-IF-002@r0](../M1-002/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-018@r0](../M1-018/TASK.md#4-embedded-cross-module-agreements). Definition-time and runtime usage differ as recorded in Section 3; reciprocal semantic dependencies are not full-task completion prerequisites.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| D01 / 2026-10-01 | Initial PRD r1 allocation; Architecture PENDING_SOURCE; user requests document preparation only | All native records; M1-IF-003@r0 | No runtime evidence exists; affected implementation and checks cannot pass before their definitions exist | UNASSIGNED; register architecture and inspect existing code before binding technical paths |
| D02 / 2026-10-01 | Architecture binds contract loader/schema, history/default storage, runner and Gate bootstrap. Latest optimized must preserve manual activation. Hidden-fixture evaluation is M1-018 and isolation policy M1-002; this task owns admission/manual activation semantics only. | plan.md unresolved decisions; T001; relevant AC/V rows | Only dependent work is constrained; independent source/fixture preparation continues | UNASSIGNED; resolve from architecture or registered capsule/product policy, not guessed requirements |

Progress is in tasks.md. No separate approval, review, handoff or implementation-checklist card is introduced.
