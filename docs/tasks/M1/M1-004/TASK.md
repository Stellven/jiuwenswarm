# TASK: M1-004 - Static model routing and reviewer provisioning

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-004 / r2 / 2026-10-02 |
| Parent TASKS | [M1](../TASKS.md) |
| Executor / collaborators | UNASSIGNED for implementation; Codex prepares documents at the user's request |
| Requested outcome and instruction/source | Prepare English TASK/Spec Kit documents from PRD Full. Current action scope: documentation only; no application changes, runtime tests or commits. Future product outcome: Register sole active Codex CLI provider, statically route the DAG-provided capsule/role, audit every call and provision independent read-only Tier-2 review. |
| Included scope / exclusions | Included: Register sole active Codex CLI provider, statically route the DAG-provided capsule/role, audit every call and provision independent read-only Tier-2 review. Excluded: No heterogeneous/dynamic production selection, local weights, fine-tuned/poorly documented model-pool expansion, learned/vector/bandit routers, ensembles, mid-call switching, complex optimization, billing/quota infrastructure, reviewer edits or iterative coder-reviewer loops. Access-gated isolated Phase 2 registry/routing and alternate-Verifier experiments belong to M1-019. |
| PRD clause and architecture node references | [Registered PRD](../sources/PRD-Full.r2.txt): PRD r2 (2026-10-02), SHA256 44928035205BDEBAE205D2B458BD438C2C6E0103E4EB2D834C6A93E1CFA37294, 200082 bytes; §4.3, §4.3.1 Phase 1, §4.3.2 Phase 1, §4.3.3, §4.3.4; sequencing §6.4; global §1.3–§1.6 and §2.1–§2.12 apply. Architecture PENDING_SOURCE; architecture nodes are not invented. |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / d9fe483ea64c273ef831886bfa83819f6d5bb21c; existing checkout; no tested runtime candidate prepared |
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

All seven [minimum architecture inputs](../ARCHITECTURE_MINIMUM_INPUTS.txt) remain reserved for Architecture. Source acceptance stays in spec.md; this section records provisional document allocation and leaves technical design unfilled.

### M1-IF-004 at r0
**Provisional PRD-semantic agreement.** This is not a final architecture, API or schema. Fields and rules explicitly present in the PRD are retained; unspecified technical details remain PENDING_DESIGN.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provisional document allocation: provider M1-004; consumers M1-001, M1-002, M1-003, M1-005, M1-007, M1-008, M1-009, M1-010, M1-011, M1-012, M1-013, M1-014, M1-015, M1-016, M1-018, M1-019, M1-SYSTEM. Actual module/process/API topology is PENDING_DESIGN (minimum inputs 1–2). |
| Purpose / source requirement | Register sole active Codex CLI provider, statically route the DAG-provided capsule/role, audit every call and provision independent read-only Tier-2 review. Source: §4.3, §4.3.1 Phase 1, §4.3.2 Phase 1, §4.3.3, §4.3.4; sequencing §6.4. |
| Inputs: fields, types, units, required/optional, validation | PENDING_DESIGN — Architecture owns payloads, types, validation, units and API/IPC handoff (minimum inputs 1–2). Product input obligations remain in spec.md. |
| Outputs: fields, types, units, semantics, guarantees | PENDING_DESIGN — Architecture owns concrete outputs and technical guarantees (minimum inputs 2 and 4). Source-defined observable results remain in spec.md. |
| States and invariants | PENDING_DESIGN — Architecture owns runtime state, transitions and coordination (minimum inputs 1–3). Product invariants remain in spec.md. |
| Errors, timeout, retry, cancellation | PENDING_DESIGN — Architecture owns error structures, propagation, timeout/cancellation and duplicate handling (minimum inputs 2–3). Source failure/restart rules remain in spec.md. |
| Side effects and idempotency | PENDING_DESIGN — Architecture owns effect enforcement, writes, partial-write recovery and repeated-call mechanics (minimum inputs 2–5). Source effect restrictions remain in spec.md. |
| Compatibility and migration | Provisional r0 identity retained. PENDING_DESIGN — Architecture owns compatibility/migration representation (minimum inputs 1–2). Source acceptance is unchanged by realization choices; update consumers and invalidate affected evidence on material revision. |
| Machine-readable schema / source path | PENDING_DESIGN — No schema or application path is supplied. Architecture binds locations, schemas and environments (minimum inputs 1–2 and 6). |
| Provider/consumer verification responsibilities | PENDING_DESIGN — Architecture owns actual check entry points and fault-injection seams (minimum input 7). Required behavioral AC/V intent and evidence mapping remain in native plan.md/tasks.md; no executed result is claimed. |
| Open agreement questions | Architecture binds registry/provider/review types and reliable-usage detection. Run/Observation/stage/role/capsule attribution is local; attribution-only labels must not reach providers. Correlation and clean-request construction remain PENDING_DESIGN. No missing model ID is invented. |

Consumed agreements: [M1-IF-001@r0](../M1-001/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements). Definition-time and runtime usage differ as recorded in Section 3; reciprocal semantic dependencies are not full-task completion prerequisites.

Architecture reservation: [minimum inputs](../ARCHITECTURE_MINIMUM_INPUTS.txt), items 1-7, owns actual modules/code/processes, typed payload/API/error contracts, runtime coordination, storage/durability, security isolation, configuration realization and executable test entry points. These remain PENDING_DESIGN; no implementation mechanism is selected by this PRD r2 update.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| D01 / 2026-10-01 | Initial PRD r1 allocation; Architecture PENDING_SOURCE; user requests document preparation only | All native records; M1-IF-004@r0 | No runtime evidence exists; affected implementation and checks cannot pass before their definitions exist | UNASSIGNED; register architecture and inspect existing code before binding technical paths |
| D02 / 2026-10-01 | Architecture binds registry/provider/review types and reliable-usage detection. Run/Observation/stage/role/capsule attribution is local; attribution-only labels must not reach providers. Correlation and clean-request construction remain PENDING_DESIGN. No missing model ID is invented. | plan.md unresolved decisions; T001; relevant AC/V rows | Only dependent work is constrained; independent source/fixture preparation continues | UNASSIGNED; resolve from architecture or registered capsule/product policy, not guessed requirements |
| PRD-R2 / 2026-10-02 | §4.3.1-§4.3.4. Adds local Observation correlation, audited invocation and provider minimization; approved isolated endpoints do not change Codex. | AC-002, AC-004, AC-005; native plan/tasks correspondence; M1-IF-004@r0 | Invalidate affected earlier evidence if any; current candidate NOT_BUILT and runtime NOT_RUN. | UNASSIGNED; complete Architecture-dependent definitions before affected implementation. |

Progress is in tasks.md. No separate approval, review, handoff or implementation-checklist card is introduced.
