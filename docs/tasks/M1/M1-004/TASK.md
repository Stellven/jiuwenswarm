# TASK: M1-004 - Static model routing and reviewer provisioning

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-004 / r1 / 2026-10-01 |
| Parent TASKS | [M1](../TASKS.md) |
| Executor / collaborators | UNASSIGNED for implementation; Codex prepares documents at the user's request |
| Requested outcome and instruction/source | Prepare English TASK/Spec Kit documents from PRD Full. Current action scope: documentation only; no application changes, runtime tests or commits. Future product outcome: Register sole active Codex CLI provider, statically route the DAG-provided capsule/role, audit every call and provision independent read-only Tier-2 review. |
| Included scope / exclusions | Included: Register sole active Codex CLI provider, statically route the DAG-provided capsule/role, audit every call and provision independent read-only Tier-2 review. Excluded: No heterogeneous/dynamic production selection, local weights, fine-tuned/poorly documented model-pool expansion, learned/vector/bandit routers, ensembles, mid-call switching, complex optimization, billing/quota infrastructure, reviewer edits or iterative coder-reviewer loops. Mocked isolated Phase 2 registry/routing is M1-019. |
| PRD clause and architecture node references | [Registered PRD](../sources/PRD-Full.r1.txt): PRD r1 (2026-10-01), SHA256 2F689644EF9517378F5CF16B28FA372F011811B9F9095AA0CA6996A6A10B13D9, 177840 bytes; §4.3, §4.3.1 Phase 1, §4.3.2 Phase 1, §4.3.3, §4.3.4; sequencing §6.4; global §1.3–§1.6 and §2.1–§2.12 apply. Architecture PENDING_SOURCE; architecture nodes are not invented. |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / a8f36245a83358a606bf00f83a64b3353a41c4cd; existing checkout; no tested runtime candidate prepared |
| Affected code/document paths | docs/tasks/M1/M1-004/TASK.md; specs/M1-004-static-model-routing/spec.md, plan.md, tasks.md. Application/test/configuration paths PENDING_DESIGN after architecture and existing-code inspection. |

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | specs/M1-004-static-model-routing/ relative to repository root | Exactly one feature for this TASK |
| spec.md | [spec](../../../../specs/M1-004-static-model-routing/spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](../../../../specs/M1-004-static-model-routing/plan.md) | Behavior blocks, future design and verification procedures |
| tasks.md | [tasks](../../../../specs/M1-004-static-model-routing/tasks.md) | Work, progress and acceptance/evidence correspondence |
| evidence/ | specs/M1-004-static-model-routing/evidence/ (create on actual verification) | Actual candidate run records/raw artifacts; none generated during preparation |
| Supporting artifacts | None | No parallel cards or invented schemas; future support remains subordinate |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [M1-001](../M1-001/TASK.md) / M1-IF-001@r0 | Codex CLI provider | Runtime before live invocation | B01–B03; T001 and applicable boundary work |
| [M1-003](../M1-003/TASK.md) / M1-IF-003@r0 | Designated capsule and role/eligibility semantics | Definition before routing; does not await full CC runner/admission implementation | B01/B03; T001 and applicable boundary work |
| [M1-005](../M1-005/TASK.md) / M1-IF-005@r0 | Per-call audit persistence | Definition then runtime before audit boundary check | B02; T001 and applicable boundary work |
| [M1-007](../M1-007/TASK.md) / M1-IF-007@r0 | Tier-2 context and structured-result consumer | Definition then boundary; not full Gate acceptance | B03; T001 and applicable boundary work |
| Master architecture / PENDING_SOURCE | Actual technical boundaries and implementation/check paths | Required only before affected implementation/real boundary checks; independent PRD preparation continues | T001 and unresolved technical work |
| [M1-SYSTEM](../M1-SYSTEM/TASK.md) | Candidate-wide journey verification | Final integration; not a prerequisite for block definitions or isolated checks | System contribution work in tasks.md |

Definition dependencies do not require a fully VERIFIED peer TASK. Define capsule/provider/evidence/gate semantics first; connect their implemented blocks later. This avoids treating runner -> Gate -> reviewer -> capsule as a circular sequence of whole-task completion.

## 4. Embedded cross-module agreements
### M1-IF-004 at r0
**Provisional PRD-semantic agreement.** This is not a final architecture, API or schema. Fields and rules explicitly present in the PRD are retained; unspecified technical details remain PENDING_DESIGN.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provider: M1-004. Consumers: M1-003, M1-006, M1-007, M1-SYSTEM. |
| Purpose / source requirement | Register sole active Codex CLI provider, statically route the DAG-provided capsule/role, audit every call and provision independent read-only Tier-2 review. Source: §4.3, §4.3.1 Phase 1, §4.3.2 Phase 1, §4.3.3, §4.3.4; sequencing §6.4. |
| Inputs: fields, types, units, required/optional, validation | DAG/Planner-designated capsule and task execution role, task/execution identity and model input; reviewer artifact/upstream/evidence/AC context. Router does not choose capsule. Exact field schema/types PENDING_DESIGN. Exact field types/requiredness/units not stated by PRD remain PENDING_DESIGN. |
| Outputs: fields, types, units, semantics, guarantees | Static Codex CLI route and provider output; per-call endpoint, capsule, task, role, timestamp, latency, call count, success/failure and fallback occurrence; optional reliable token/cost values; structured review delivered to Gate. |
| States and invariants | Only Codex CLI active in Phase 1; router chooses model endpoint, not capsule; reviewer uses designated verifier_capsule.md with independent read-only context. Underlying foundation-model identifier is not prescribed. |
| Errors, timeout, retry, cancellation | Provider/authentication/time faults propagate honestly; absent unreliable token/cost fields do not fail a run. Exact errors/timeout/cancellation mapping PENDING_DESIGN; no reviewer-driven model switching/repair. |
| Side effects and idempotency | Endpoint calls and per-call audit writes; repeated model calls are not assumed idempotent and remain counted. Reviewer cannot change code/artifacts; storage guarantees reference M1-IF-005. |
| Compatibility and migration | Initial r0. Architecture may refine technical representation without altering product behavior. Material changes update this owner, parent allocation and affected consumers and invalidate corresponding boundary/system evidence. |
| Machine-readable schema / source path | None created; PENDING_DESIGN. Future generated representations implement this agreement and carry its effective IF revision. |
| Provider/consumer verification responsibilities | M1-004/V01–V04 cover source criteria; M1-004/V90 connects actual peers. Consumers provide actual inputs/state and their matching boundary evidence. M1-SYSTEM owns complete journeys. |
| Open agreement questions | Architecture binds registry/provider/review types and reliable-usage detection. Actual task-role metadata is required by this PRD even if older placeholder documentation omitted it. No missing model ID is invented. |

Consumed agreements: [M1-IF-001@r0](../M1-001/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements). Definition-time and runtime usage differ as recorded in Section 3; reciprocal semantic dependencies are not full-task completion prerequisites.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| D01 / 2026-10-01 | Initial PRD r1 allocation; Architecture PENDING_SOURCE; user requests document preparation only | All native records; M1-IF-004@r0 | No runtime evidence exists; affected implementation and checks cannot pass before their definitions exist | UNASSIGNED; register architecture and inspect existing code before binding technical paths |
| D02 / 2026-10-01 | Architecture binds registry/provider/review types and reliable-usage detection. Actual task-role metadata is required by this PRD even if older placeholder documentation omitted it. No missing model ID is invented. | plan.md unresolved decisions; T001; relevant AC/V rows | Only dependent work is constrained; independent source/fixture preparation continues | UNASSIGNED; resolve from architecture or registered capsule/product policy, not guessed requirements |

Progress is in tasks.md. No separate approval, review, handoff or implementation-checklist card is introduced.
