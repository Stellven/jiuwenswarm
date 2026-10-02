# TASK: M1-018 - Offline implementation-only capsule improvement
PRD-derived preparation. This task records the requested initial document breakdown; it does not authorize or claim an implemented runtime. Read the complete registered source, not this extraction alone.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-018 / r1 / 2026-10-01 |
| Parent TASKS | [M1](../TASKS.md) |
| Executor / collaborators | Implementation executor UNASSIGNED; document preparation by Codex |
| Requested outcome and instruction/source | User request: build initial TASK and Spec Kit documents from PRD Full under Code SOP v2, filling source-supported content while reserving architecture decisions. Bounded product outcome: A researcher can evaluate a bounded child of a permitted capsule offline, inspect evidence and later choose whether to activate it through the existing admission/activation process. |
| Included scope / exclusions | Offline single-user RSI for explicitly eligible capsule implementation text/code only: bounded proposal, sealed fixed fixtures, immutable scoring, provenance and candidate handoff for manual activation. Excludes live workflow mutation, active-pointer changes by RSI, contract/schema/Verifier/operator mutation, model training, autonomous routing/budget changes and automatic publication. M1-003 owns standard admission/manual activation; this task submits candidates and cannot replace that authority. |
| PRD clause and architecture node references | [PRD-Full.r1](../sources/PRD-Full.r1.txt): §4.4 (all); shared §§1–2; sequencing §6.11; consumes capsule admission/evolution constraints §4.1 and frozen Gate policy §4.2. Baseline r1 / 2026-10-01 / 177840 bytes / SHA256 2F689644EF9517378F5CF16B28FA372F011811B9F9095AA0CA6996A6A10B13D9. Architecture source/node IDs: PENDING_SOURCE. |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / a8f36245a83358a606bf00f83a64b3353a41c4cd observed for document preparation; dirty-tree status is not an executable candidate identity |
| Affected code/document paths | This TASK and specs/M1-018-offline-rsi/{spec.md,plan.md,tasks.md}; actual implementation/test/configuration paths PENDING_DESIGN |

No separate authorization/review/handoff card is created. Implementation and execution have not been performed by this document-preparation task.

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | specs/M1-018-offline-rsi/ | One registered directory for this TASK |
| spec.md | [spec](../../../../specs/M1-018-offline-rsi/spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](../../../../specs/M1-018-offline-rsi/plan.md) | Behavior blocks, pending technical decisions and verification design |
| tasks.md | [tasks](../../../../specs/M1-018-offline-rsi/tasks.md) | Work, progress and AC-to-evidence correspondence |
| evidence/ | specs/M1-018-offline-rsi/evidence/ (create actual run records when checks execute) | Actual run records/raw artifacts; none yet |
| Supporting artifacts | None generated; schemas/research/data models PENDING_DESIGN only if needed | Subordinate to TASK/spec/plan authorities |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [M1-003](../M1-003/TASK.md); [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements) | Capsule mutation permissions, pinned parent/interface, admission and manual active-pointer operations | Permission/contract definition before candidate design; stable real implementation before evaluation, not completed M1 acceptance | B01–B06; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-005](../M1-005/TASK.md); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements) | Sealed production-record export and RSI evidence persistence interfaces | Definition before bindings; real exports needed for recorded-input replay, manually seeded fixtures permit cold start | B02/B06; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-002](../M1-002/TASK.md); [M1-IF-002@r0](../M1-002/TASK.md#4-embedded-cross-module-agreements) | Authorized offline workspace and effective hidden-fixture isolation | Architecture/security definition before oracle implementation; actual verified isolation before sealed evaluation | B02–B03; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-007](../M1-007/TASK.md); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements) | Frozen verifier/governance policy boundary | Definition of immutable exclusions before mutation checks; actual planted-violation checks before acceptance | B01/B05; T001/T002 and associated implementation/verification rows in native tasks.md |
| [M1-SYSTEM](../M1-SYSTEM/TASK.md) | Integrated candidate and complete research/required offline journeys | Final system verification follows relevant block and boundary readiness; full system acceptance is not a prerequisite for independent block preparation | T016; system contribution |

Definition-time agreements are needed before dependent design; runtime provider/consumer readiness is needed before real boundary checks. Neither means waiting for every provider task's final acceptance. r0 agreements remain preliminary until architecture binds them.

## 4. Embedded cross-module agreements
### M1-IF-018 at r0
This is a **preliminary PRD semantic agreement**, not a finalized schema, API or architecture contract. Architecture source is PENDING_SOURCE; representation and implementation are PENDING_DESIGN. Advancing the IF revision must update affected consumers.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provider M1-018; consumers M1-003, M1-005, M1-017, M1-SYSTEM |
| Purpose / source requirement | §4.4 (all); shared §§1–2; sequencing §6.11; consumes capsule admission/evolution constraints §4.1 and frozen Gate policy §4.2; bounded offline implementation-only capsule improvement handoff |
| Inputs: fields, types, units, required/optional, validation | An explicitly eligible, admitted parent capsule and its fixed interface/test suites; allowed mutation fields from M1-003; recorded node inputs/evidence exports from M1-005; target-specific split manifests and manually seeded hidden fixtures; one pinned session model; frozen scoring/governance policy. Exact fields/types/daemon calls PENDING_DESIGN. |
| Outputs: fields, types, units, semantics, guarantees | Versioned implementation-only child candidate, compatibility and fixed-policy evaluation evidence, hash-chained attempts with parent_hash lineage, trace/call/time records and rsi_pairs.jsonl. The oracle reveals aggregate counts only. Candidate submission references M1-003 admission; active version is never changed by the loop. |
| States and invariants | Offline only; contract/interface, rubric dimensions, Verifier, checks, hidden suites, policy, DAG/roles, model weights and routing/budgets remain fixed. Candidate may not see hidden fixtures; no auto-promotion; no product-memory learning. One code-file change per child; source-capped queries and paired repeats enforced. |
| Errors, timeout, retry, cancellation | Preserve observable source-defined failures and available evidence; use shared bounded execution/independent Gate semantics where applicable. No autonomous repair/unbounded retry. Exact error taxonomy, cancellation/timeout cleanup and encoding PENDING_DESIGN; no fabricated default budgets. |
| Side effects and idempotency | Write only offline candidate copies and RSI-specific lineage/evidence/export data; oracle may execute child in a fresh authorized process. No main product-memory writes, fixture mutation, live capsule mutation, upstream publication or active-pointer updates. Session cancellation, cleanup, restart and duplicate query accounting details PENDING_DESIGN; source limits must remain enforceable. |
| Compatibility and migration | r0 records source semantics only. Final typed agreement/versioning rules await architecture. Any input/output/behavior change updates owner and consumer documents and invalidates impacted boundary/system evidence; do not silently weaken PRD scope. |
| Machine-readable schema / source path | None created; PENDING_DESIGN. Any generated schema must implement this IF revision rather than establish a parallel authority. |
| Provider/consumer verification responsibilities | M1-018/V01, V02, V03, V04, V05, V06, V07, V08, V09 establish provider blocks; M1-018/V90 checks actual connected handoff; M1-SYSTEM owns complete integrated journeys. Consumers bind their checks to this revision after architecture, without duplicating AC authority. |
| Open agreement questions | M1-018-Q01, M1-018-Q02, M1-018-Q03 in section 5; field-level schema/API/code paths remain explicitly pending. |

Consumed agreements: [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-002@r0](../M1-002/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements). Registry admission/manual activation and shared infrastructure policies stay with their owning tasks.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| M1-018-Q01 / 2026-10-01 | Architecture is PENDING_SOURCE; effective oracle secrecy/privilege design, daemon/schema, runtime binding and code paths are PENDING_DESIGN. The source's same-user/no-sudo/POSIX premise is not verified isolation. | All blocks/checks, especially B03/V09, M1-IF-018 | Only affected bindings/implementation/checks; any changed source/IF invalidates affected rows and downstream evidence | UNASSIGNED; Architecture must realize source-required secrecy and authorized effects; record incompatible source constraints as a product decision rather than silently claiming security. |
| M1-018-Q02 / 2026-10-01 | §4.4.8 states 20% of 'the hidden set' plus at least 5 final-set failures without naming the first denominator explicitly. Preserve both thresholds; do not invent whether the percentage is loop-only or combined. | AC-008/V08, B02, M1-IF-018 headroom | Only affected bindings/implementation/checks; any changed source/IF invalidates affected rows and downstream evidence | UNASSIGNED; Clarify threshold interpretation or register a source-backed fixture policy before those boundary assertions; split seeding and other independent preparation continue. |
| M1-018-Q03 / 2026-10-01 | Exact benchmark/score aggregation under k=3 and the strict lower-bound rule must be bound to a frozen target policy without changing zero visible regressions, hidden-loop win or time tie-break ordering. | AC-001/003/005 and B04/B05 | Only affected bindings/implementation/checks; any changed source/IF invalidates affected rows and downstream evidence | UNASSIGNED; Bind source-compatible evaluation procedure in architecture/target fixture design; request product clarification only if an unprovided policy choice changes observable acceptance. |

Progress belongs in native tasks.md. Register material source/IF changes in the parent allocation/index and affected native artifacts; there is currently no runtime evidence to invalidate.

