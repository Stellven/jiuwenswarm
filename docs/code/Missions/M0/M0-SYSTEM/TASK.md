# TASK: M0-SYSTEM — Phase 1 integration, TRIAL-1 characterization and source-complete acceptance

## 1. Identity

| Field | Value |
| --- | --- |
| TASK/revision/date | M0-SYSTEM / r3 / 2026-10-06 |
| Parent | [M0 joint-source register](../TASKS.md) |
| Executor | Codex; documentation reconciliation now; future phase work follows the registered work order and disjoint ownership |
| Current outcome | One M0 objective has two source views: the user-supplied PRD Delivery Phase 1 defines the complete deterministic research product and Stages 0-7, while immediate-plan.md defines its bounded TRIAL-1 implementation/verification slice. Preserve the existing trial criteria and evidence as scoped contributions; explicitly own and plan unbuilt Phase 1 pipeline, workstation, invariant and report responsibilities without claiming full-M1 completion. |
| Excluded work | Phase 2 Local-Isolated RSI optimization/Stage 8 and Phase 3 dynamic/advanced integration remain separately contextual. No unbounded swarms, live graph mutation, autonomous repair/retry, automatic capsule promotion, model training, generated cloud deployment or external publication; full-M1 release/demo and Phase 2/3/M1 completion reports are not established by this Phase 1/TRIAL alignment. Exactly two authored CCs is the trial boundary only, not a global Phase 1 cap. |
| Current source authority | [User PRD](../source/PRD%20-%20AI4Research.txt), selected Delivery Phase 1/global/domain/Sections3-5/Stages0-7 clauses, together with [immediate plan](../source/build-package/immediate-plan.md); source hashes and semantic selections are owned by TASKS |
| Supporting architecture and context | The supplied build-package records refine the current trial and adopted D1-D15 amendments; exact applicable ranges/roles are recorded by TASKS. PRD Phase 2 RSI and Phase 3 integration remain separate contextual responsibilities, not current Phase 1 execution work. |
| Checkout/base | D:\research\ai_for_research\jiuwenswarm / ai4r_xiaoyang / 2cc0b8695d4000cc72af64eb781356697f7fd861 |
| Affected paths | docs/code/Missions/M0; existing jiuwenswarm/ai4research; jiuwenswarm/agents/harness/team/handlers/workflow_state.py; jiuwenswarm/agents/harness/team/handlers/workflow_monitor_handler.py; jiuwenswarm/start_services.py; jiuwenswarm/resources/config.yaml; native CLI/Web/TUI; actual trial tests; proposed full-product definitions/test ownership determined under T085 before implementation |

## 2. Spec Kit registry

| Artifact | Registered path | Authority |
| --- | --- | --- |
| Feature | docs/code/Missions/M0/M0-SYSTEM | One colocated TASK directory |
| spec.md | [spec](spec.md) | Current ACs and predeclared criteria |
| plan.md | [plan](plan.md) | Blocks, decisions and verification procedures |
| tasks.md | [tasks](tasks.md) | Sole work/status/AC-to-evidence authority |
| evidence/ | docs/code/Missions/M0/M0-SYSTEM/evidence/ | Actual observed runs; preserve historical r1 separately |
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
| [M0-TRIAL-1](../M0-TRIAL-1/TASK.md); [M0-IF-020@r2](../M0-TRIAL-1/TASK.md#m0-if-020-at-r2) | Connected intermediate Intent compiler and protected Verifier slice | Scoped r2 definition for independent design; actual same-candidate evidence before connected PASS | T001/T002 and participating B/V |

## 4. Embedded cross-module agreements

No new runtime IF is declared by this reconciliation. SYSTEM consumes current trial interfaces as bounded contributions, owns active Phase 1 gap integration/evidence, and owns full-product contract/interface design work T085 before dependent implementation. Existing r2 agreements do not imply complete Phase 1 compatibility; incompatible scope/schema extensions require their canonical owning TASK revisions.

Consumed agreements: [M0-IF-001@r2](../M0-001/TASK.md#m0-if-001-at-r2); [M0-IF-002@r2](../M0-002/TASK.md#m0-if-002-at-r2); [M0-IF-003@r2](../M0-003/TASK.md#m0-if-003-at-r2); [M0-IF-004@r2](../M0-004/TASK.md#m0-if-004-at-r2); [M0-IF-005@r2](../M0-005/TASK.md#m0-if-005-at-r2); [M0-IF-006@r2](../M0-006/TASK.md#m0-if-006-at-r2); [M0-IF-007@r2](../M0-007/TASK.md#m0-if-007-at-r2); [M0-IF-020@r2](../M0-TRIAL-1/TASK.md#m0-if-020-at-r2). Runtime connections remain scoped. AC-018 through AC-027 add explicit product integration responsibilities, not a claim that these eight agreements already define every full-product boundary.

## 5. Changes and unresolved decisions

| ID | Source/question | Affected scope | Resolution/invalidation |
| --- | --- | --- | --- |
| USR-04 | Historical immediate-plan-only interpretation | Retained r2 trial observations | Superseded by the explicit joint-source instruction; immutable prior runs retain their scoped meaning and no broad archive is restored |
| USR-JOINT | PRD Phase 1 and immediate-plan are two views of one M0 objective | AC-001, AC-018 through AC-027 and T085 | Activate explicit Phase 1 gap ownership here, preserve the trial criteria/IFs/evidence, and invalidate the affected documentary sole-authority acceptance pending current revalidation |
| D6-PLACEMENT | Native-only/no-persistent-database original wording versus authorized SQLite/files and one local service-container realization | AC-019/025/027, T085 | Preserve the authorized source-recorded technical deviation; native Task/Coding memory, append-only file projections, static scorecards and real-run exports remain required; no duplicate approval |
| D5-COMPILER | Original PRD one-shot versus authorized D5 bounded Intent/Requirement decomposition | AC-020, T085 | Record the already authorized product deviation, complete Brief contract, scoped contexts and combined frozen budgets; no duplicate approval request and no Intent-only Stage2 claim |
| USR-01/02 | Verification/gating and applicable intent rubric adaptation | Protected M0-007 and consumers | No extra CC, general equivalence, source authority or scientific feature |
| Q-TRIAL-SAME-CANDIDATE | What exact runnable package, active interfaces, component/dependency/profile/configuration pins and test/fixture digest identify the connected trial candidate? | AC-002 and AC-013 through AC-017 | Freeze one candidate manifest including relevant dirty code/test/configuration hashes, installed/native dependency versions, actual model route and environment before integrated execution; changes invalidate affected evidence. Source-only or isolated block results remain labelled and do not close system acceptance. |
| Q-TRIAL-CHARACTERIZATION-POLICY | Which independently labelled finite cases, repetitions and measured semantic fidelity/injection acceptance criteria are frozen by M0-TRIAL-1 before evaluation? | AC-014 and semantic acceptance/refusal observations in AC-013 | The business owner chooses and records source-shaped development acceptance policy before candidate measurement, covers every immediate-plan L114 category, preserves false acceptance/refusal and makes no unsupported numerical reliability claim. Missing policy blocks dependent semantic characterization only. |
| Q-TRIAL-REAL-READINESS | Are the approved authenticated actual baseline model route and protected local/container IPC/runtime ready for the packaged trial? | AC-002 and real model-backed portions of AC-013/014/017 | Execute actual readiness and secure-boundary probes on the same candidate. Continue independent native records/custody/failure preparation, retain mock wiring as mock, and record missing real prerequisites BLOCKED/NOT_RUN. |

Historical criterion identities retained without reactivation:

| Historical AC | Reason/disposition |
| --- | --- |
| AC-003 | Historical r1 complete Stage1 criterion remains archived; current joint gap is AC-019, including actual worker Node A -> Gate -> worker Node B. Verifier/result retrieval is never B. |
| AC-004 | Historical r1 Stage2 criterion remains archived; active intake/fullBrief/staticDAG gap is AC-020, not current Intent-only evidence. |
| AC-005 | Historical r1 Stage3 criterion remains archived; active search/screening/hypothesis gap is AC-021. |
| AC-006 | Historical r1 Stage4 criterion remains archived; active dedicated Builder/POC gap is AC-022. |
| AC-007 | Historical r1 Stage5 criterion remains archived; active benchmark/scientific-positive/negative gap is AC-023. |
| AC-008 | Historical r1 Stage6 criterion remains archived; active Delivery/fullresearch gap is AC-024, while trial return stays control plane. |
| AC-009 | Historical r1 Stage7 criterion remains archived; active native workstation/shell gap is AC-025; AC-017 stays narrow trial packaging. |
| AC-010 | Stage8/Phase2RSI remains separate context; no optimization or hidden-referee trial is activated by this reconciliation. |
| AC-011 | Phase3dynamic/advanced integration remains separate context; trial/fullPhase1 do not prove those exits. |
| AC-012 | Historical whole-M1 reports remain context; the active Phase_1_Completion_Report and Phase1 exit are newly AC-026, with no fullM1 claim. |

The sole work/evidence state is tasks.md. This turn reconciles documentation only; new Phase 1 work is planned and unexecuted. Prior implementation observations remain scoped; no provider calls, commits, pushes or deployment are authorized by this documentation turn.

## 6. Active Phase 1 gap ownership

AC-018 through AC-025 own source-defined Stages0-7, AC-026 owns Phase1 completion/report accounting, and AC-027 owns cross-stage domain/global obligations. Their exact selected productRefs/phase1Units are registered by TASKS and their criteria/procedures/work are colocated here. T085 designs and decomposes full-product responsibilities/contracts/interfaces/independent fixtures before dependent stage work. Archived M0-008 through M0-017 are semantic references only; they are neither prerequisites nor an active work queue. Existing library/runner/gate/state/native shell code is an audited extension anchor, not proof the missing duties are implemented.
