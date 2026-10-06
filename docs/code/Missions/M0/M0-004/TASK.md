# TASK: M0-004 — Bounded shared trial compiler/verifier runner

## 1. Identity

| Field | Value |
| --- | --- |
| TASK/revision/date | M0-004 / r3 / 2026-10-06 |
| Parent | [M0 joint Phase 1 / TRIAL-1 register](../TASKS.md) |
| Executor | Codex; bounded current trial implementation, collaborators assigned with disjoint code ownership |
| Current outcome | Execute only the two admitted trial CCs through one governed native-model integration/capture boundary under their frozen contract, scoped context and time/call limits. Retain M0-004 and M0-IF-004 identities. |
| Excluded work | No generated POC execution, POC sandbox implementation, shell/browsing/resource profiling, arbitrary tool execution, internal CC composition, uncontrolled loops, capability installation, dynamic routing, automatic retries, uncertain-call replay or producer-written release. |
| Current source authorities | [PRD Phase 1](../source/PRD%20-%20AI4Research.txt) and [TRIAL-1 immediate plan](../source/build-package/immediate-plan.md), the product and architecture views of one M0 objective / recorded source manifest |
| Product clause references / architecture interpretation | PRD 2.6, 4.1.4, 4.6.3; immediate-plan.md, capsules.md, placement.md, guard-design.md, principles.md; exact Phase 1 allocation is in source-coverage.json; other delivery phases are not activated |
| Checkout/base | D:\research\ai_for_research\jiuwenswarm / ai4r_xiaoyang / 2cc0b8695d4000cc72af64eb781356697f7fd861 |
| Affected paths | `jiuwenswarm/ai4research/runner.py`; `jiuwenswarm/ai4research/bridge.py`; `tests/integration_tests/ai4research/test_intent_trial.py`; `tests/unit_tests/ai4research/test_m0_004.py` |

## 2. Spec Kit registry

| Artifact | Registered path | Authority |
| --- | --- | --- |
| Feature | docs/code/Missions/M0/M0-004 | One colocated TASK directory |
| spec.md | [spec](spec.md) | Current ACs and predeclared criteria |
| plan.md | [plan](plan.md) | Blocks, decisions and verification procedures |
| tasks.md | [tasks](tasks.md) | Sole work/status/AC-to-evidence authority |
| evidence/ | docs/code/Missions/M0/M0-004/evidence/ | Actual observed runs; preserve historical r1 separately |
| Support | [research](research.md), [data model](data-model.md), [quickstart](quickstart.md) | Context only; no independent interface/acceptance authority |

## 3. Dependencies

| TASK / IF | Required contribution | Prerequisite scope | Work |
| --- | --- | --- | --- |
| [M0-001](../M0-001/TASK.md); [M0-IF-001@r2](../M0-001/TASK.md#m0-if-001-at-r2) | Audited Codex model bridge | Scoped r2 definition for independent design; actual same-candidate evidence before connected PASS | T001/T002 and participating B/V |
| [M0-002](../M0-002/TASK.md); [M0-IF-002@r2](../M0-002/TASK.md#m0-if-002-at-r2) | TRIAL-1 local identity, session authority and frozen configuration | Scoped r2 definition for independent design; actual same-candidate evidence before connected PASS | T001/T002 and participating B/V |
| [M0-003](../M0-003/TASK.md); [M0-IF-003@r2](../M0-003/TASK.md#m0-if-003-at-r2) | Trial capsule declarations and admitted two-definition library | Scoped r2 definition for independent design; actual same-candidate evidence before connected PASS | T001/T002 and participating B/V |

## 4. Embedded cross-module agreements

### M0-IF-004 at r2

| Property | Definition |
| --- | --- |
| Provider and consumers | M0-004; consumers: M0-006, M0-007, M0-SYSTEM, M0-TRIAL-1 |
| Purpose | Execute only the two admitted trial CCs through one governed native-model integration/capture boundary under their frozen contract, scoped context and time/call limits. Retain M0-004 and M0-IF-004 identities. |
| Inputs | BoundTrialInvocation: exact admitted CC pin, intent-node contract or verifier assignment, typed attributable inputs, finite permissions/limits and approved role. References validate exact SHA256, type/schema and run/subject attribution. Counts are integers, durations seconds, timestamps UTC. |
| Outputs | TrialInvocationObservation: candidate bytes/references, actual completion/tool/effect/timing observations, counts and reliable telemetry gaps; no producer-authored acceptance. Required identities are nonempty strings; optional unavailable telemetry has an explicit reason, never assumed zero. |
| States/invariants | Candidate differs from accepted. Two immutable CC pins; producer/verifier context separation; authority derives from host, not candidate fields. Required durable decision precedes exposure. |
| Errors/timeout/retry/cancellation | Typed invalid_input/incompatible_revision/ineligible_pin/environment_unavailable/policy_denied/timeout/cancelled/persistence_failed/delivery_unknown as applicable. Zero automatic compiler repair/replay; verifier malformed/uncertain cannot release. Cancellation differs from restart interruption. |
| Effects/idempotency | Only declared bounded model access and protected infrastructure writes. Client request reconciliation never re-executes uncertain work; changed payload under same identity is rejected. No tools/browsing/shell/POC/RSI effects. |
| Compatibility | Retained IF identity, scoped r2 implemented representation; required live evidence remains pending. Historical full-M1 r1 is context, not a live API. Required additional Phase 1 mechanisms need owned versioned contracts and affected verification; their product scope is already active. Separately phased mechanisms remain contextual. |
| Implementation schema | runner.py defines TrialRunner.invoke with frozen role/pin/model, exact invocation context/observation references and terminal outcomes; it consumes configuration/bridge/evidence owners. Paths are relative to jiuwenswarm/ai4research unless fully qualified. The owning r2 IF remains canonical; no parallel schemas/*.schema.json is generated. |
| Boundary verification | Provider odd V IDs, connected even V IDs in this plan; current SYSTEM candidate covers integration |
| Unresolved inputs | Q-TRIAL-MODEL-SECURITY: Existing native adapter source or container presence does not establish authenticated bounded model access or secure IPC. |

Consumed agreements: [M0-IF-001@r2](../M0-001/TASK.md#m0-if-001-at-r2); [M0-IF-002@r2](../M0-002/TASK.md#m0-if-002-at-r2); [M0-IF-003@r2](../M0-003/TASK.md#m0-if-003-at-r2); [M0-IF-005@r2](../M0-005/TASK.md#m0-if-005-at-r2); [M0-IF-006@r2](../M0-006/TASK.md#m0-if-006-at-r2); [M0-IF-007@r2](../M0-007/TASK.md#m0-if-007-at-r2). Runtime connections do not add broad implementation dependencies.

## 5. Changes and unresolved decisions

| ID | Source/question | Affected scope | Resolution/invalidation |
| --- | --- | --- | --- |
| USR-05 | Joint PRD Phase 1 / TRIAL-1 scope confirmation | Program allocation and component interpretation | r3 restores active product obligations under SYSTEM; implemented r2 IF and unchanged trial predicates are retained. USR-04 sole-authority interpretation is superseded. |
| USR-01/02 | Verification/gating and applicable intent rubric adaptation | Protected M0-007 and consumers | No extra CC, general equivalence, source authority or scientific feature |
| Q-TRIAL-MODEL-SECURITY | Existing native adapter source or container presence does not establish authenticated bounded model access or secure IPC. | AC-001, AC-002 and real connected acceptance | Verify the actual configured bridge, process ownership, denied tools/context access and protected credential/IPC boundary. If unavailable, report ENVIRONMENT_BLOCKED; continue explicitly labelled isolated wiring preparation. |

Historical criteria outside the active slice:

| Historical AC | Reason/disposition |
| --- | --- |
| AC-003 | Historical r1 criterion is not independently active. Its applicable Phase 1 obligations are active gaps owned by M0-SYSTEM/AC-022, M0-SYSTEM/AC-025, M0-SYSTEM/AC-027. Retain this ID as provenance only; no duplicate work or PASS/N/A claim. Phase 2 optimization/dynamic execution portions remain separate context. |

The sole work/evidence state is tasks.md. Current coding is authorized; commits/pushes/deployment are not.

## Joint Phase 1 allocation

USR-05 jointly activates PRD Delivery Phase 1 and the corresponding TRIAL-1 architecture view. This component retains its implemented Intent responsibilities and r2 interfaces. Its local exclusions limit this component realization; Phase 1 obligations beyond it are active owned gaps in [M0-SYSTEM AC-018 through AC-027](../M0-SYSTEM/spec.md), not future context. Exactly two authored CCs describes implemented TRIAL-1 only; it is not a Phase 1 capability ceiling. Phase 2 RSI and Phase 3 dynamic execution remain outside the selected Phase 1 target.

USR-05 changes program allocation, not the retained trial runtime or AC predicates. LOCAL-3 observations may be reused only for the same unchanged trial assertions after exact execution-input comparison; they cannot establish a new Phase 1 stage, full Brief, work Node B or end-to-end exit. The broadened SYSTEM documentary AC-001 is renewed at r3; [fresh alignment observations](../M0-SYSTEM/evidence/RUN-20261006-JOINT-ALIGNMENT-R3.md) establish documentary consistency only. New SYSTEM AC-018 through AC-027 remain unaccepted with NOT_RUN/BLOCKED statuses until their required work and connected checks are observed. Historical r1/r2 source interpretations and evidence are preserved; the former sole-authority interpretation is superseded.
