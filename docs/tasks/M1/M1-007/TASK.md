# TASK: M1-007 - Evaluator Gate and independent Verifier

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-007 / r1 / 2026-10-01 |
| Parent TASKS | [M1](../TASKS.md) |
| Executor / collaborators | UNASSIGNED for implementation; Codex prepares documents at the user's request |
| Requested outcome and instruction/source | Prepare English TASK/Spec Kit documents from PRD Full. Current action scope: documentation only; no application changes, runtime tests or commits. Future product outcome: Check node evidence with deterministic Tier 1 then independent read-only Tier 2, persist structured infrastructure verdicts and control advancement while preserving scientific conclusions. |
| Included scope / exclusions | Included: Check node evidence with deterministic Tier 1 then independent read-only Tier 2, persist structured infrastructure verdicts and control advancement while preserving scientific conclusions. Excluded: No reviewer swarms/voting, Auto Harness/live evaluator modification, schema repair/relaxation, autonomous engineering repair/refactoring, cheaper-model rerouting or learned thresholds; no legal/regulatory certification, per-gate web fact checking/replication panels, enterprise approval queues or automatic replay. All §4.2.10 autonomous multi-faceted evaluation is excluded. |
| PRD clause and architecture node references | [Registered PRD](../sources/PRD-Full.r1.txt): PRD r1 (2026-10-01), SHA256 2F689644EF9517378F5CF16B28FA372F011811B9F9095AA0CA6996A6A10B13D9, 177840 bytes; §4.2, §4.2.1–§4.2.9; §4.2.10 explicitly excluded; sequencing §6.4; global §1.3–§1.6 and §2.1–§2.12 apply. Architecture PENDING_SOURCE; architecture nodes are not invented. |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / a8f36245a83358a606bf00f83a64b3353a41c4cd; existing checkout; no tested runtime candidate prepared |
| Affected code/document paths | docs/tasks/M1/M1-007/TASK.md; specs/M1-007-evaluator-gate/spec.md, plan.md, tasks.md. Application/test/configuration paths PENDING_DESIGN after architecture and existing-code inspection. |

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | specs/M1-007-evaluator-gate/ relative to repository root | Exactly one feature for this TASK |
| spec.md | [spec](../../../../specs/M1-007-evaluator-gate/spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](../../../../specs/M1-007-evaluator-gate/plan.md) | Behavior blocks, future design and verification procedures |
| tasks.md | [tasks](../../../../specs/M1-007-evaluator-gate/tasks.md) | Work, progress and acceptance/evidence correspondence |
| evidence/ | specs/M1-007-evaluator-gate/evidence/ (create on actual verification) | Actual candidate run records/raw artifacts; none generated during preparation |
| Supporting artifacts | None | No parallel cards or invented schemas; future support remains subordinate |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [M1-003](../M1-003/TASK.md) / M1-IF-003@r0 | Capsule types/hashes/proof obligations/permissions and immutable verifier definition | Contract definitions before checks; not full runner completion | B01–B05; T001 and applicable boundary work |
| [M1-004](../M1-004/TASK.md) / M1-IF-004@r0 | Static independent Reviewer provisioning | Actual provider before real Tier-2 boundary check | B04; T001 and applicable boundary work |
| [M1-005](../M1-005/TASK.md) / M1-IF-005@r0 | Raw evidence and durable final verdict storage | Agree semantics first, actual persistence before connected acceptance | B05; T001 and applicable boundary work |
| [M1-006](../M1-006/TASK.md) / M1-IF-006@r0 | Stage Evidence Bundle producer/release/human-session consumer | Definition then real wiring; no circular whole-task completion prerequisite | B01/B05/B06; T001 and applicable boundary work |
| [M1-013](../M1-013/TASK.md) / M1-IF-013@r0 | Generated source and supplied compile/test evidence | Later connected artifact coverage only | B02/B03; T001 and applicable boundary work |
| [M1-014](../M1-014/TASK.md) / M1-IF-014@r0 | Baseline/treatment and preregistered protocol evidence | Later benchmark boundary coverage | B03; T001 and applicable boundary work |
| [M1-015](../M1-015/TASK.md) / M1-IF-015@r0 | Scientific verdict artifact, including valid negative result | Later scientific-failure boundary coverage | B04/B06; T001 and applicable boundary work |
| Master architecture / PENDING_SOURCE | Actual technical boundaries and implementation/check paths | Required only before affected implementation/real boundary checks; independent PRD preparation continues | T001 and unresolved technical work |
| [M1-SYSTEM](../M1-SYSTEM/TASK.md) | Candidate-wide journey verification | Final integration; not a prerequisite for block definitions or isolated checks | System contribution work in tasks.md |

Definition dependencies do not require a fully VERIFIED peer TASK. Define capsule/provider/evidence/gate semantics first; connect their implemented blocks later. This avoids treating runner -> Gate -> reviewer -> capsule as a circular sequence of whole-task completion.

## 4. Embedded cross-module agreements
### M1-IF-007 at r0
**Provisional PRD-semantic agreement.** This is not a final architecture, API or schema. Fields and rules explicitly present in the PRD are retained; unspecified technical details remain PENDING_DESIGN.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provider: M1-007. Consumers: M1-003, M1-006, M1-015, M1-016, M1-017, M1-SYSTEM. |
| Purpose / source requirement | Check node evidence with deterministic Tier 1 then independent read-only Tier 2, persist structured infrastructure verdicts and control advancement while preserving scientific conclusions. Source: §4.2, §4.2.1–§4.2.9; §4.2.10 explicitly excluded; sequencing §6.4. |
| Inputs: fields, types, units, required/optional, validation | Stage Evidence Bundle includes where applicable: run_id; stage_id/node_id; capsule ID/version/interface_hash; input/upstream contracts; output artifacts; acceptance/proof obligations; route/model metadata; declared/observed tools/effects; duration/time budget; stdout/stderr; test/compile/benchmark results and citation/evidence references. Exact field types/requiredness/units not stated by PRD remain PENDING_DESIGN. |
| Outputs: fields, types, units, semantics, guarantees | PRD minimum result: run_id/stage_id strings; gate_verdict (PASS, PASS_WITH_KNOWN_LIMITATIONS, FAIL, ENVIRONMENT_BLOCKED, INCONCLUSIVE); normalized_verdict (PASS, FAIL, BLOCKED, INCONCLUSIVE); routing_action (ADVANCE, HALT, ESCALATE_TO_HUMAN); tier_1 status PASS/FAIL/BLOCKED plus checks; tier_2 status PASS/FAIL/INCONCLUSIVE/NOT_RUN plus reasons/evidence_refs; failed_checks, warnings, known_limitations, evidence_refs and ISO-8601 timestamp. Nested item schema/API PENDING_DESIGN. |
| States and invariants | Mandatory Tier-1 failure means Tier 2 NOT_RUN with no reviewer call; otherwise independent read-only Tier 2 uses frozen policy/rubric. Final decision persists before transition. All mandatory checks must pass even with warnings. Valid scientific FAIL remains unchanged and receives infrastructure PASS. |
| Errors, timeout, retry, cancellation | Mandatory violation -> FAIL; missing/misconfigured runtime -> ENVIRONMENT_BLOCKED; insufficient evidence -> INCONCLUSIVE. All halt and may escalate to human_session. No evaluator edits/retries/automatic passes; exception/cancellation representation and unspecified profile values remain pending design/source inputs. |
| Side effects and idempotency | Executes declared checks and reviewer invocation, writes attributable verdict/evidence and controls release through Harness. Does not rewrite artifacts. Repeated evaluations may consume another call and are not presumed idempotent; run/node/hash binding prevents swapped evidence. |
| Compatibility and migration | Initial r0. Architecture may refine technical representation without altering product behavior. Material changes update this owner, parent allocation and affected consumers and invalidate corresponding boundary/system evidence. |
| Machine-readable schema / source path | None created; PENDING_DESIGN. Future generated representations implement this agreement and carry its effective IF revision. |
| Provider/consumer verification responsibilities | M1-007/V01–V19 cover source criteria; M1-007/V90 connects actual peers. Consumers provide actual inputs/state and their matching boundary evidence. M1-SYSTEM owns complete journeys. |
| Open agreement questions | Architecture binds envelope/result types, aggregation and Gate bootstrap without changing supplied vocabulary. Exact time limits, per-node fixed reviewer rubrics and supplied test entries must come from registered configuration/capsule sources; no thresholds are invented. |

Consumed agreements: [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-013@r0](../M1-013/TASK.md#4-embedded-cross-module-agreements); [M1-IF-014@r0](../M1-014/TASK.md#4-embedded-cross-module-agreements); [M1-IF-015@r0](../M1-015/TASK.md#4-embedded-cross-module-agreements). Definition-time and runtime usage differ as recorded in Section 3; reciprocal semantic dependencies are not full-task completion prerequisites.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| D01 / 2026-10-01 | Initial PRD r1 allocation; Architecture PENDING_SOURCE; user requests document preparation only | All native records; M1-IF-007@r0 | No runtime evidence exists; affected implementation and checks cannot pass before their definitions exist | UNASSIGNED; register architecture and inspect existing code before binding technical paths |
| D02 / 2026-10-01 | Architecture binds envelope/result types, aggregation and Gate bootstrap without changing supplied vocabulary. Exact time limits, per-node fixed reviewer rubrics and supplied test entries must come from registered configuration/capsule sources; no thresholds are invented. | plan.md unresolved decisions; T001; relevant AC/V rows | Only dependent work is constrained; independent source/fixture preparation continues | UNASSIGNED; resolve from architecture or registered capsule/product policy, not guessed requirements |

Progress is in tasks.md. No separate approval, review, handoff or implementation-checklist card is introduced.
