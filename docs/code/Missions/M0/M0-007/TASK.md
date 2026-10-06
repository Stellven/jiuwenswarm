# TASK: M0-007 — Protected intent fidelity profile, Verifier and durable trial release

## 1. Identity

| Field | Value |
| --- | --- |
| TASK/revision/date | M0-007 / r3 / 2026-10-06 |
| Parent | [M0 joint Phase 1 / TRIAL-1 register](../TASKS.md) |
| Executor | Codex; bounded current trial implementation, collaborators assigned with disjoint code ownership |
| Current outcome | Own the trial's protected fidelity/ambiguity profile, exact check assignment, deterministic-before-semantic checking, separately scoped read-only intent assessor, applicable upstream rubric adaptation and host-owned durable accepted-intent decision. Retain M0-007 and M0-IF-007 identities; verification findings and gating policy remain distinct responsibilities within the one trial Evaluator Gate. |
| Excluded work | No scientific evaluation or delivery, POC testing/import/sandbox checks, citation retrieval, full-M1 failure suite, recursive/ensemble/dynamic evaluator, verifier-authored repair, producer-approved criteria, hidden-fixture disclosure, RSI execution or assertion of independent model errors/calibrated universal truth. |
| Current source authorities | [PRD Phase 1](../source/PRD%20-%20AI4Research.txt) and [TRIAL-1 immediate plan](../source/build-package/immediate-plan.md), the product and architecture views of one M0 objective / recorded source manifest |
| Product clause references / architecture interpretation | PRD 4.2.1, 4.2.2, 4.2.6, 4.2.7, 4.2.8, 4.2.9, 4.3.4; immediate-plan.md, guard-design.md, capsules.md, failure-and-human.md, capsule/declaration.md, placement.md, principles.md; exact Phase 1 allocation is in source-coverage.json; other delivery phases are not activated |
| Checkout/base | D:\research\ai_for_research\jiuwenswarm / ai4r_xiaoyang / 2cc0b8695d4000cc72af64eb781356697f7fd861 |
| Affected paths | `jiuwenswarm/ai4research/verification/gate.py`; `jiuwenswarm/ai4research/verification/profile.json`; `jiuwenswarm/ai4research/verification/upstream-adaptation.json`; `jiuwenswarm/ai4research/verification/upstream/result-evaluator.md`; `jiuwenswarm/ai4research/verification/upstream/citation-reviewer.md`; `jiuwenswarm/ai4research/verification/upstream/LICENSE`; `jiuwenswarm/ai4research/intent/verifier.prompt.md`; `tests/unit_tests/ai4research/test_m0_007.py`; `tests/unit_tests/ai4research/test_m0_006.py`; `tests/unit_tests/ai4research/test_intent_compiler.py`; `tests/unit_tests/ai4research/test_m0_004.py`; `tests/unit_tests/ai4research/test_m0_005.py`; `tests/unit_tests/ai4research/test_runtime_security.py`; `tests/integration_tests/ai4research/test_intent_trial.py`; `tests/journeys/ai4research/test_intent_trial_frontend.py`; `tests/integration_tests/ai4research/test_m0_003_boundary.py`; `tests/journeys/ai4research/test_intent_trial_system.py`; `tests/fixtures/ai4research/intent/characterization/cases.json`; `jiuwenswarm/ai4research/characterization.py`; `tests/unit_tests/ai4research/test_characterization.py`; `tests/fixtures/ai4research/intent/characterization/locked-candidates.json` |

## 2. Spec Kit registry

| Artifact | Registered path | Authority |
| --- | --- | --- |
| Feature | docs/code/Missions/M0/M0-007 | One colocated TASK directory |
| spec.md | [spec](spec.md) | Current ACs and predeclared criteria |
| plan.md | [plan](plan.md) | Blocks, decisions and verification procedures |
| tasks.md | [tasks](tasks.md) | Sole work/status/AC-to-evidence authority |
| evidence/ | docs/code/Missions/M0/M0-007/evidence/ | Actual observed runs; preserve historical r1 separately |
| Support | [research](research.md), [data model](data-model.md), [quickstart](quickstart.md) | Context only; no independent interface/acceptance authority |

## 3. Dependencies

| TASK / IF | Required contribution | Prerequisite scope | Work |
| --- | --- | --- | --- |
| [M0-001](../M0-001/TASK.md); [M0-IF-001@r2](../M0-001/TASK.md#m0-if-001-at-r2) | Audited Codex model bridge | Scoped r2 definition for independent design; actual same-candidate evidence before connected PASS | T001/T002 and participating B/V |
| [M0-003](../M0-003/TASK.md); [M0-IF-003@r2](../M0-003/TASK.md#m0-if-003-at-r2) | Trial capsule declarations and admitted two-definition library | Scoped r2 definition for independent design; actual same-candidate evidence before connected PASS | T001/T002 and participating B/V |
| [M0-005](../M0-005/TASK.md); [M0-IF-005@r2](../M0-005/TASK.md#m0-if-005-at-r2) | TRIAL-1 durable state, exact evidence custody and minimal observations | Scoped r2 definition for independent design; actual same-candidate evidence before connected PASS | T001/T002 and participating B/V |

## 4. Embedded cross-module agreements

### M0-IF-007 at r2

| Property | Definition |
| --- | --- |
| Provider and consumers | M0-007; consumers: M0-001, M0-002, M0-003, M0-004, M0-005, M0-006, M0-SYSTEM, M0-TRIAL-1 |
| Purpose | Own the trial's protected fidelity/ambiguity profile, exact check assignment, deterministic-before-semantic checking, separately scoped read-only intent assessor, applicable upstream rubric adaptation and host-owned durable accepted-intent decision. Retain M0-007 and M0-IF-007 identities; verification findings and gating policy remain distinct responsibilities within the one trial Evaluator Gate. |
| Inputs | ExactIntentVerificationSubject: original text, exact candidate and required execution evidence, immutable contract/profile/check/source pins and disclosure scope. References validate exact SHA256, type/schema and run/subject attribution. Counts are integers, durations seconds, timestamps UTC. |
| Outputs | IntentVerificationAndGateDecision: deterministic findings; separate read-only semantic assessment with reasons/evidence_refs; protected final verdict/action; durable exact acceptance or halt receipt. Required identities are nonempty strings; optional unavailable telemetry has an explicit reason, never assumed zero. |
| States/invariants | Candidate differs from accepted. Two immutable CC pins; producer/verifier context separation; authority derives from host, not candidate fields. Required durable decision precedes exposure. |
| Errors/timeout/retry/cancellation | Typed invalid_input/incompatible_revision/ineligible_pin/environment_unavailable/policy_denied/timeout/cancelled/persistence_failed/delivery_unknown as applicable. Zero automatic compiler repair/replay; verifier malformed/uncertain cannot release. Cancellation differs from restart interruption. |
| Effects/idempotency | Only declared bounded model access and protected infrastructure writes. Client request reconciliation never re-executes uncertain work; changed payload under same identity is rejected. No tools/browsing/shell/POC/RSI effects. |
| Compatibility | Retained IF identity, scoped r2 implemented representation; required live evidence remains pending. Historical full-M1 r1 is context, not a live API. Required additional Phase 1 mechanisms need owned versioned contracts and affected verification; their product scope is already active. Separately phased mechanisms remain contextual. |
| Implementation schema | verification/gate.py defines strict Finding/Assessment and aggregate; verification/profile.json owns frozen F1-F6; upstream-adaptation.json pins scoped source logic. Durable release consumes M0-IF-005. Paths are relative to jiuwenswarm/ai4research unless fully qualified. The owning r2 IF remains canonical; no parallel schemas/*.schema.json is generated. |
| Boundary verification | Provider odd V IDs, connected even V IDs in this plan; current SYSTEM candidate covers integration |
| Unresolved inputs | SRC-GATE: Legacy quality-refusal, retry and fallback semantics can conflict with protected mandatory trial release.; Q-TRIAL-CHARACTERIZATION: No calibrated universal reliability threshold or supplied trial case catalogue establishes semantic correctness.; Q-UPSTREAM-RUBRICS: The required upstream bodies and exact source revision/content pins are not yet retained in the local trial profile support. |

Consumed agreements: [M0-IF-001@r2](../M0-001/TASK.md#m0-if-001-at-r2); [M0-IF-003@r2](../M0-003/TASK.md#m0-if-003-at-r2); [M0-IF-004@r2](../M0-004/TASK.md#m0-if-004-at-r2); [M0-IF-005@r2](../M0-005/TASK.md#m0-if-005-at-r2); [M0-IF-006@r2](../M0-006/TASK.md#m0-if-006-at-r2). Runtime connections do not add broad implementation dependencies.

## 5. Changes and unresolved decisions

| ID | Source/question | Affected scope | Resolution/invalidation |
| --- | --- | --- | --- |
| USR-05 | Joint PRD Phase 1 / TRIAL-1 scope confirmation | Program allocation and component interpretation | r3 restores active product obligations under SYSTEM; implemented r2 IF and unchanged trial predicates are retained. USR-04 sole-authority interpretation is superseded. |
| USR-01/02 | Verification/gating and applicable intent rubric adaptation | Protected M0-007 and consumers | No extra CC, general equivalence, source authority or scientific feature |
| SRC-GATE | Legacy refusal, retry and fallback semantics conflicted with mandatory trial release; active policy is now selected. | Active assignments and AC-001/AC-002/AC-006 | Resolved implementation: verification/gate.py performs protected aggregation of deterministic checks and exactly six attributable semantic findings for the same frozen original/candidate/profile/contract. RunStore alone commits an advancing exact subject after all mandatory findings PASS and both actual attempts succeed. Failed/uncertain conditions halt without replay, alternate model or producer waiver; archived epochs grant no active permission. |
| Q-TRIAL-CHARACTERIZATION | The finite independent fidelity and control corpus is selected; actual real measurements remain unobserved. | AC-003, AC-005, AC-009, AC-010 and AC-011 | Resolved design: cases.json freezes nine semantic categories and nine runtime/control categories with source-shaped outcomes, three predeclared verifier repetitions and no universal reliability threshold. locked-candidates.json binds independently authored exact candidate bytes/source spans. characterization.py measures only those nine verifier subjects, records every outcome/false acceptance/refusal, compiler NOT_RUN and no release capability. Actual protected real execution is BLOCKED/NOT_RUN; ordinary two-call client trial acceptance remains separately required. |
| Q-UPSTREAM-RUBRICS | Exact upstream bodies, revision/hash pins and scoped adaptation are retained; real adaptation measurements remain pending. | AC-010 and dependent intent-profile admission/characterization acceptance only | Resolved source preparation: retained result-evaluator.md and citation-reviewer.md from openJiuwen-ai/sciencediscovery revision 7a0324257eecb48b57f60b6a80ce2fff54e7dba7 bind exact SHA256 in upstream-adaptation.json and the protected profile. F1-F6 map applicable completeness, support, scope, uncertainty, evidence and instruction-resistance logic; science/statistics/citation-specific obligations are explicitly inapplicable to plain Intent. Local pin/disposition/fixture tests exist; actual real measurements remain BLOCKED and do not change gate policy. |

Historical criteria outside the active slice:

| Historical AC | Reason/disposition |
| --- | --- |
| AC-007 | Historical r1 criterion is not independently active. Its applicable Phase 1 obligations are active gaps owned by M0-SYSTEM/AC-023, M0-SYSTEM/AC-024, M0-SYSTEM/AC-027. Retain this ID as provenance only; no duplicate work or PASS/N/A claim. Phase 2 optimization/dynamic execution portions remain separate context. |
| AC-008 | Historical r1 criterion is not independently active. Its applicable Phase 1 obligations are active gaps owned by M0-SYSTEM/AC-019, M0-SYSTEM/AC-026, M0-SYSTEM/AC-027. Retain this ID as provenance only; no duplicate work or PASS/N/A claim. Phase 2 optimization/dynamic execution portions remain separate context. |

The sole work/evidence state is tasks.md. Current coding is authorized; commits/pushes/deployment are not.

## Joint Phase 1 allocation

USR-05 jointly activates PRD Delivery Phase 1 and the corresponding TRIAL-1 architecture view. This component retains its implemented Intent responsibilities and r2 interfaces. Its local exclusions limit this component realization; Phase 1 obligations beyond it are active owned gaps in [M0-SYSTEM AC-018 through AC-027](../M0-SYSTEM/spec.md), not future context. Exactly two authored CCs describes implemented TRIAL-1 only; it is not a Phase 1 capability ceiling. Phase 2 RSI and Phase 3 dynamic execution remain outside the selected Phase 1 target.

USR-05 changes program allocation, not the retained trial runtime or AC predicates. LOCAL-3 observations may be reused only for the same unchanged trial assertions after exact execution-input comparison; they cannot establish a new Phase 1 stage, full Brief, work Node B or end-to-end exit. The broadened SYSTEM documentary AC-001 is renewed at r3; [fresh alignment observations](../M0-SYSTEM/evidence/RUN-20261006-JOINT-ALIGNMENT-R3.md) establish documentary consistency only. New SYSTEM AC-018 through AC-027 remain unaccepted with NOT_RUN/BLOCKED statuses until their required work and connected checks are observed. Historical r1/r2 source interpretations and evidence are preserved; the former sole-authority interpretation is superseded.
