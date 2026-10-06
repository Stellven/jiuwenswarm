---
description: "Scoped trial work and acceptance/evidence correspondence"
---
# Tasks: M0-006 — Fixed trial contracts and gate-locked lifecycle

**TASK/spec/plan**: [TASK](TASK.md), [spec](spec.md), [plan](plan.md) / r3 (implemented interfaces remain r2)
**Feature**: docs/code/Missions/M0/M0-006

This list owns the component realization. The joint Phase 1 program also includes the active work in SYSTEM AC-018 through AC-027. Archived full-M1 records supply planning context, never automatic acceptance or an independent work queue.

## Work Items

### Foundation / definitions

- [x] T001 [US1] Observed renewed current definition/source/profile/fixture and exact local candidate freeze; current B/AC/V; plan.md. HEAD `2cc0b8695d4000cc72af64eb781356697f7fd861`, 316-input snapshot `1a2510b1dff775a97d00a8ef9254027ec84c0bd427facb633ec19025fcbe4d85`; [retained current execution evidence](evidence/RUN-20261006-RUNTIME-LOCAL-3.md). Real unavailable runtime/security/account identities and reasons are recorded, not substituted; no live acceptance follows.
- [x] T002 [US1] Implemented current owned/consumed representations and scoped fixtures; current B/AC/V; `jiuwenswarm/ai4research/application.py`; `jiuwenswarm/ai4research/http.py`; `jiuwenswarm/ai4research/service.py`; `tests/unit_tests/ai4research/test_m0_006.py`; `tests/unit_tests/ai4research/test_m0_005.py`; `tests/integration_tests/ai4research/test_intent_trial.py`; `tests/unit_tests/ai4research/test_headless_client.py`; `tests/journeys/ai4research/test_intent_trial_system.py`. Code/fixture presence does not establish live acceptance.

### Block B02

- [x] T005 [US1] Assemble the protected run-specific intent-node contract and separate verifier assignment before dispatch. B02, AC-002; `jiuwenswarm/ai4research/application.py`. Implemented scoped mechanism; required verification/live evidence remains separate.
- [x] T006 [US1] Observed execute V03 BLOCK; B02, AC-002; `tests/unit_tests/ai4research/test_m0_006.py`. All declared local mechanical assertions: 2 selected cases PASS, 0 failed/skipped, actual batch exit 0; [owning current observations](evidence/RUN-20261006-RUNTIME-LOCAL-3.md). Actual batch covered these cases; the planned individual selector was not separately executed. No model-fidelity claim.
- [x] T016 [US2] Observed execute V04 BOUNDARY; B02, AC-002; `tests/integration_tests/ai4research/test_intent_trial.py; tests/integration_tests/ai4research/test_intent_trial.py`; `tests/unit_tests/ai4research/test_m0_006.py`. All declared local mechanical assertions: 3 selected cases PASS, 0 failed/skipped, actual batch exit 0; [owning current observations](evidence/RUN-20261006-RUNTIME-LOCAL-3.md). Actual batch covered these cases; the planned individual selector was not separately executed. No model-fidelity claim.

### Block B03

- [x] T007 [US1] Freeze trial pins and requested/effective configuration while rechecking actual readiness and eligibility. B03, AC-003; `jiuwenswarm/ai4research/application.py`. Implemented scoped mechanism; required verification/live evidence remains separate.
- [ ] T008 [US1] PARTIAL: execute V05 BLOCK; B03, AC-003; `tests/unit_tests/ai4research/test_m0_006.py`. Actual renewed frozen local subset: 2 selected assertions PASS, 0 failed/skipped in the retained batch; [owning current observations](evidence/RUN-20261006-RUNTIME-LOCAL-3.md). Required real portion remains BLOCKED/NOT_RUN with zero provider calls; this task and whole check remain open.
- [ ] T017 [US2] PARTIAL: execute V06 BOUNDARY; B03, AC-003; `tests/integration_tests/ai4research/test_intent_trial.py; tests/unit_tests/ai4research/test_m0_006.py`. Actual renewed frozen local subset: 3 selected assertions PASS, 0 failed/skipped in the retained batch; [owning current observations](evidence/RUN-20261006-RUNTIME-LOCAL-3.md). Required real portion remains BLOCKED/NOT_RUN with zero provider calls; this task and whole check remain open.

### Block B04

- [x] T009 [US1] Expose accepted intent only after the exact advancing gate decision and artifact reference are durably committed. B04, AC-004; `jiuwenswarm/ai4research/application.py`. Implemented scoped mechanism; required verification/live evidence remains separate.
- [x] T010 [US1] Observed execute V07 BLOCK; B04, AC-004; `tests/unit_tests/ai4research/test_m0_006.py; tests/unit_tests/ai4research/test_m0_005.py`. All declared local mechanical assertions: 19 selected cases PASS, 0 failed/skipped, actual batch exit 0; [owning current observations](evidence/RUN-20261006-RUNTIME-LOCAL-3.md). Actual batch covered these cases; the planned individual selector was not separately executed. No model-fidelity claim.
- [x] T018 [US2] Observed execute V08 BOUNDARY; B04, AC-004; `tests/integration_tests/ai4research/test_intent_trial.py; tests/integration_tests/ai4research/test_intent_trial.py; tests/integration_tests/ai4research/test_intent_trial.py`; `tests/unit_tests/ai4research/test_m0_006.py`. All declared local mechanical assertions: 14 selected cases PASS, 0 failed/skipped, actual batch exit 0; [owning current observations](evidence/RUN-20261006-RUNTIME-LOCAL-3.md). Actual batch covered these cases; the planned individual selector was not separately executed. No model-fidelity claim.

### Block B05

- [x] T011 [US1] Halt trial dispatch on blocking faults and preserve original failure and in-flight evidence. B05, AC-005; `jiuwenswarm/ai4research/application.py`. Implemented scoped mechanism; required verification/live evidence remains separate.
- [x] T012 [US1] Observed execute V09 BLOCK; B05, AC-005; `tests/integration_tests/ai4research/test_intent_trial.py; tests/integration_tests/ai4research/test_intent_trial.py; tests/integration_tests/ai4research/test_intent_trial.py; tests/integration_tests/ai4research/test_intent_trial.py`. All declared local mechanical assertions: 18 selected cases PASS, 0 failed/skipped, actual batch exit 0; [owning current observations](evidence/RUN-20261006-RUNTIME-LOCAL-3.md). Actual batch covered these cases; the planned individual selector was not separately executed. No model-fidelity claim.
- [x] T019 [US2] Observed execute V10 BOUNDARY; B05, AC-005; `tests/integration_tests/ai4research/test_intent_trial.py; tests/integration_tests/ai4research/test_intent_trial.py; tests/integration_tests/ai4research/test_intent_trial.py; tests/integration_tests/ai4research/test_intent_trial.py`. All declared local mechanical assertions: 18 selected cases PASS, 0 failed/skipped, actual batch exit 0; [owning current observations](evidence/RUN-20261006-RUNTIME-LOCAL-3.md). Actual batch covered these cases; the planned individual selector was not separately executed. No model-fidelity claim.

### Block B06

- [x] T013 [US1] Preserve browser-independent work and restart-safe inspection with mode-correct failure routing. B06, AC-006; `jiuwenswarm/ai4research/application.py`. Implemented scoped mechanism; required verification/live evidence remains separate.
- [ ] T014 [US1] PARTIAL: execute V11 BLOCK; B06, AC-006; `tests/unit_tests/ai4research/test_headless_client.py`. Actual renewed frozen local subset: 15 selected assertions PASS, 0 failed/skipped in the retained batch; [owning current observations](evidence/RUN-20261006-RUNTIME-LOCAL-3.md). Required real portion remains BLOCKED/NOT_RUN with zero provider calls; this task and whole check remain open.
- [ ] T020 [US2] PARTIAL: execute V12 BOUNDARY; B06, AC-006; `tests/integration_tests/ai4research/test_intent_trial.py; tests/journeys/ai4research/test_intent_trial_system.py`. Actual renewed frozen local subset: 5 selected assertions PASS, 0 failed/skipped in the retained batch; [owning current observations](evidence/RUN-20261006-RUNTIME-LOCAL-3.md). Required real portion remains BLOCKED/NOT_RUN with zero provider calls; this task and whole check remain open.

### Block B07

- [x] T022 [US1] Execute only the fixed connected intent trial sequence with exactly two authored CCs. B07, AC-007; `jiuwenswarm/ai4research/application.py`. Implemented scoped mechanism; required verification/live evidence remains separate.
- [ ] T023 [US1] PARTIAL: execute V13 BLOCK; B07, AC-007; `tests/integration_tests/ai4research/test_intent_trial.py; tests/integration_tests/ai4research/test_intent_trial.py`. Actual renewed frozen local subset: 6 selected assertions PASS, 0 failed/skipped in the retained batch; [owning current observations](evidence/RUN-20261006-RUNTIME-LOCAL-3.md). Required real portion remains BLOCKED/NOT_RUN with zero provider calls; this task and whole check remain open.
- [ ] T024 [US2] PARTIAL: execute V14 BOUNDARY; B07, AC-007; `tests/integration_tests/ai4research/test_intent_trial.py; tests/integration_tests/ai4research/test_intent_trial.py; tests/journeys/ai4research/test_intent_trial_system.py`. Actual renewed frozen local subset: 7 selected assertions PASS, 0 failed/skipped in the retained batch; [owning current observations](evidence/RUN-20261006-RUNTIME-LOCAL-3.md). Required real portion remains BLOCKED/NOT_RUN with zero provider calls; this task and whole check remain open.

### System contribution

- [ ] T021 [US3] Integrate current pins/profiles/evidence into the scoped SYSTEM trial candidate and execute affected complete trial journeys; all current AC/B/V; docs/code/Missions/M0/M0-SYSTEM/tasks.md. PARTIAL: local wiring exists; complete scoped SYSTEM/live evidence remains BLOCKED/NOT_RUN.

## Acceptance and Evidence Matrix

| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-002](spec.md) | B02; M0-IF-006@r2 | T001, T002, T005 | V03 / T006; V04 / T016 | PASS | [Observed RUN-20261006-RUNTIME-LOCAL-3](evidence/RUN-20261006-RUNTIME-LOCAL-3.md); exact 316-input snapshot `1a2510b1dff775a97d00a8ef9254027ec84c0bd427facb633ec19025fcbe4d85`; both required local mechanical V checks observed PASS; current actual case allocation retained. | Current source/IF/runtime/test/profile/pin/dependency changes invalidate affected checks; prior LOCAL-1/LOCAL-2 and r1 are historical, not current PASS reuse. This AC PASS covers its declared local mechanical contract on LOCAL-3 only; integrated real trial acceptance remains BLOCKED. |
| [AC-003](spec.md) | B03; M0-IF-006@r2 | T001, T002, T007 | V05 / T008; V06 / T017 | BLOCKED | [Observed RUN-20261006-RUNTIME-LOCAL-3](evidence/RUN-20261006-RUNTIME-LOCAL-3.md); exact 316-input snapshot `1a2510b1dff775a97d00a8ef9254027ec84c0bd427facb633ec19025fcbe4d85`; local selected assertions PASS, whole required real check(s) BLOCKED/NOT_RUN. | Current source/IF/runtime/test/profile/pin/dependency changes invalidate affected checks; prior LOCAL-1/LOCAL-2 and r1 are historical, not current PASS reuse. Approved real model/container/fidelity observations missing; local controls do not complete this AC. |
| [AC-004](spec.md) | B04; M0-IF-006@r2 | T001, T002, T009 | V07 / T010; V08 / T018 | PASS | [Observed RUN-20261006-RUNTIME-LOCAL-3](evidence/RUN-20261006-RUNTIME-LOCAL-3.md); exact 316-input snapshot `1a2510b1dff775a97d00a8ef9254027ec84c0bd427facb633ec19025fcbe4d85`; both required local mechanical V checks observed PASS; current actual case allocation retained. | Current source/IF/runtime/test/profile/pin/dependency changes invalidate affected checks; prior LOCAL-1/LOCAL-2 and r1 are historical, not current PASS reuse. This AC PASS covers its declared local mechanical contract on LOCAL-3 only; integrated real trial acceptance remains BLOCKED. |
| [AC-005](spec.md) | B05; M0-IF-006@r2 | T001, T002, T011 | V09 / T012; V10 / T019 | PASS | [Observed RUN-20261006-RUNTIME-LOCAL-3](evidence/RUN-20261006-RUNTIME-LOCAL-3.md); exact 316-input snapshot `1a2510b1dff775a97d00a8ef9254027ec84c0bd427facb633ec19025fcbe4d85`; both required local mechanical V checks observed PASS; current actual case allocation retained. | Current source/IF/runtime/test/profile/pin/dependency changes invalidate affected checks; prior LOCAL-1/LOCAL-2 and r1 are historical, not current PASS reuse. This AC PASS covers its declared local mechanical contract on LOCAL-3 only; integrated real trial acceptance remains BLOCKED. |
| [AC-006](spec.md) | B06; M0-IF-006@r2 | T001, T002, T013 | V11 / T014; V12 / T020 | BLOCKED | [Observed RUN-20261006-RUNTIME-LOCAL-3](evidence/RUN-20261006-RUNTIME-LOCAL-3.md); exact 316-input snapshot `1a2510b1dff775a97d00a8ef9254027ec84c0bd427facb633ec19025fcbe4d85`; local selected assertions PASS, whole required real check(s) BLOCKED/NOT_RUN. | Current source/IF/runtime/test/profile/pin/dependency changes invalidate affected checks; prior LOCAL-1/LOCAL-2 and r1 are historical, not current PASS reuse. Approved real model/container/fidelity observations missing; local controls do not complete this AC. |
| [AC-007](spec.md) | B07; M0-IF-006@r2 | T001, T002, T022 | V13 / T023; V14 / T024 | BLOCKED | [Observed RUN-20261006-RUNTIME-LOCAL-3](evidence/RUN-20261006-RUNTIME-LOCAL-3.md); exact 316-input snapshot `1a2510b1dff775a97d00a8ef9254027ec84c0bd427facb633ec19025fcbe4d85`; local selected assertions PASS, whole required real check(s) BLOCKED/NOT_RUN. | Current source/IF/runtime/test/profile/pin/dependency changes invalidate affected checks; prior LOCAL-1/LOCAL-2 and r1 are historical, not current PASS reuse. Approved real model/container/fidelity observations missing; local controls do not complete this AC. |

## Dependency Order and Execution Notes

Freeze current definitions/fixtures → implement and verify each block → real connected boundaries → complete same-candidate trial journeys. Missing service blocks its checks only. Serialize shared production files and coordinate disjoint collaborators; no parallel generator sessions. Coding and required scoped validation are user-authorized. Comments/code comments/artifacts must be English.

## Current Verification Conclusion

- Candidate: observed HEAD `2cc0b8695d4000cc72af64eb781356697f7fd861` plus exact 316-input snapshot `1a2510b1dff775a97d00a8ef9254027ec84c0bd427facb633ec19025fcbe4d85` and retained dirty diff/dependencies. [Own observed record](evidence/RUN-20261006-RUNTIME-LOCAL-3.md) links immutable shared raw artifacts. HEAD alone is insufficient.
- Work: representation/implementation and wholly observed local verification items are checked; partial real model/security/characterization checks and complete SYSTEM contribution remain open. Each AC derives its result from both required V checks.
- Local observations: renewed combined batch 329 PASS, zero failed/skipped (62.76 seconds), plus current exact-candidate browser batch nine PASS, zero failed/skipped (26.19 seconds). [Per-V actual case allocation](evidence/RUN-20261006-RUNTIME-LOCAL-3.md) distinguishes whole local checks from local subsets of BLOCKED real checks; no separately run selector claim or prior candidate PASS reuse.
- Real prerequisites: required authenticated native model, supported protected POSIX/container IPC/custody and actual characterization portions remain BLOCKED. Mock/fixture-only standing never proves them.
- Conclusion: NOT_READY for complete connected trial acceptance; no full stage/M1 claim.
- Next work: satisfy approved native account/model and protected POSIX/container IPC/custody prerequisites, preserve exact admission/runtime pins and run the remaining required actual two-call, security/lifecycle/fault and independent characterization procedures. Changed execution inputs require affected revalidation.

## Evidence Invalidation

USR-05 changes program allocation, not the retained trial runtime or AC predicates. LOCAL-3 observations may be reused only for the same unchanged trial assertions after exact execution-input comparison; they cannot establish a new Phase 1 stage, full Brief, work Node B or end-to-end exit. The broadened SYSTEM documentary AC-001 is renewed at r3; [fresh alignment observations](../M0-SYSTEM/evidence/RUN-20261006-JOINT-ALIGNMENT-R3.md) establish documentary consistency only. New SYSTEM AC-018 through AC-027 remain unaccepted with NOT_RUN/BLOCKED statuses until their required work and connected checks are observed. Historical r1/r2 source interpretations and evidence are preserved; the former sole-authority interpretation is superseded.

Current candidate update: native configured-model/reroute enforcement and protected identity metadata corrections are included in the renewed LOCAL-3 snapshot `1a2510b1dff775a97d00a8ef9254027ec84c0bd427facb633ec19025fcbe4d85` and exact new declaration pins. Local observations and provisional receipt are renewed here; LOCAL-1/LOCAL-2 remain immutable historical candidates. Independently served-model identity is unavailable, never inferred. Required real measurements remain BLOCKED.

## Joint Phase 1 allocation

USR-05 jointly activates PRD Delivery Phase 1 and the corresponding TRIAL-1 architecture view. This component retains its implemented Intent responsibilities and r2 interfaces. Its local exclusions limit this component realization; Phase 1 obligations beyond it are active owned gaps in [M0-SYSTEM AC-018 through AC-027](../M0-SYSTEM/spec.md), not future context. Exactly two authored CCs describes implemented TRIAL-1 only; it is not a Phase 1 capability ceiling. Phase 2 RSI and Phase 3 dynamic execution remain outside the selected Phase 1 target.

USR-05 changes program allocation, not the retained trial runtime or AC predicates. LOCAL-3 observations may be reused only for the same unchanged trial assertions after exact execution-input comparison; they cannot establish a new Phase 1 stage, full Brief, work Node B or end-to-end exit. The broadened SYSTEM documentary AC-001 is renewed at r3; [fresh alignment observations](../M0-SYSTEM/evidence/RUN-20261006-JOINT-ALIGNMENT-R3.md) establish documentary consistency only. New SYSTEM AC-018 through AC-027 remain unaccepted with NOT_RUN/BLOCKED statuses until their required work and connected checks are observed. Historical r1/r2 source interpretations and evidence are preserved; the former sole-authority interpretation is superseded.
