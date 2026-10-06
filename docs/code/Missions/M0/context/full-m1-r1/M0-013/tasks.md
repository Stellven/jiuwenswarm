---
description: "TASK-native work and acceptance/evidence correspondence"
---
# Tasks: M0-013 — Bounded Builder and mechanical POC artifact assembly

**TASK**: [TASK.md](TASK.md) | **Spec / Plan revisions**: r1 / r1
**Feature directory**: docs/code/Missions/M0/M0-013/

Verification work is required by spec and plan. This is the sole implementation work list. Preparing these artifacts does not complete product work or establish runtime acceptance.

## Work Items

### Foundation / shared definitions

- [ ] T001 [US1] Read all allocated exact source clauses/global restrictions and owning IFs; freeze independent fixture labels, dependency/runtime prerequisites and relevant dataset/profile/source identities; all B/AC/V; docs/code/Missions/M0/M0-013/plan.md and evidence/fixture-manifest.json.
- [ ] T002 [US1] Implement the owned/consumed r1 boundary representations and validated fixtures without authority duplication; all B/AC/V; jiuwenswarm/agents/harness/code/spec.py; jiuwenswarm/agents/harness/code/prompt/code_prompt_builder.py; jiuwenswarm/agents/harness/common/tools/command_tools.py; jiuwenswarm/server/sandbox/jiuwenbox_runner.py; jiuwenswarm/ai4research/builder.py (proposed); tests/unit_tests/ai4research/test_builder.py (proposed); tests/integration_tests/ai4research/test_builder_boundary.py (proposed); tests/fixtures/ai4research/builder/calibration_manifest.json (proposed).

### Block B01 — FR-001

- [ ] T003 [US1] Prepare a bounded construction workspace from accepted supplied resources. B01, AC-001; `jiuwenswarm/ai4research/builder.py`.
- [ ] T004 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V01; AC-001, B01; `tests/unit_tests/ai4research/test_builder.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B02 — FR-002

- [ ] T005 [US1] Generate one bounded patch using declared local CodeSearch. B02, AC-002; `jiuwenswarm/ai4research/builder.py`.
- [ ] T006 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V03; AC-002, B02; `tests/unit_tests/ai4research/test_builder.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B03 — FR-003

- [ ] T007 [US1] Wire an ordered baseline/treatment harness under the frozen protocol. B03, AC-003; `jiuwenswarm/ai4research/builder.py`.
- [ ] T008 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V05; AC-003, B03; `tests/unit_tests/ai4research/test_builder.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B04 — FR-004

- [ ] T009 [US1] Run mechanical readiness only and preserve failed checks. B04, AC-004; `jiuwenswarm/ai4research/builder.py`.
- [ ] T010 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V07; AC-004, B04; `tests/unit_tests/ai4research/test_builder.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B05 — FR-005

- [ ] T011 [US1] Package exact bounded construction artifacts for Benchmarking. B05, AC-005; `jiuwenswarm/ai4research/builder.py`.
- [ ] T012 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V09; AC-005, B05; `tests/unit_tests/ai4research/test_builder.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B06 — FR-006

- [ ] T013 [US1] Keep executable construction separate from analytical authorship and excluded lifecycle work. B06, AC-006; `jiuwenswarm/ai4research/builder.py`.
- [ ] T014 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V11; AC-006, B06; `tests/unit_tests/ai4research/test_builder.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B07 — FR-007

- [ ] T015 [US1] Supply Builder-specific independent verification and calibrated evidence. B07, AC-007; `jiuwenswarm/ai4research/builder.py`.
- [ ] T016 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V13; AC-007, B07; `tests/unit_tests/ai4research/test_builder.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Connected boundaries

- [ ] T017 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V02; inject `Unauthorized path, missing baseline/data, package installation/discovery or changed dependency declaration after freeze is rejected. Missing, swapped, unadmitted or stale poc_capsule.md identity prevents dispatch/release.` and check recovery; B01, AC-001; `tests/integration_tests/ai4research/test_builder_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T018 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V04; inject `Large autonomous refactor, unadmitted search, hidden dependency change or prohibited generated code is rejected before benchmarking.` and check recovery; B02, AC-002; `tests/integration_tests/ai4research/test_builder_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T019 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V06; inject `Measurement/threshold/data substitution, baseline-only/treatment-only harness or out-of-scope integration cannot pass.` and check recovery; B03, AC-003; `tests/integration_tests/ai4research/test_builder_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T020 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V08; inject `Failed syntax/mandatory readiness stops build advancement; no autonomous Coder-Reviewer repair or scientific dry-run occurs.` and check recovery; B04, AC-004; `tests/integration_tests/ai4research/test_builder_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T021 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V10; inject `Malformed/incomplete/changed bundle, unsafe archive path or premature empirical execution remains non-advancing.` and check recovery; B05, AC-005; `tests/integration_tests/ai4research/test_builder_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T022 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V12; inject `Analytical rewrite, weight construction, multi-file product integration or deployment effect fails role/effect checks.` and check recovery; B06, AC-006; `tests/integration_tests/ai4research/test_builder_boundary.py`, `evidence/RUN-ID.md`.
- [ ] T023 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V14; inject `Correct-looking bundle cannot compensate for failed mandatory compile/security/protocol check; missing confinement dependency blocks later empirical execution.` and check recovery; B07, AC-007; `tests/integration_tests/ai4research/test_builder_boundary.py`, `evidence/RUN-ID.md`.

### System contribution

- [ ] T024 [US3] Integrate the exact component/IF/profile and evidence manifest into M0-SYSTEM, execute affected connected stage/complete-journey checks, and reassess invalidated evidence; all AC/B/V; `docs/code/Missions/M0/M0-SYSTEM/tasks.md`.

## Acceptance and Evidence Matrix

| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md) | B01; M0-IF-013@r1 | T001, T002, T003 | V01 / T004; V02 / T017 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-002](spec.md) | B02; M0-IF-013@r1 | T001, T002, T005 | V03 / T006; V04 / T018 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-003](spec.md) | B03; M0-IF-013@r1 | T001, T002, T007 | V05 / T008; V06 / T019 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-004](spec.md) | B04; M0-IF-013@r1 | T001, T002, T009 | V07 / T010; V08 / T020 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-005](spec.md) | B05; M0-IF-013@r1 | T001, T002, T011 | V09 / T012; V10 / T021 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-006](spec.md) | B06; M0-IF-013@r1 | T001, T002, T013 | V11 / T014; V12 / T022 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-007](spec.md) | B07; M0-IF-013@r1 | T001, T002, T015 | V13 / T016; V14 / T023 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |

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
