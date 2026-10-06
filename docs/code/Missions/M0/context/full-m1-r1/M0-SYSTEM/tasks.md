---
description: "TASK-native work and acceptance/evidence correspondence"
---
# Tasks: M0-SYSTEM — Integrated M1 validation and phase accounting

**TASK**: [TASK.md](TASK.md) | **Spec / Plan revisions**: r1 / r1
**Feature directory**: docs/code/Missions/M0/M0-SYSTEM/

Verification work is required by spec and plan. This is the sole implementation work list. Preparing these artifacts does not complete product work or establish runtime acceptance.

## Work Items

### Foundation / shared definitions

- [ ] T001 [US1] Read all allocated exact source clauses/global restrictions and owning IFs; freeze independent fixture labels, dependency/runtime prerequisites and relevant dataset/profile/source identities; all B/AC/V; docs/code/Missions/M0/M0-SYSTEM/plan.md and evidence/fixture-manifest.json.
- [ ] T002 [US1] Implement the owned/consumed r1 boundary representations and validated fixtures without authority duplication; all B/AC/V; docs/code/Missions/M0; tests/journeys/ai4research (proposed); docs/code/Missions/M0/M0-SYSTEM/evidence.

### Block B01 — FR-001

- [x] T003 [US1] Maintain a complete source-governed English Spec Kit program for the supplied M1 product in the M0 directory. B01, AC-001; `docs/code/Missions/M0`.
- [x] T004 [US1] Execute framework document validator BLOCK and native prerequisites; retain actual outcomes V01; AC-001, B01; `docs/code/Missions/M0/tools/validate_framework.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B02 — FR-002

- [ ] T005 [US1] Establish the Stage 0 real secured model boundary. B02, AC-002; `tests/journeys/ai4research/test_stage_exits.py`.
- [ ] T006 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V03; AC-002, B02; `tests/journeys/ai4research/test_stage_exits.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B03 — FR-003

- [ ] T007 [US1] Demonstrate real Node A -> mandatory verification/gating -> work Node B progression and all ten failure-injection categories. B03, AC-003; `tests/journeys/ai4research/test_gate_failure_injection.py`.
- [ ] T008 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V05; AC-003, B03; `tests/journeys/ai4research/test_gate_failure_injection.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B04 — FR-004

- [ ] T009 [US1] Establish Stage 2 request/assets -> accepted Research Brief -> initialized operational static graph. B04, AC-004; `tests/journeys/ai4research/test_stage_exits.py`.
- [ ] T010 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V07; AC-004, B04; `tests/journeys/ai4research/test_stage_exits.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B05 — FR-005

- [ ] T011 [US1] Establish evidence-to-hypothesis Stage 3. B05, AC-005; `tests/journeys/ai4research/test_stage_exits.py`.
- [ ] T012 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V09; AC-005, B05; `tests/journeys/ai4research/test_stage_exits.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B06 — FR-006

- [ ] T013 [US1] Establish Stage 4 bounded POC construction and mechanical acceptance. B06, AC-006; `tests/journeys/ai4research/test_stage_exits.py`.
- [ ] T014 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V11; AC-006, B06; `tests/journeys/ai4research/test_stage_exits.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B07 — FR-007

- [ ] T015 [US1] Establish Stage 5 empirical comparison and valid positive/negative scientific routes. B07, AC-007; `tests/journeys/ai4research/test_scientific_journeys.py`.
- [ ] T016 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V13; AC-007, B07; `tests/journeys/ai4research/test_scientific_journeys.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B08 — FR-008

- [ ] T017 [US1] Complete Stage 6 full user research lifecycle and traceable delivery. B08, AC-008; `tests/journeys/ai4research/test_scientific_journeys.py`.
- [ ] T018 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V15; AC-008, B08; `tests/journeys/ai4research/test_scientific_journeys.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B09 — FR-009

- [ ] T019 [US1] Establish Stage 7 installed operational surfaces, durability and local security. B09, AC-009; `tests/journeys/ai4research/test_operational_shell.py`.
- [ ] T020 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V17; AC-009, B09; `tests/journeys/ai4research/test_operational_shell.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B10 — FR-010

- [ ] T021 [US1] Establish Stage 8 and required Phase 2 local-isolated RSI Target 1 with protected referee. B10, AC-010; `tests/journeys/ai4research/test_rsi_journey.py`.
- [ ] T022 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V19; AC-010, B10; `tests/journeys/ai4research/test_rsi_journey.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B11 — FR-011

- [ ] T023 [US1] Account for and validate all six applicable Phase 3 integration efforts without destabilizing baseline. B11, AC-011; `tests/journeys/ai4research/test_dynamic_integrations.py`.
- [ ] T024 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V21; AC-011, B11; `tests/journeys/ai4research/test_dynamic_integrations.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B12 — FR-012

- [ ] T025 [US1] Produce product-required phase and M1 implementation reports derived from current evidence. B12, AC-012; `docs/code/Missions/M0/M0-SYSTEM/evidence`.
- [ ] T026 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V23; AC-012, B12; `tests/journeys/ai4research/test_phase_reports.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Connected boundaries

- [x] T027 [US2] Execute framework document validator BOUNDARY and native prerequisites, including links, single IF ownership and source-copy alignment; V02; inject `Detect missing clause allocation, stale source, broken native link, invented acceptance evidence or verification/gating equivalence.` and check recovery; B01, AC-001; `docs/code/Missions/M0/tools/validate_framework.py`, `evidence/RUN-ID.md`.
- [ ] T028 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V04; inject `Unavailable subscription/secure IPC is environment blocked and never a mock PASS.` and check recovery; B02, AC-002; `tests/journeys/ai4research/test_stage_exits.py`, `evidence/RUN-ID.md`.
- [ ] T029 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V06; inject `Malformed/stale/swapped/citation/budget/tool/environment/uncertain/delayed decision cases lock B with Tier 2 NOT_RUN on mandatory Tier 1 failure.` and check recovery; B03, AC-003; `tests/journeys/ai4research/test_gate_failure_injection.py`, `evidence/RUN-ID.md`.
- [ ] T030 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V08; inject `Material ambiguity/unreadable asset/missing verification blocks; no dataset download or live capability search.` and check recovery; B04, AC-004; `tests/journeys/ai4research/test_stage_exits.py`, `evidence/RUN-ID.md`.
- [ ] T031 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V10; inject `Unsupported claim/no feasible opportunity/missing threshold cannot advance to Builder.` and check recovery; B05, AC-005; `tests/journeys/ai4research/test_stage_exits.py`, `evidence/RUN-ID.md`.
- [ ] T032 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V12; inject `Prohibited module, undeclared effect, bad syntax or unavailable mandatory security blocks release.` and check recovery; B06, AC-006; `tests/journeys/ai4research/test_stage_exits.py`, `evidence/RUN-ID.md`.
- [ ] T033 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V14; inject `Corrupt/missing/favorable-substituted measurements halt as process evidence failure, not scientific rejection.` and check recovery; B07, AC-007; `tests/journeys/ai4research/test_scientific_journeys.py`, `evidence/RUN-ID.md`.
- [ ] T034 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V16; inject `Reject empty/irrelevant/fabricated report and any unexecuted-stage claim.` and check recovery; B08, AC-008; `tests/journeys/ai4research/test_scientific_journeys.py`, `evidence/RUN-ID.md`.
- [ ] T035 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V18; inject `No Windows authoring check proves POSIX tmux/isolation; missing native surface or mandatory check is unverified.` and check recovery; B09, AC-009; `tests/journeys/ai4research/test_operational_shell.py`, `evidence/RUN-ID.md`.
- [ ] T036 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V20; inject `Block fixture read/leak/referee/mutation/permissions/audit/resource/promotion bypass; violation halts affected session and requires explicit human clearance.` and check recovery; B10, AC-010; `tests/journeys/ai4research/test_rsi_journey.py`, `evidence/RUN-ID.md`.
- [ ] T037 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V22; inject `Unavailable required dependency is explicit BLOCKED; available unimplemented behavior is INCOMPLETE rather than silently future-scoped.` and check recovery; B11, AC-011; `tests/journeys/ai4research/test_dynamic_integrations.py`, `evidence/RUN-ID.md`.
- [ ] T038 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V24; inject `Reject report-only/checklist-only acceptance, gate-disabled ablations and excluded Future State implementation.` and check recovery; B12, AC-012; `tests/journeys/ai4research/test_phase_reports.py`, `evidence/RUN-ID.md`.

### System contribution

- [ ] T039 [US3] Integrate the exact component/IF/profile and evidence manifest into M0-SYSTEM, execute affected connected stage/complete-journey checks, and reassess invalidated evidence; all AC/B/V; `docs/code/Missions/M0/M0-SYSTEM/tasks.md`.

## Acceptance and Evidence Matrix

| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md) | B01; all participating IFs | T003 | V01 / T004; V02 / T027 | PASS | [RUN-20261006-FRAMEWORK-01](evidence/RUN-20261006-FRAMEWORK-01.md); documentary candidate only | Exact documentary/source baseline; no runtime evidence reused |
| [AC-002](spec.md) | B02; all participating IFs | T001, T002, T005 | V03 / T006; V04 / T028 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-003](spec.md) | B03; all participating IFs | T001, T002, T007 | V05 / T008; V06 / T029 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-004](spec.md) | B04; all participating IFs | T001, T002, T009 | V07 / T010; V08 / T030 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-005](spec.md) | B05; all participating IFs | T001, T002, T011 | V09 / T012; V10 / T031 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-006](spec.md) | B06; all participating IFs | T001, T002, T013 | V11 / T014; V12 / T032 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-007](spec.md) | B07; all participating IFs | T001, T002, T015 | V13 / T016; V14 / T033 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-008](spec.md) | B08; all participating IFs | T001, T002, T017 | V15 / T018; V16 / T034 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-009](spec.md) | B09; all participating IFs | T001, T002, T019 | V17 / T020; V18 / T035 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-010](spec.md) | B10; all participating IFs | T001, T002, T021 | V19 / T022; V20 / T036 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-011](spec.md) | B11; all participating IFs | T001, T002, T023 | V21 / T024; V22 / T037 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-012](spec.md) | B12; all participating IFs | T001, T002, T025 | V23 / T026; V24 / T038 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |

## Dependency Order and Execution Notes

Framework AC-001 uses T003/T004/T027 against the supplied documentary baseline; T001/T002 prepare runtime fixtures/boundaries for AC-002–AC-012 and are not prerequisites for documentary acceptance. Runtime order: T001 → T002 → each implementation/block-verification pair → connected boundaries → system contribution. Definitions can proceed independently of missing runtime services; actual boundary acceptance cannot. No [P] is preassigned because shared native infrastructure and governing profiles require scoped ownership. Future disjoint work may be marked [P] after exact paths/dependencies are established.

Resume through parent TASKS → this TASK → spec/plan → first unresolved native work item. Select the exact feature directory explicitly; a feature pointer is not a task lock. Do not run simultaneous feature-generator sessions in a shared checkout. Scope for this request is preparation only. Live-provider tests, publication, pushes, deployment and installed-product changes are not automatically authorized by generated tasks.

## Current Verification Conclusion

- Candidate identity: NOT_BUILT for runtime; authoring baseline 2cc0b8695d4000cc72af64eb781356697f7fd861.
- Required work complete: framework T003/T004/T027 complete; no product implementation work completed by preparation.
- Required AC/check coverage: framework AC-001 / V01 / V02 PASS with retained evidence; all runtime ACs/checks remain NOT_RUN.
- Conclusion: NOT_READY for product/runtime acceptance. Framework documentary acceptance is separately M0-SYSTEM/AC-001.
- Remaining limitations and next work IDs: T001–T002, then the ordered blocks; source/service-specific questions in TASK and plan constrain only dependent work.

## Evidence Invalidation

No prior runtime evidence exists for this generated revision. Any implementation/input/schema/interface/profile/model/test/configuration/dependency/acceptance change marks affected rows STALE and propagates through the parent dependency graph. Keep old observed runs, exact candidate identity and limitations. Do not turn missing mandatory service/check into PASS or N/A; exclusions require source basis.
