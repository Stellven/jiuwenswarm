---

description: "TASK-native work and acceptance/evidence correspondence"

---

# Tasks: M1-003 - Qualified ingestion and complete bounded Intention Compiler

**TASK**: [TASK.md](TASK.md) | **Spec / Plan revisions**: r3 / r3 | **Tasks revision/date**: r2 / 2026-10-16

**Feature directory**: docs/code/Missions/M1/M1-003/

Verification, testing, integration and applicable benchmarks are explicitly required by the invoked prompt/spec/plan. This is the sole implementation work list and AC-to-evidence authority. Qualified sequential T IDs apply Code SOP v2. Checkmarks mean performed work; AC acceptance requires current PASS for every required check. No additional reviewer/approval/commit gate exists.

## Work Items

The native template is organized by dependency-ordered blocks with user-story labels. Shared blocks serve the listed stories; story completion dependencies and independent criteria appear below. Construct tests before implementing their target behavior, verify blocks as soon as dependencies permit, then connect actual boundaries. Initial [P] markers are withheld until disjoint ownership and prerequisites are satisfied.

### Foundation / shared definitions

- [ ] M1-003/T001 Resolve the final qualified-intake/Intent/Brief/default-policy source versions and protected compiler fixture custody. Prepare exact stored upload/text/resource identities and independently labelled source cases; record live native/model and conditional advanced dependencies separately; paths: `tests/fixtures/research/compiler/`, `docs/code/Missions/M1/M1-003/evidence/<RUN_ID>/manifest.json`.

### Block M1-003/B01 - US1

- [ ] M1-003/T002 [US1] Construct unit and actual upload-boundary qualification tests before extraction/intake code. Freeze text/Markdown/PDF originals, strict UTF-8 and code-point counterparts, malformed/encrypted/textless PDFs, duplicate refs, optional rejection and required failure. Assert extraction happens once and qualification verifies identical stored UTF-8/text_sha256 without re-extraction; refs: M1-003/B01, M1-003/AC-001, M1-003/V01, M1-003/V07; also serves US2; after M1-003/T001; paths: `tests/unit_tests/research/test_intake.py`, `tests/integration/research/test_intake.py`, `tests/fixtures/research/compiler/intake/`.

### Block M1-003/B02 - US1

- [ ] M1-003/T003 [US1] Construct Intent schema/ref/span/readiness tests before the Intent carrier/checks. Pin independently counted Unicode code-point spans including astral and combining text, malformed spans and local IDs, missing purpose and blocked readiness; refs: M1-003/B02, M1-003/AC-002, M1-003/AC-003, M1-003/AC-005, M1-003/V02; also serves US2; after M1-003/T001; paths: `tests/unit_tests/research/test_intent_checks.py`, `tests/fixtures/research/compiler/intent/`.

### Block M1-003/B03 - US1

- [ ] M1-003/T004 [US1] Construct Requirements coverage/default/acceptance/evidence tests before the Requirements carrier. Freeze lost constraints, unresolved dispositions, mandatory links, qualitative comparisons, authorized default pointers, conflicting instructions and invented purpose/metric/hardware counterparts; refs: M1-003/B03, M1-003/AC-003, M1-003/AC-004, M1-003/AC-005, M1-003/V03; also serves US2; after M1-003/T001; paths: `tests/unit_tests/research/test_requirements_checks.py`, `tests/fixtures/research/compiler/requirements/`.

### Block M1-003/B04 - US1

- [ ] M1-003/T005 [US1] Construct compiler aggregate, combined-budget, idempotent submit/handoff and actual live/fault/binding/mode boundary tests before orchestration. Freeze private compiler-challenges-v1 expectations, independent three-fresh-run live procedure and explicit eval-only failures; assert zero downstream on invalid/uncommitted Intent or Brief; refs: M1-003/B04, M1-003/AC-003, M1-003/AC-005, M1-003/AC-006, M1-003/AC-008, M1-003/V04, M1-003/V05, M1-003/V08, M1-003/V09, M1-003/V10, M1-003/V11; also serves US2; after M1-003/T001; paths: `tests/unit_tests/research/test_compiler.py`, `tests/unit_tests/research/test_compiler_handoff.py`, `tests/integration/research/test_compiler_live.py`, `tests/integration/research/test_compiler_faults.py`, `tests/integration/research/test_compiler_binding.py`, `tests/integration/research/test_intake_modes.py`, `tests/fixtures/research/compiler/challenges/`, `tests/fixtures/research/compiler/faults/`. C008: construct gating_failures cases for two workers plus both independent reviews, insufficient configured aggregate/run remainder, worker overspend and zero downstream unauthorized call. Keep exact worker pins and no numerical compiler default; extend tests/integration/research/test_compiler_faults.py before consumer changes.

### Block M1-003/B05 - US1

- [ ] M1-003/T006 [US1] Construct absent/incompatible/adopted-module adapter tests and conditional actual advanced integration tests before the adapter. Track each classification, local/history filtering, native Leader clarification and Planner/Cluster handoff item separately; fake compatibility proves adapter logic only; refs: M1-003/B05, M1-003/AC-007, M1-003/AC-008, M1-003/V06, M1-003/V12; also serves US2; after M1-003/T001; paths: `tests/unit_tests/research/test_advanced_compiler_adapter.py`, `tests/integration/research/test_advanced_compiler.py`, `tests/fixtures/research/compiler/advanced/`.

### Block M1-003/B01 - US1

- [ ] M1-003/T007 [US1] Implement the canonical upload-time strict UTF-8/text-layer PDF extractor in intake.py, reusing pdfplumber 0.11.9. Bound its process, preserve original and extracted bytes and record parser version/options/identities; no OCR, semantic dedup or second decoder; refs: M1-003/B01, M1-003/AC-001; also serves US2; after M1-003/T002; provider/check prerequisites: M1-002/B01/B02 trusted capture/validators/state implementations before real qualification; M1-006 controlled upload/auth boundary before V07; Locked pdfplumber 0.11.9 and bounded extraction process; no model prerequisite for qualification; paths: `jiuwenswarm/research/intake.py`.

- [ ] M1-003/T008 [US1] Implement authorized live upload and separated resource qualification, exact stored text_sha256 verification, unique scoped source/resource refs and explicit optional rejections. Refuse raw/foreign/deleted/stale paths and required failures before any worker; provide the protected extractor to M1-006 through ResearchService without editing its HTTP client; refs: M1-003/B01, M1-003/AC-001; also serves US2; after M1-003/T007; paths: `jiuwenswarm/research/intake.py`.

### Block verification - US1

- [ ] M1-003/T009 [US1] Execute M1-003/V01 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-003/B01, M1-003/AC-001, M1-003/V01; also serves US2; after M1-003/T002, M1-003/T008; paths: `tests/unit_tests/research/test_intake.py`, `docs/code/Missions/M1/M1-003/evidence/<RUN_ID>/manifest.json`.

### Block M1-003/B02 - US1

- [ ] M1-003/T010 [US1] Implement the source-pinned Intent work carrier and immutable declaration/body assets, with fidelity self-review, exact qualified-context inputs and source-admitted budgets. Register via M1-002 without giving the carrier admission/gate authority; refs: M1-003/B02, M1-003/AC-002, M1-003/AC-003, M1-003/AC-005; also serves US2; after M1-003/T003, M1-003/B01:implementation, M1-003/T005; provider/check prerequisites: M1-002 admitted carrier/check registration and common runner/gate implementations; M1-001 model bridge for actual work and verifier calls; local fixtures need no live model; paths: `jiuwenswarm/research/capsules/intent.py`, `jiuwenswarm/research_assets/compiler/intent/`.

- [ ] M1-003/T011 [US1] Implement Intent deterministic source identity, code-point span, schema/reference and advisory/blocking readiness checks through the protected registry. Require accepted Intent before Requirements; do not claim deterministic entailment or expand the independent verifier payload; refs: M1-003/B02, M1-003/AC-002, M1-003/AC-003, M1-003/AC-005; also serves US2; after M1-003/T010; paths: `jiuwenswarm/research/checks/compiler.py`.

### Block verification - US1

- [ ] M1-003/T012 [US1] Execute M1-003/V02 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-003/B02, M1-003/AC-002, M1-003/V02; also serves US2; after M1-003/T003, M1-003/T011; paths: `tests/unit_tests/research/test_intent_checks.py`, `docs/code/Missions/M1/M1-003/evidence/<RUN_ID>/manifest.json`.

### Block M1-003/B03 - US1

- [ ] M1-003/T013 [US1] Implement the source-pinned Requirements carrier/declaration/body assets consuming accepted Intent and qualified resources only, preserving purpose/constraints/targets and explicit unresolved/assumption/default attribution without choosing a scientific procedure; refs: M1-003/B03, M1-003/AC-003, M1-003/AC-004, M1-003/AC-005; also serves US2; after M1-003/T004, M1-003/B02:implementation, M1-003/T005; provider/check prerequisites: M1-002 common registry/gate and accepted Intent from B02; Protected approved default-policy1.0.0 before a work call; no dynamic host profiling; paths: `jiuwenswarm/research/capsules/requirements.py`, `jiuwenswarm/research_assets/compiler/requirements/`.

- [ ] M1-003/T014 [US1] Extend compiler checks serially with exact coverage, mandatory requirement-to-acceptance/evidence linkage, valid default authority/pointers, nullable qualitative comparisons and Brief2 schema obligations, then use the same independent per-output gate; refs: M1-003/B03, M1-003/AC-003, M1-003/AC-004, M1-003/AC-005; also serves US2; after M1-003/T013; paths: `jiuwenswarm/research/checks/compiler.py`.

### Block verification - US1

- [ ] M1-003/T015 [US1] Execute M1-003/V03 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-003/B03, M1-003/AC-004, M1-003/AC-005, M1-003/V03; also serves US2; after M1-003/T004, M1-003/T014; paths: `tests/unit_tests/research/test_requirements_checks.py`, `docs/code/Missions/M1/M1-003/evidence/<RUN_ID>/manifest.json`.

### Block M1-003/B04 - US1

- [ ] M1-003/T016 [US1] Implement the bounded two-stage parent compiler: Intent then accepted-boundary Requirements, exactly the eligible work/verifier calls, frozen combined limits including verification, mechanical aggregate and durable exact Brief release. Retain reasons/observations and halt without retry/repair on failure; refs: M1-003/B04, M1-003/AC-003, M1-003/AC-005, M1-003/AC-006, M1-003/AC-008; also serves US2; after M1-003/T005, M1-003/B02:implementation, M1-003/B03:implementation; provider/check prerequisites: M1-002/B02/B04/B05/B06/B09 actual state/binder/runner/gate/control before connected compiler checks; M1-001 qualified live bridge and independently admitted checking assets before V08/V09 live cases; M1-004 static template and M1-005 planned consumer before V10; M1-006 actual submission/mode boundary before V11; advanced positive additionally depends on B05 actual module; paths: `jiuwenswarm/research/compiler.py`. C008: consume IF002 r2 shared reservations and exact worker/verifier bindings. Freeze the explicit configured compiler aggregate and reject insufficient node/run remainder before dispatch; do not widen the worker declarations, configured parent or overall run ceiling.

- [ ] M1-003/T017 [US1] Wire compiler delegates into M1-002-owned ResearchService serially: ingest is deterministic only, durable idempotent submit starts compilation once, and exact accepted Brief bytes feed static/planned consumers. Freeze mode before execution, keep fallback noninteractive and preserve linked new-work lineage without post-intake waits or mutation; refs: M1-003/B04, M1-003/AC-003, M1-003/AC-005, M1-003/AC-006, M1-003/AC-008; also serves US2; after M1-003/T016; paths: `jiuwenswarm/research/compiler.py`, `jiuwenswarm/research/control.py`.

### Block verification - US1

- [ ] M1-003/T018 [US1] Execute M1-003/V04 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-003/B02, M1-003/B03, M1-003/B04, M1-003/AC-003, M1-003/AC-005, M1-003/V04; also serves US2; after M1-003/T005, M1-003/T011, M1-003/T014, M1-003/T017; paths: `tests/unit_tests/research/test_compiler.py`, `docs/code/Missions/M1/M1-003/evidence/<RUN_ID>/manifest.json`. C008: execute the amended V04 gating_failures reservation/call-ledger cases after current shared provider implementation, retaining aggregate-budget-proof.json.

- [ ] M1-003/T019 [US1] Execute M1-003/V05 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-003/B04, M1-003/AC-006, M1-003/AC-008, M1-003/V05; also serves US2; after M1-003/T005, M1-003/T017; paths: `tests/unit_tests/research/test_compiler_handoff.py`, `docs/code/Missions/M1/M1-003/evidence/<RUN_ID>/manifest.json`.

### Block M1-003/B05 - US1

- [ ] M1-003/T020 [US1] Implement the conditional module capability/version/binding checks and explicit per-item implementation/integration/verification status reporting. Keep fixed scientific_research compilation available and reject unadopted schemas, authority transfer or clarification after accepted Brief; refs: M1-003/B05, M1-003/AC-007, M1-003/AC-008; also serves US2; after M1-003/T006, M1-003/B04:implementation, M1-003/T005; provider/check prerequisites: PENDING_SOURCE actual external advanced module and adopted alternate-lane bindings for positive conditional items; M1-005 native Leader adapter and M1-006 bounded intake interaction API before applicable live advanced checks; Baseline scientific_research remains independent and Brief2.0.0 unchanged; paths: `jiuwenswarm/research/advanced_compiler.py`.

- [ ] M1-003/T021 [US1] When its actual source and adopted versioned bindings exist, integrate applicable dynamic classification variants through the advanced module without inventing alternate-lane schemas. Retain unresolved dependency and work item if unavailable; refs: M1-003/B05, M1-003/AC-007, M1-003/AC-008; also serves US2; after M1-003/T020; paths: `jiuwenswarm/research/advanced_compiler.py`.

- [ ] M1-003/T022 [US1] When the module/bindings exist, implement permitted relevant local-repository and history context filtering with source-scoped refs, no network cloning/download or undeclared traversal; prove unrelated or unauthorized context stays excluded; refs: M1-003/B05, M1-003/AC-007, M1-003/AC-008; also serves US2; after M1-003/T021; paths: `jiuwenswarm/research/advanced_compiler.py`.

- [ ] M1-003/T023 [US1] When the module/bindings exist, integrate bounded native Leader intake clarification and Planner/Cluster task-contract handoff through their owner-provided adapters, finishing interaction before Brief acceptance. Headless uses supplied answers or halts; do not implement Planner/native/client ownership here; refs: M1-003/B05, M1-003/AC-007, M1-003/AC-008; also serves US2; after M1-003/T022; paths: `jiuwenswarm/research/advanced_compiler.py`.

### Block verification - US1

- [ ] M1-003/T024 [US1] Execute M1-003/V06 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-003/B05, M1-003/AC-007, M1-003/AC-008, M1-003/V06; also serves US2; after M1-003/T006, M1-003/T020; paths: `tests/unit_tests/research/test_advanced_compiler_adapter.py`, `docs/code/Missions/M1/M1-003/evidence/<RUN_ID>/manifest.json`. Absent/incompatible/fake-adapter BLOCK cases do not require the unavailable external advanced module; actual positive V12 retains its own dependency.

### Connected boundaries - US1

- [ ] M1-003/T025 [US1] Execute M1-003/V07 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-003/B01, M1-003/AC-001, M1-003/V07; also serves US2; after M1-003/T002, M1-003/T008; provider/check prerequisites: M1-003/B01; M1-002/B02; M1-002/B09; M1-006 actual authenticated controlled upload route; Locked bounded pdfplumber process; paths: `tests/integration/research/test_intake.py`, `docs/code/Missions/M1/M1-003/evidence/<RUN_ID>/manifest.json`.

- [ ] M1-003/T026 [US1] Execute M1-003/V08 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-003/B02, M1-003/B03, M1-003/B04, M1-003/AC-002, M1-003/AC-003, M1-003/AC-004, M1-003/AC-005, M1-003/V08; also serves US2; after M1-003/T005, M1-003/T011, M1-003/T014, M1-003/T017; provider/check prerequisites: M1-003/B02; M1-003/B03; M1-003/B04; M1-001 qualified live Codex; M1-002 actual independent assets/runner/gate/store; Frozen private challenge expectations; three fresh runs per case; paths: `tests/integration/research/test_compiler_live.py`, `docs/code/Missions/M1/M1-003/evidence/<RUN_ID>/manifest.json`.

- [ ] M1-003/T027 [US1] Execute M1-003/V09 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-003/B04, M1-003/AC-003, M1-003/AC-005, M1-003/V09; also serves US2; after M1-003/T005, M1-003/T017; provider/check prerequisites: M1-003/B04; M1-001 actual bridge; M1-002 actual runner/gate/state and protected approved eval faults; paths: `tests/integration/research/test_compiler_faults.py`, `docs/code/Missions/M1/M1-003/evidence/<RUN_ID>/manifest.json`. C008: execute real amended V09 reservation/overspend controls after current shared provider implementation; retain unchanged configuration/worker pins and actual durable failed/no-dispatch evidence.

- [ ] M1-003/T028 [US1] Execute M1-003/V10 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-003/B04, M1-003/AC-006, M1-003/V10; also serves US2; after M1-003/T005, M1-003/T017; provider/check prerequisites: M1-003/B04; M1-002/B04; M1-004 static template/carriers; M1-005 compatible planned consumer; paths: `tests/integration/research/test_compiler_binding.py`, `docs/code/Missions/M1/M1-003/evidence/<RUN_ID>/manifest.json`.

- [ ] M1-003/T029 [US1] Execute M1-003/V11 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-003/B04, M1-003/B05, M1-003/AC-008, M1-003/V11; also serves US2; after M1-003/T005, M1-003/T017, M1-003/T020; provider/check prerequisites: M1-003/B04; M1-006 actual mode/submission interface; M1-003/B05 real module only for advanced interactive positive; paths: `tests/integration/research/test_intake_modes.py`, `docs/code/Missions/M1/M1-003/evidence/<RUN_ID>/manifest.json`. Execute baseline/fixed/headless/disconnect assertions when their providers are ready. The advanced interactive positive additionally needs M1-003/T023 and its actual module/binding; retain that assertion and this required V as incomplete/BLOCKED when unavailable, never PASS from the partial subset.

- [ ] M1-003/T030 [US1] Execute M1-003/V12 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-003/B05, M1-003/AC-007, M1-003/V12; also serves US2; after M1-003/T006, M1-003/T023; provider/check prerequisites: M1-003/B05; PENDING_SOURCE actual advanced implementation and adopted versioned bindings; M1-005 actual native Leader; M1-006 supported bounded interaction; paths: `tests/integration/research/test_advanced_compiler.py`, `docs/code/Missions/M1/M1-003/evidence/<RUN_ID>/manifest.json`.

## Acceptance and Evidence Matrix

| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [M1-003/AC-001](spec.md) | M1-003/B01; M1-IF-004@r1; M1-IF-007@r1 | M1-003/T007; M1-003/T008 | M1-003/V01 / M1-003/T009; M1-003/V07 / M1-003/T025 | NOT_RUN | None / NOT_BUILT | Initial; no reusable runtime evidence |
| [M1-003/AC-002](spec.md) | M1-003/B02; M1-IF-001@r1; M1-IF-002@r2; M1-IF-003@r1; M1-IF-004@r1 | M1-003/T010; M1-003/T011 | M1-003/V02 / M1-003/T012; M1-003/V08 / M1-003/T026 | NOT_RUN | None / NOT_BUILT | Initial; no reusable runtime evidence |
| [M1-003/AC-003](spec.md) | M1-003/B02; M1-003/B03; M1-003/B04; M1-IF-001@r1; M1-IF-002@r2; M1-IF-003@r1; M1-IF-004@r1 | M1-003/T010; M1-003/T011; M1-003/T013; M1-003/T014; M1-003/T016; M1-003/T017 | M1-003/V04 / M1-003/T018; M1-003/V08 / M1-003/T026; M1-003/V09 / M1-003/T027 | NOT_RUN | None / NOT_BUILT | Initial; no reusable runtime evidence |
| [M1-003/AC-004](spec.md) | M1-003/B03; M1-IF-001@r1; M1-IF-002@r2; M1-IF-003@r1; M1-IF-004@r1 | M1-003/T013; M1-003/T014 | M1-003/V03 / M1-003/T015; M1-003/V08 / M1-003/T026 | NOT_RUN | None / NOT_BUILT | Initial; no reusable runtime evidence |
| [M1-003/AC-005](spec.md) | M1-003/B02; M1-003/B03; M1-003/B04; M1-IF-001@r1; M1-IF-002@r2; M1-IF-003@r1; M1-IF-004@r1 | M1-003/T010; M1-003/T011; M1-003/T013; M1-003/T014; M1-003/T016; M1-003/T017 | M1-003/V03 / M1-003/T015; M1-003/V04 / M1-003/T018; M1-003/V08 / M1-003/T026; M1-003/V09 / M1-003/T027 | NOT_RUN | None / NOT_BUILT | Initial; no reusable runtime evidence |
| [M1-003/AC-006](spec.md) | M1-003/B04; M1-IF-002@r2; M1-IF-003@r1; M1-IF-004@r1; M1-IF-006@r1; M1-IF-007@r1 | M1-003/T016; M1-003/T017 | M1-003/V05 / M1-003/T019; M1-003/V10 / M1-003/T028 | NOT_RUN | None / NOT_BUILT | Initial; no reusable runtime evidence |
| [M1-003/AC-007](spec.md) | M1-003/B05; M1-IF-003@r1; M1-IF-004@r1; M1-IF-006@r1; M1-IF-007@r1 | M1-003/T020; M1-003/T021; M1-003/T022; M1-003/T023 | M1-003/V06 / M1-003/T024; M1-003/V12 / M1-003/T030 | NOT_RUN | None / NOT_BUILT | Initial; no reusable runtime evidence |
| [M1-003/AC-008](spec.md) | M1-003/B04; M1-003/B05; M1-IF-003@r1; M1-IF-004@r1; M1-IF-006@r1; M1-IF-007@r1 | M1-003/T016; M1-003/T017; M1-003/T020; M1-003/T021; M1-003/T022; M1-003/T023 | M1-003/V05 / M1-003/T019; M1-003/V06 / M1-003/T024; M1-003/V11 / M1-003/T029 | NOT_RUN | None / NOT_BUILT | Initial; no reusable runtime evidence |

### Individual required check results

| V ID / plan link | Execution work ID | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- |
| [M1-003/V01](plan.md) | M1-003/T009 | NOT_RUN | None / NOT_BUILT | Initial; no execution |
| [M1-003/V02](plan.md) | M1-003/T012 | NOT_RUN | None / NOT_BUILT | Initial; no execution |
| [M1-003/V03](plan.md) | M1-003/T015 | NOT_RUN | None / NOT_BUILT | Initial; no execution |
| [M1-003/V04](plan.md) | M1-003/T018 | NOT_RUN | None / NOT_BUILT | Initial; no execution |
| [M1-003/V05](plan.md) | M1-003/T019 | NOT_RUN | None / NOT_BUILT | Initial; no execution |
| [M1-003/V06](plan.md) | M1-003/T024 | NOT_RUN | None / NOT_BUILT | Initial; no execution |
| [M1-003/V07](plan.md) | M1-003/T025 | NOT_RUN | None / NOT_BUILT | Initial; no execution |
| [M1-003/V08](plan.md) | M1-003/T026 | NOT_RUN | None / NOT_BUILT | Initial; no execution |
| [M1-003/V09](plan.md) | M1-003/T027 | NOT_RUN | None / NOT_BUILT | Initial; no execution |
| [M1-003/V10](plan.md) | M1-003/T028 | NOT_RUN | None / NOT_BUILT | Initial; no execution |
| [M1-003/V11](plan.md) | M1-003/T029 | NOT_RUN | None / NOT_BUILT | Initial; no execution |
| [M1-003/V12](plan.md) | M1-003/T030 | NOT_RUN | None / NOT_BUILT | Initial; no execution |

## Dependency Order and Execution Notes

An earlier blocked operation is not a global stop: continue work whose explicit prerequisites are satisfied. In particular, evidence/report derivation may describe incomplete/blocked upstream results truthfully; it cannot improve those results.

### User stories and independent criteria

User Story 1 - Obtain the supported outcome (Priority: P1): **Independent Test**: Use frozen source-valid inputs through the actual supported provider/consumer boundary and independently reconcile effects, exact identities, accepted artifacts and persisted evidence. Source/schema fixtures alone cannot establish real external connections.

User Story 2 - Understand a failed or blocked attempt (Priority: P1): **Independent Test**: Supply a frozen invalid/boundary counterpart and inspect actual effects, terminal outcome and retained evidence against an independent expectation.

References ending :implementation require that provider's implementation, not its live acceptance. Runtime resources are check-specific. Intra-feature work keys require construction/implementation before mapped verification. Final renderer must assign native T IDs and retain these edges.

B01 -> B02 -> B03 -> B04; B05 adapter preparation follows baseline B04, with actual advanced positives gated only by their named external sources and native/client providers.; B02 and B03 share checks/compiler.py and compiler asset registration; edit serially. B04 coordinates control.py with its M1-002 owner after B09, without duplicating ResearchService or an intake endpoint.; M1-003 owns the sole upload-time extractor; M1-006 calls it once. Later qualification verifies exact stored text bytes/hash, preserving source refs and spans.; Block tests can use explicitly tagged model doubles; V08/V09 actual work/verifier boundaries and V12 actual advanced integration cannot pass from them.; All current statuses remain NOT_STARTED/NOT_RUN/NOT_READY; missing advanced sources remain explicit, including classification variants, local/history filtering, native clarification and Planner/Cluster handoff.

V07: M1-003/B01; M1-002/B02; M1-002/B09; M1-006 actual authenticated controlled upload route; Locked bounded pdfplumber process; V08: M1-003/B02; M1-003/B03; M1-003/B04; M1-001 qualified live Codex; M1-002 actual independent assets/runner/gate/store; Frozen private challenge expectations; three fresh runs per case; V09: M1-003/B04; M1-001 actual bridge; M1-002 actual runner/gate/state and protected approved eval faults; V10: M1-003/B04; M1-002/B04; M1-004 static template/carriers; M1-005 compatible planned consumer; V11: M1-003/B04; M1-006 actual mode/submission interface; M1-003/B05 real module only for advanced interactive positive; V12: M1-003/B05; PENDING_SOURCE actual advanced implementation and adopted versioned bindings; M1-005 actual native Leader; M1-006 supported bounded interaction

Each work item names its implementation/test paths and satisfied-before-execution dependencies. Definition-time source/IF preparation is distinct from live provider readiness. Missing authentication, dedicated Builder credential, catalogs, isolation, protected custody or native hardware constrains affected execution only; do not turn it into a global preparation gate. Source thresholds, exact schemas, repeats and commands remain in spec/plan/owning IFs.

Parallel examples: once generated contract definitions and required providers are ready, independent fixture/test construction for the supported-outcome and failure stories may proceed in disjoint files; after shared core seams are implemented, separate router, RSI, research CC and shell modules may be developed independently. Shared files in the plan have one editor at a time. A static Phase1 path is the first integrated increment; all other requested work stays required.

## Current Verification Conclusion

- Candidate identity: NOT_BUILT; exact relevant uncommitted execution inputs must be captured before runs.
- Required work complete: 0 / 30.
- Required coverage: 8 ACs / 5 blocks / 12 V procedures mapped; all runtime results NOT_RUN.
- Conclusion: NOT_READY.
- Next action: first listed work item after program-wide read-only Analyze and separate corrections; Implementation is in progress; complete the remaining required work and execute current amended checks without accepting partial observations as full V PASS.
- Resource limitations are the check-specific prerequisites in plan.md; unavailable resources are never accepted as passing skips.

VERIFIED requires all required work complete and all required checks PASS on the exact candidate with no invalidating dependency. Contribution to M1-SYSTEM does not itself establish whole-program acceptance.

## Evidence Invalidation

Initial generation has no reusable runtime evidence. Changed source/IF/code/config/test/fixture/profile/dependency/image inputs invalidate affected V/AC rows and connected consumers through TASKS. Mark STALE, preserve previous raw attempts, rerun before acceptance and state any equivalent-evidence reuse basis. Evidence-only annotations do not create a runtime pass or require a commit.

C008 evidence validity: current spec/plan revisions and M1-IF-002@r2 are required by every affected matrix row. Existing T/AC/V identities and progress are preserved. Amended V03/V04/V12/V14 (002), V04/V09 (003) and V02/V08 (005), as applicable to this feature, require current new library/static-template/bootstrap candidate pins and actual reservation/accounting assertions. Earlier affected partial runs are STALE for C008, retained unchanged; required unexecuted checks remain NOT_RUN. No source bytes or whole-run ceilings are changed.

## Implementation progress - 2026-10-16

C008 native amendment and clean read-only Analyze rerun preceded dependent implementation. Shared library/runner budget enforcement and explicit containment wiring are implemented; actual development results and retained failures are recorded in [the shared development evidence](../M1-002/evidence/20261016-budget-containment-dev01/run.md). These partial controlled checks do not complete a full required V procedure or establish live model/confinement/system acceptance. Current required V/AC rows remain NOT_RUN; affected older candidate observations are invalidated by current IF002 r2 and new source/schema/code inputs. Continue outstanding authored static-template release pins, explicit native init, independent v2 RSI admission and all required actual boundary/system procedures. No checkbox is changed solely from code presence or partial checks.

Implementation checkpoint: current focused development runs, failures, source-readiness correction and stable main-code boundary are appended to [the shared core development evidence](../M1-002/evidence/20261016-budget-containment-dev01/run.md). No whole V/AC status was changed; required connected/live/system procedures and resource qualification remain outstanding.
