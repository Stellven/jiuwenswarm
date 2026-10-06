---
description: "TASK-native work and acceptance/evidence correspondence"
---
# Tasks: M0-011 — Fixed-rubric screening and deterministic Top-1 ranking

**TASK**: [TASK.md](TASK.md) | **Spec / Plan revisions**: r1 / r1
**Feature directory**: docs/code/Missions/M0/M0-011/

Verification work is required by spec and plan. This is the sole implementation work list. Preparing these artifacts does not complete product work or establish runtime acceptance.

## Work Items

### Foundation / shared definitions

- [ ] T001 [US1] Read all allocated exact source clauses/global restrictions and owning IFs; freeze independent fixture labels, dependency/runtime prerequisites and relevant dataset/profile/source identities; all B/AC/V; docs/code/Missions/M0/M0-011/plan.md and evidence/fixture-manifest.json.
- [ ] T002 [US1] Implement the owned/consumed r1 boundary representations and validated fixtures without authority duplication; all B/AC/V; jiuwenswarm/agents/harness/common/tools/skill_toolkits.py; jiuwenswarm/agents/harness/common/prompt/prompt_builder.py; jiuwenswarm/ai4research/screening.py (proposed); tests/unit_tests/ai4research/test_screening.py (proposed); tests/integration_tests/ai4research/test_screening_boundary.py (proposed); tests/fixtures/ai4research/screening/calibration_manifest.json (proposed).

### Block B01 — FR-001

- [ ] T003 [US1] Consolidate near-duplicates once without erasing distinct mechanisms. B01, AC-001; `jiuwenswarm/ai4research/screening.py`.
- [ ] T004 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V01; AC-001, B01; `tests/unit_tests/ai4research/test_screening.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B02 — FR-002

- [ ] T005 [US1] Form typed grounded Idea Cards. B02, AC-002; `jiuwenswarm/ai4research/screening.py`.
- [ ] T006 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V03; AC-002, B02; `tests/unit_tests/ai4research/test_screening.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B03 — FR-003

- [ ] T007 [US1] State the specific scientific opportunity without commercial expansion. B03, AC-003; `jiuwenswarm/ai4research/screening.py`.
- [ ] T008 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V05; AC-003, B03; `tests/unit_tests/ai4research/test_screening.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B04 — FR-004

- [ ] T009 [US1] Score exactly the fixed three dimensions with reasons in one pass. B04, AC-004; `jiuwenswarm/ai4research/screening.py`.
- [ ] T010 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V07; AC-004, B04; `tests/unit_tests/ai4research/test_screening.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B05 — FR-005

- [ ] T011 [US1] Reject disallowed or unavailable candidate dependencies before ranking. B05, AC-005; `jiuwenswarm/ai4research/screening.py`.
- [ ] T012 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V09; AC-005, B05; `tests/unit_tests/ai4research/test_screening.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B06 — FR-006

- [ ] T013 [US1] Use a pure deterministic ranking helper preserving required Top-1 semantics. B06, AC-006; `jiuwenswarm/ai4research/screening.py`.
- [ ] T014 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V11; AC-006, B06; `tests/unit_tests/ai4research/test_screening.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B07 — FR-007

- [ ] T015 [US1] Preserve full selection and rejection evidence in Opportunity_Card. B07, AC-007; `jiuwenswarm/ai4research/screening.py`.
- [ ] T016 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V13; AC-007, B07; `tests/unit_tests/ai4research/test_screening.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B08 — FR-008

- [ ] T017 [US1] Provide fixed screening domain calibration to the common verification/gate composition. B08, AC-008; `jiuwenswarm/ai4research/screening.py`.
- [ ] T018 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V15; AC-008, B08; `tests/unit_tests/ai4research/test_screening.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B09 — FR-009

- [ ] T019 [US1] Keep pragmatic screening inside the bounded M1 responsibility. B09, AC-009; `jiuwenswarm/ai4research/screening.py`.
- [ ] T020 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V17; AC-009, B09; `tests/unit_tests/ai4research/test_screening.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Connected boundaries

- [ ] T021 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V02; inject `Unsupported dropped variant, invented replacement idea or iterative re-clustering fails the assigned obligation. Missing, swapped, unadmitted or stale screening_capsule.md identity prevents dispatch/release.` and check recovery; B01, AC-001; `tests/integration_tests/ai4research/test_screening_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T022 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V04; inject `Missing required fields, non-grounded new idea or unresolvable source cannot advance.` and check recovery; B02, AC-002; `tests/integration_tests/ai4research/test_screening_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T023 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V06; inject `Fabricated gap, business-case substitution or omitted assumptions are flagged.` and check recovery; B03, AC-003; `tests/integration_tests/ai4research/test_screening_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T024 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V08; inject `Invalid dimensions/scores/reasons, live code test or debate/voting cannot satisfy screening.` and check recovery; B04, AC-004; `tests/integration_tests/ai4research/test_screening_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T025 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V10; inject `High novelty/feasibility score cannot compensate for a denied mandatory dependency.` and check recovery; B05, AC-005; `tests/integration_tests/ai4research/test_screening_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T026 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V12; inject `Wrong arithmetic, lower-score winner, multiple winners or undeclared helper effect fails checks; no viable card causes non-advancing outcome.` and check recovery; B06, AC-006; `tests/integration_tests/ai4research/test_screening_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T027 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V14; inject `Detached citation, missing disposition, stale candidate set or interactive human override cannot advance.` and check recovery; B07, AC-007; `tests/integration_tests/ai4research/test_screening_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T028 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V16; inject `Screening author/proposer cannot waive rubric dimensions or use a semantic pass to excuse arithmetic/dependency failure.` and check recovery; B08, AC-008; `tests/integration_tests/ai4research/test_screening_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T029 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V18; inject `Observed forbidden behavior halts under common policy even if a selected card looks valid.` and check recovery; B09, AC-009; `tests/integration_tests/ai4research/test_screening_boundary.py`, `evidence/RUN-ID.md`.

### System contribution

- [ ] T030 [US3] Integrate the exact component/IF/profile and evidence manifest into M0-SYSTEM, execute affected connected stage/complete-journey checks, and reassess invalidated evidence; all AC/B/V; `docs/code/Missions/M0/M0-SYSTEM/tasks.md`.

## Acceptance and Evidence Matrix

| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md) | B01; M0-IF-011@r1 | T001, T002, T003 | V01 / T004; V02 / T021 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-002](spec.md) | B02; M0-IF-011@r1 | T001, T002, T005 | V03 / T006; V04 / T022 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-003](spec.md) | B03; M0-IF-011@r1 | T001, T002, T007 | V05 / T008; V06 / T023 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-004](spec.md) | B04; M0-IF-011@r1 | T001, T002, T009 | V07 / T010; V08 / T024 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-005](spec.md) | B05; M0-IF-011@r1 | T001, T002, T011 | V09 / T012; V10 / T025 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-006](spec.md) | B06; M0-IF-011@r1 | T001, T002, T013 | V11 / T014; V12 / T026 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-007](spec.md) | B07; M0-IF-011@r1 | T001, T002, T015 | V13 / T016; V14 / T027 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-008](spec.md) | B08; M0-IF-011@r1 | T001, T002, T017 | V15 / T018; V16 / T028 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-009](spec.md) | B09; M0-IF-011@r1 | T001, T002, T019 | V17 / T020; V18 / T029 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |

## Dependency Order and Execution Notes

T001 → T002 → each implementation/block-verification pair → connected boundaries → system contribution. Definitions can proceed independently of missing runtime services; actual boundary acceptance cannot. No [P] is preassigned because shared native infrastructure and governing profiles require scoped ownership. Future disjoint work may be marked [P] after exact paths/dependencies are established.

Resume through parent TASKS → this TASK → spec/plan → first unresolved native work item. Select the exact feature directory explicitly; a feature pointer is not a task lock. Do not run simultaneous feature-generator sessions in a shared checkout. Scope for this request is preparation only. Live-provider tests, publication, pushes, deployment and installed-product changes are not automatically authorized by generated tasks.

## Current Verification Conclusion

- Candidate identity: NOT_BUILT for runtime; authoring baseline 2cc0b8695d4000cc72af64eb781356697f7fd861.
- Required work complete: no product implementation work completed by preparation.
- Required AC/check coverage: all ACs mapped, all runtime required checks NOT_RUN.
- Conclusion: NOT_READY for product/runtime acceptance. Framework documentary acceptance is separately M0-SYSTEM/AC-001.
- Remaining limitations and next work IDs: T001–T002, then the ordered blocks; source/service-specific questions in TASK and plan constrain only dependent work.

## Evidence Invalidation

No prior runtime evidence exists for this generated revision. Any implementation/input/schema/interface/profile/model/test/configuration/dependency/acceptance change marks affected rows STALE and propagates through the parent dependency graph. Keep old observed runs, exact candidate identity and limitations. Do not turn missing mandatory service/check into PASS or N/A; exclusions require source basis.
