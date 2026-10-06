---
description: "TASK-native work and acceptance/evidence correspondence"
---
# Tasks: M0-003 — Capability declarations and admitted library

**TASK**: [TASK.md](TASK.md) | **Spec / Plan revisions**: r1 / r1
**Feature directory**: docs/code/Missions/M0/M0-003/

Verification work is required by spec and plan. This is the sole implementation work list. Preparing these artifacts does not complete product work or establish runtime acceptance.

## Work Items

### Foundation / shared definitions

- [ ] T001 [US1] Read all allocated exact source clauses/global restrictions and owning IFs; freeze independent fixture labels, dependency/runtime prerequisites and relevant dataset/profile/source identities; all B/AC/V; docs/code/Missions/M0/M0-003/plan.md and evidence/fixture-manifest.json.
- [ ] T002 [US1] Implement the owned/consumed r1 boundary representations and validated fixtures without authority duplication; all B/AC/V; jiuwenswarm/symphony/adapter.py; jiuwenswarm/symphony/build.py; jiuwenswarm/ai4research/capsules.py (proposed); jiuwenswarm/ai4research/schemas/capsule-current.schema.json (proposed); jiuwenswarm/resources/ai4research/capsules/primary-registry.json (proposed); jiuwenswarm/resources/ai4research/capsules/<primary-role>/capsule.json and pinned prompt/alias resources (proposed).

### Block B01 — FR-001

- [ ] T003 [US1] Reconcile machine 2.9, semantic 2.10b and the complete declaration field inventory in one versioned current profile. B01, AC-001; `jiuwenswarm/ai4research/schemas/capsule-current.schema.json`.
- [ ] T004 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V01; AC-001, B01; `tests/unit_tests/ai4research/test_m0_003.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B02 — FR-002

- [ ] T005 [US1] Pin and verify the complete implementation and dependency closure. B02, AC-002; `jiuwenswarm/ai4research/capsules.py`.
- [ ] T006 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V03; AC-002, B02; `tests/unit_tests/ai4research/test_m0_003.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B03 — FR-003

- [ ] T007 [US1] Enforce strict admission and provisional standing for authored and RSI candidates. B03, AC-003; `jiuwenswarm/ai4research/capsules.py`.
- [ ] T008 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V05; AC-003, B03; `tests/unit_tests/ai4research/test_m0_003.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B04 — FR-004

- [ ] T009 [US1] Separate admission from human activation, suspension, deprecation and rollback. B04, AC-004; `jiuwenswarm/ai4research/capsules.py`.
- [ ] T010 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V07; AC-004, B04; `tests/unit_tests/ai4research/test_m0_003.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B05 — FR-005

- [ ] T011 [US1] Preserve server-enforced mutation and frozen governance boundaries. B05, AC-005; `jiuwenswarm/ai4research/capsules.py`.
- [ ] T012 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V09; AC-005, B05; `tests/unit_tests/ai4research/test_m0_003.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B06 — FR-006

- [ ] T013 [US1] Preserve composite meaning without granting unsupported runtime mechanisms. B06, AC-006; `jiuwenswarm/ai4research/capsules.py`.
- [ ] T014 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V11; AC-006, B06; `tests/unit_tests/ai4research/test_m0_003.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Connected boundaries

- [ ] T015 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V02; inject `Reject ambiguous migration, incompatible governance fields and legacy inert-budget bypass.` and check recovery; B01, AC-001; `tests/integration_tests/ai4research/test_m0_003_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T016 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V04; inject `Reject hash mismatch, missing dependency or unsupported external pin.` and check recovery; B02, AC-002; `tests/integration_tests/ai4research/test_m0_003_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T017 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V06; inject `No mocked/skipped/missing required check can certify a live capability.` and check recovery; B03, AC-003; `tests/integration_tests/ai4research/test_m0_003_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T018 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V08; inject `Reject self-activation, unknown standing action and deleted historical identity.` and check recovery; B04, AC-004; `tests/integration_tests/ai4research/test_m0_003_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T019 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V10; inject `Reject permission widening, overwritten parent or mutable referee dependency.` and check recovery; B05, AC-005; `tests/integration_tests/ai4research/test_m0_003_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T020 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V12; inject `Reject missing/recursive/ineligible members and author-granted generalist gate exemption.` and check recovery; B06, AC-006; `tests/integration_tests/ai4research/test_m0_003_boundary.py`, `evidence/RUN-ID.md`.

### System contribution

- [ ] T021 [US3] Integrate the exact component/IF/profile and evidence manifest into M0-SYSTEM, execute affected connected stage/complete-journey checks, and reassess invalidated evidence; all AC/B/V; `docs/code/Missions/M0/M0-SYSTEM/tasks.md`.

## Acceptance and Evidence Matrix

| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md) | B01; M0-IF-003@r1 | T001, T002, T003 | V01 / T004; V02 / T015 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-002](spec.md) | B02; M0-IF-003@r1 | T001, T002, T005 | V03 / T006; V04 / T016 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-003](spec.md) | B03; M0-IF-003@r1 | T001, T002, T007 | V05 / T008; V06 / T017 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-004](spec.md) | B04; M0-IF-003@r1 | T001, T002, T009 | V07 / T010; V08 / T018 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-005](spec.md) | B05; M0-IF-003@r1 | T001, T002, T011 | V09 / T012; V10 / T019 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-006](spec.md) | B06; M0-IF-003@r1 | T001, T002, T013 | V11 / T014; V12 / T020 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |

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
