# TASK: M0-TRIAL-1 — Connected intermediate Intent compiler and protected Verifier slice

## 1. Identity

| Field | Value |
| --- | --- |
| TASK/revision/date | M0-TRIAL-1 / r3 / 2026-10-06 |
| Parent | [M0 joint Phase 1 / TRIAL-1 register](../TASKS.md) |
| Executor | Codex; bounded current trial implementation, collaborators assigned with disjoint code ownership |
| Current outcome | Implement only immediate-plan.md TRIAL-1: native web text submission → one admitted Intent compiler invocation → deterministic checks → separate admitted intent verifier invocation → protected durable exact intermediate-intent acceptance or visible halt, with minimal sequential authenticated headless client and supporting runtime. |
| Excluded work | No complete Research Brief or Requirement compiler; no document/code/data intake, planner/research graph, search, screening, hypothesis, POC execution, scientific benchmarking/evaluation, Delivery CC, internal composition, dynamic routing, alternate verifier, RSI, full campaign dashboard, TUI/tmux shell or full-M1/stage completion claim. Exactly two authored CCs; ordinary control-plane retrieval is not a third CC or downstream work Node B. |
| Current source authorities | [PRD Phase 1](../source/PRD%20-%20AI4Research.txt) and [TRIAL-1 immediate plan](../source/build-package/immediate-plan.md), the product and architecture views of one M0 objective / recorded source manifest |
| Product clause references / architecture interpretation | PRD 3.0.1, 3.0.2, 3.1.1, 3.1.3, 3.1.5, 3.2.1, 3.2.2, 3.2.3, 3.2.4, 4.1.1, 4.1.2, 4.1.3, 4.1.4, 4.2.1, 4.2.2, 4.2.6, 4.2.7, 4.2.8, 4.2.9, 4.3.3, 4.3.4, 4.5.2, 4.5.3, 4.6.1, 4.6.2, 4.6.3, 4.6.4, 4.7.2, 4.7.3, 4.7.4, 5.1.1, 5.1.2, 5.2.2, 5.3.1, 5.3.2, 5.4.1, 5.4.2, 5.4.3, 5.6.3, 5.6.5, 6.3, 6.4, 6.5; immediate-plan.md, placement.md, capsules.md, guard-design.md, failure-and-human.md, automation.md; exact Phase 1 allocation is in source-coverage.json; other delivery phases are not activated |
| Checkout/base | D:\research\ai_for_research\jiuwenswarm / ai4r_xiaoyang / 2cc0b8695d4000cc72af64eb781356697f7fd861 |
| Affected paths | `jiuwenswarm/ai4research/intent/models.py`; `jiuwenswarm/ai4research/intent/compiler.prompt.md`; `jiuwenswarm/ai4research/intent/verifier.prompt.md`; `jiuwenswarm/ai4research/application.py`; `jiuwenswarm/ai4research/http.py`; `jiuwenswarm/ai4research/headless.py`; `jiuwenswarm/ai4research/service.py`; `tests/unit_tests/ai4research/test_m0_002.py`; `tests/unit_tests/ai4research/test_m0_005.py`; `tests/unit_tests/ai4research/test_m0_006.py`; `tests/unit_tests/ai4research/test_intent_compiler.py`; `tests/integration_tests/ai4research/test_intent_trial.py`; `tests/unit_tests/ai4research/test_m0_007.py`; `tests/unit_tests/ai4research/test_m0_004.py`; `tests/unit_tests/ai4research/test_m0_001.py`; `tests/unit_tests/ai4research/test_headless_client.py`; `tests/unit_tests/ai4research/test_m0_003.py`; `tests/integration_tests/ai4research/test_m0_002_boundary.py`; `tests/journeys/ai4research/test_intent_trial_frontend.py`; `tests/journeys/ai4research/test_intent_trial_system.py`; `jiuwenswarm/channels/web/frontend/src/features/intentTrial/IntentTrialPage.tsx`; `jiuwenswarm/channels/web/frontend/src/features/intentTrial/IntentTrialPage.css`; `tests/fixtures/ai4research/trial_support.py`; `tests/fixtures/ai4research/intent/characterization/cases.json`; `deploy/intent-trial/README.md`; `jiuwenswarm/ai4research/characterization.py`; `tests/unit_tests/ai4research/test_characterization.py`; `tests/fixtures/ai4research/intent/characterization/locked-candidates.json` |

## 2. Spec Kit registry

| Artifact | Registered path | Authority |
| --- | --- | --- |
| Feature | docs/code/Missions/M0/M0-TRIAL-1 | One colocated TASK directory |
| spec.md | [spec](spec.md) | Current ACs and predeclared criteria |
| plan.md | [plan](plan.md) | Blocks, decisions and verification procedures |
| tasks.md | [tasks](tasks.md) | Sole work/status/AC-to-evidence authority |
| evidence/ | docs/code/Missions/M0/M0-TRIAL-1/evidence/ | Actual observed runs; preserve historical r1 separately |
| Support | [research](research.md), [data model](data-model.md), [quickstart](quickstart.md) | Context only; no independent interface/acceptance authority |

## 3. Dependencies

| TASK / IF | Required contribution | Prerequisite scope | Work |
| --- | --- | --- | --- |
| [M0-001](../M0-001/TASK.md); [M0-IF-001@r2](../M0-001/TASK.md#m0-if-001-at-r2) | Audited Codex model bridge | Scoped r2 definition for independent design; actual same-candidate evidence before connected PASS | T001/T002 and participating B/V |
| [M0-002](../M0-002/TASK.md); [M0-IF-002@r2](../M0-002/TASK.md#m0-if-002-at-r2) | TRIAL-1 local identity, session authority and frozen configuration | Scoped r2 definition for independent design; actual same-candidate evidence before connected PASS | T001/T002 and participating B/V |
| [M0-003](../M0-003/TASK.md); [M0-IF-003@r2](../M0-003/TASK.md#m0-if-003-at-r2) | Trial capsule declarations and admitted two-definition library | Scoped r2 definition for independent design; actual same-candidate evidence before connected PASS | T001/T002 and participating B/V |
| [M0-004](../M0-004/TASK.md); [M0-IF-004@r2](../M0-004/TASK.md#m0-if-004-at-r2) | Bounded shared trial compiler/verifier runner | Scoped r2 definition for independent design; actual same-candidate evidence before connected PASS | T001/T002 and participating B/V |
| [M0-005](../M0-005/TASK.md); [M0-IF-005@r2](../M0-005/TASK.md#m0-if-005-at-r2) | TRIAL-1 durable state, exact evidence custody and minimal observations | Scoped r2 definition for independent design; actual same-candidate evidence before connected PASS | T001/T002 and participating B/V |
| [M0-006](../M0-006/TASK.md); [M0-IF-006@r2](../M0-006/TASK.md#m0-if-006-at-r2) | Fixed trial contracts and gate-locked lifecycle | Scoped r2 definition for independent design; actual same-candidate evidence before connected PASS | T001/T002 and participating B/V |
| [M0-007](../M0-007/TASK.md); [M0-IF-007@r2](../M0-007/TASK.md#m0-if-007-at-r2) | Protected intent fidelity profile, Verifier and durable trial release | Scoped r2 definition for independent design; actual same-candidate evidence before connected PASS | T001/T002 and participating B/V |

## 4. Embedded cross-module agreements

### M0-IF-020 at r2

| Property | Definition |
| --- | --- |
| Provider and consumers | M0-TRIAL-1; consumers: M0-SYSTEM |
| Purpose | Implement only immediate-plan.md TRIAL-1: native web text submission → one admitted Intent compiler invocation → deterministic checks → separate admitted intent verifier invocation → protected durable exact intermediate-intent acceptance or visible halt, with minimal sequential authenticated headless client and supporting runtime. |
| Inputs | AuthenticatedTextSubmission: nonempty original text; client_request_id; approved trial options; protected auth context, no client gate state. References validate exact SHA256, type/schema and run/subject attribution. Counts are integers, durations seconds, timestamps UTC. |
| Outputs | IntermediateIntentResult: run identity/status; accepted intermediate Intent preserving objective/outcome/scope/constraints/omissions/conflicts and original attribution, or durable reason; allowed bundle and cancellation result. Required identities are nonempty strings; optional unavailable telemetry has an explicit reason, never assumed zero. |
| States/invariants | Candidate differs from accepted. Two immutable CC pins; producer/verifier context separation; authority derives from host, not candidate fields. Required durable decision precedes exposure. |
| Errors/timeout/retry/cancellation | Typed invalid_input/incompatible_revision/ineligible_pin/environment_unavailable/policy_denied/timeout/cancelled/persistence_failed/delivery_unknown as applicable. Zero automatic compiler repair/replay; verifier malformed/uncertain cannot release. Cancellation differs from restart interruption. |
| Effects/idempotency | Only declared bounded model access and protected infrastructure writes. Client request reconciliation never re-executes uncertain work; changed payload under same identity is rejected. No tools/browsing/shell/POC/RSI effects. |
| Compatibility | Retained IF identity, scoped r2 implemented representation; required live evidence remains pending. Historical full-M1 r1 is context, not a live API. Required additional Phase 1 mechanisms need owned versioned contracts and affected verification; their product scope is already active. Separately phased mechanisms remain contextual. |
| Implementation schema | intent/models.py defines IntermediateIntent/Statement/SourceSpan and validate_intent; application.py projects exact accepted Intent/halt; http.py/headless.py implement the ordinary authenticated clients. Paths are relative to jiuwenswarm/ai4research unless fully qualified. The owning r2 IF remains canonical; no parallel schemas/*.schema.json is generated. |
| Boundary verification | Provider odd V IDs, connected even V IDs in this plan; current SYSTEM candidate covers integration |
| Unresolved inputs | Q-INTENT-CHARACTERIZATION: What independent labeled fixture set, semantic fidelity acceptance criteria and repetitions will be frozen for the real Intent/verifier characterization?; Q-REAL-READINESS: When are the approved authenticated real model route and enforceable local/container IPC and restricted context available for connected trial execution? |

Consumed agreements: [M0-IF-001@r2](../M0-001/TASK.md#m0-if-001-at-r2); [M0-IF-002@r2](../M0-002/TASK.md#m0-if-002-at-r2); [M0-IF-003@r2](../M0-003/TASK.md#m0-if-003-at-r2); [M0-IF-004@r2](../M0-004/TASK.md#m0-if-004-at-r2); [M0-IF-005@r2](../M0-005/TASK.md#m0-if-005-at-r2); [M0-IF-006@r2](../M0-006/TASK.md#m0-if-006-at-r2); [M0-IF-007@r2](../M0-007/TASK.md#m0-if-007-at-r2). Runtime connections do not add broad implementation dependencies.

## 5. Changes and unresolved decisions

| ID | Source/question | Affected scope | Resolution/invalidation |
| --- | --- | --- | --- |
| USR-05 | Joint PRD Phase 1 / TRIAL-1 scope confirmation | Program allocation and component interpretation | r3 restores active product obligations under SYSTEM; implemented r2 IF and unchanged trial predicates are retained. USR-04 sole-authority interpretation is superseded. |
| USR-01/02 | Verification/gating and applicable intent rubric adaptation | Protected M0-007 and consumers | No extra CC, general equivalence, source authority or scientific feature |
| Q-INTENT-CHARACTERIZATION | Independent exact subjects, finite case criteria and repetitions are now selected; protected real observations are pending. | Real semantic-quality acceptance only; schema/security/client/runtime preparation proceeds with explicitly labelled fixtures. | Resolved design: cases.json declares nine semantic and nine control categories; locked-candidates.json fixes nine independently authored exact original/candidate subjects and expected per-case findings, with three verifier repetitions before measurement. characterization.py has no mock CLI fallback, requires current protected admission/readiness and retains manifest, raw evidence and all 27 outcomes without accepted references. Its direct verifier evidence cannot prove compiler fidelity or whole two-call trial acceptance. Actual real measurements are BLOCKED/NOT_RUN; no scientific metric or post-result threshold change is introduced. |
| Q-REAL-READINESS | When are the approved authenticated real model route and enforceable local/container IPC and restricted context available for connected trial execution? | Actual model/security acceptance observations; mock wiring remains independently executable and honestly labeled. | Consume M0-001/M0-002 readiness evidence, exercise real calls only within authorized execution scope, and keep unavailable boundaries BLOCKED/NOT_RUN. |

The sole work/evidence state is tasks.md. Current coding is authorized; commits/pushes/deployment are not.

## Joint Phase 1 allocation

USR-05 jointly activates PRD Delivery Phase 1 and the corresponding TRIAL-1 architecture view. This component retains its implemented Intent responsibilities and r2 interfaces. Its local exclusions limit this component realization; Phase 1 obligations beyond it are active owned gaps in [M0-SYSTEM AC-018 through AC-027](../M0-SYSTEM/spec.md), not future context. Exactly two authored CCs describes implemented TRIAL-1 only; it is not a Phase 1 capability ceiling. Phase 2 RSI and Phase 3 dynamic execution remain outside the selected Phase 1 target.

USR-05 changes program allocation, not the retained trial runtime or AC predicates. LOCAL-3 observations may be reused only for the same unchanged trial assertions after exact execution-input comparison; they cannot establish a new Phase 1 stage, full Brief, work Node B or end-to-end exit. The broadened SYSTEM documentary AC-001 is renewed at r3; [fresh alignment observations](../M0-SYSTEM/evidence/RUN-20261006-JOINT-ALIGNMENT-R3.md) establish documentary consistency only. New SYSTEM AC-018 through AC-027 remain unaccepted with NOT_RUN/BLOCKED statuses until their required work and connected checks are observed. Historical r1/r2 source interpretations and evidence are preserved; the former sole-authority interpretation is superseded.
