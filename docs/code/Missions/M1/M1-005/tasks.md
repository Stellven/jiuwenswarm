---

description: "TASK-native work and acceptance/evidence correspondence"

---

# Tasks: M1-005 - Bounded native Leader planning with shared protected execution

**TASK**: [TASK.md](TASK.md) | **Spec / Plan revisions**: r3 / r4 | **Tasks revision/date**: r3 / 2026-10-19

**Feature directory**: docs/code/Missions/M1/M1-005/

Verification, testing, integration and applicable benchmarks are explicitly required by the invoked prompt/spec/plan. This is the sole implementation work list and AC-to-evidence authority. Qualified sequential T IDs apply Code SOP v2. Checkmarks mean performed work; AC acceptance requires current PASS for every required check. No additional reviewer/approval/commit gate exists.

## Work Items

The native template is organized by dependency-ordered blocks with user-story labels. Shared blocks serve the listed stories; story completion dependencies and independent criteria appear below. Construct tests before implementing their target behavior, verify blocks as soon as dependencies permit, then connect actual boundaries. Initial [P] markers are withheld until disjoint ownership and prerequisites are satisfied.

### Foundation / shared definitions

- [ ] M1-005/T001 Resolve final plan-proposal3.0.0, run-plan policy/host checks and the exact pinned native Leader adapter source. Prepare independent proposal counterexamples and live qualification manifest; retain Phase 3 implementation/integration/verification status separately; paths: `tests/fixtures/research/planner/`, `docs/code/Missions/M1/M1-005/evidence/<RUN_ID>/manifest.json`.

### Block M1-005/B01 - US1

- [ ] M1-005/T002 [US1] Construct preselected-mode/input-contract tests and actual static/planned binder boundary tests before input assembly. Freeze omitted/static/planned modes, accepted versus candidate Brief, exact input refs, two Brief IDs and later catalog changes; static must make zero Planner calls; refs: M1-005/B01, M1-005/AC-001, M1-005/AC-002, M1-005/V01, M1-005/V02, M1-005/V07; also serves US2; after M1-005/T001; paths: `tests/unit_tests/research/test_planning.py`, `tests/unit_tests/research/test_planner_contract.py`, `tests/integration/research/test_plan_binding.py`, `tests/fixtures/research/planner/inputs/`. C008: construct test_planner_contract.py cases using IF002 r2 aggregate snapshot ceilings, exact copied node limits and unchanged worker/overall limits; do not reinterpret aggregate fields or use old work-only pins.

### Block M1-005/B02 - US1

- [ ] M1-005/T003 [US1] Construct native adapter configuration/call-count tests and actual live Planner tests before extending native.py. Freeze one-shot settings, attempted native injected tool/MCP/subagent/second call, timeout/cancel, malformed response and single-line INFEASIBLE length boundaries. Assert actual 120s/one-call/zero-tools behavior without mocks as native completion evidence; refs: M1-005/B02, M1-005/AC-002, M1-005/AC-006, M1-005/V06, M1-005/V09; also serves US2; after M1-005/T001; paths: `tests/unit_tests/research/test_native_planner.py`, `tests/integration/research/test_planner_live.py`, `tests/fixtures/research/planner/native/`.

### Block M1-005/B03 - US1

- [ ] M1-005/T004 [US1] Construct all twelve host-check and restricted semantic-review tests, actual adversarial binder/gate boundaries and complete planned research/static controls before validation/handoff. Freeze graph/ports/pins/coverage/resource/effect/stage negatives, unknown suggested-check warning, exact policy boundaries and zero-downstream assertions; refs: M1-005/B03, M1-005/AC-002, M1-005/AC-003, M1-005/AC-004, M1-005/AC-006, M1-005/V03, M1-005/V04, M1-005/V08, M1-005/V11; also serves US2; after M1-005/T001; paths: `tests/unit_tests/research/test_plan_validation.py`, `tests/unit_tests/research/test_plan_review.py`, `tests/integration/research/test_plan_adversarial.py`, `tests/integration/research/test_planned_research.py`, `tests/fixtures/research/planner/graphs/`, `tests/fixtures/research/planner/review/`. C008: construct actual adversarial_plan budget controls for widened aggregate limits, insufficient review reservations and stale library/template refs before consumer implementation; use protected binder/runner authority.

### Block M1-005/B04 - US2

- [ ] M1-005/T005 [US2] Construct protected outcome/lineage tests and actual compiler-to-Planner new-run boundary before control integration. Freeze first/second infeasibility, duplicate linkage request, all reasons carried/addressed, static/model/runtime/budget fault controls and no third attempt; distinguish new linked work from replay; refs: M1-005/B04, M1-005/AC-005, M1-005/AC-006, M1-005/V05, M1-005/V10; also serves US1; after M1-005/T001; paths: `tests/unit_tests/research/test_plan_outcome.py`, `tests/integration/research/test_plan_retry_boundary.py`, `tests/fixtures/research/planner/outcomes/`.

### Block M1-005/B01 - US1

- [ ] M1-005/T006 [US1] Implement frozen preselected-mode dispatch and protected assembly of accepted Brief/library/resource/policy inputs, refusing mismatched/candidate refs. Static bypasses Planner and uses the existing protected binder; planned failure cannot switch the same run to static; refs: M1-005/B01, M1-005/AC-001, M1-005/AC-002; also serves US2; after M1-005/T002, M1-005/T004; provider/check prerequisites: M1-IF-002@r2/M1-IF-003@r1/M1-IF-004@r1/M1-IF-005@r1/M1-IF-006@r1 definitions for construction; M1-002 actual binder, M1-003 accepted Brief and M1-004 admitted carriers before V07; paths: `jiuwenswarm/research/planning.py`. C008: assemble the current pinned IF002 r2 snapshot and exact authored static-template refs. Preserve the Planner worker 120-second/one-call/zero-tool declaration; its independent review is reserved inside the explicit configured pre-plan aggregate.

### Block verification - US1

- [ ] M1-005/T007 [US1] Execute M1-005/V01 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-005/B01, M1-005/AC-001, M1-005/V01; also serves US2; after M1-005/T002, M1-005/T006; paths: `tests/unit_tests/research/test_planning.py`, `docs/code/Missions/M1/M1-005/evidence/<RUN_ID>/manifest.json`.

### Block M1-005/B02 - US1

- [ ] M1-005/T008 [US1] Extend the owner-provided native.py serially with NativePlanner and AuditedBridgeModelClient through public BaseModelClient registration. Use actual TeamAgentSpec.build().harness.run_once in LEADER role, zero SDK retries and strict message/modalities validation, delegating all auth/dispatch to the existing protected bridge; refs: M1-005/B02, M1-005/AC-002, M1-005/AC-006; also serves US2; after M1-005/T003, M1-005/B01:implementation, M1-002/B07:implementation, M1-005/T002, M1-005/T004; provider/check prerequisites: M1-002-owned native.py base implemented before coordinated extension; Installed exact OpenJiuwen pin and M1-001 audited bridge before actual native/live V09; Actual accepted Brief/catalog/resources, source-pinned Planner/check assets and live fixed Codex; paths: `jiuwenswarm/research/native.py`.

- [ ] M1-005/T009 [US1] Implement the data-only Planner carrier and immutable source-bound declaration/body assets. Disable task loop/planning/system operations/tools/MCP/subagents/repair/review/evolution/coordinator paths; enforce the protected one-call/zero-tool/120-second budget and dispose fresh native contexts on all outcomes; refs: M1-005/B02, M1-005/AC-002, M1-005/AC-006; also serves US2; after M1-005/T008; paths: `jiuwenswarm/research/capsules/planner.py`, `jiuwenswarm/research_assets/planner/`, `jiuwenswarm/research/native.py`.

### Block verification - US1

- [ ] M1-005/T010 [US1] Execute M1-005/V02 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-005/B01, M1-005/B02, M1-005/AC-002, M1-005/AC-005, M1-005/V02; also serves US2; after M1-005/T002, M1-005/T006, M1-005/T009; paths: `tests/unit_tests/research/test_planner_contract.py`, `docs/code/Missions/M1/M1-005/evidence/<RUN_ID>/manifest.json`. C008: execute amended V02 aggregate-boundary and copied-field checks after current shared library/binder and Planner assembly are implemented; retain aggregate-budget-proof.json.

- [ ] M1-005/T011 [US1] Execute M1-005/V06 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-005/B02, M1-005/AC-002, M1-005/AC-006, M1-005/V06; also serves US2; after M1-005/T003, M1-005/T009; paths: `tests/unit_tests/research/test_native_planner.py`, `docs/code/Missions/M1/M1-005/evidence/<RUN_ID>/manifest.json`.

### Block M1-005/B03 - US1

- [ ] M1-005/T012 [US1] Register the complete source Planner deterministic check population through the existing protected check/binder mechanisms: exact refs/CC/check pins, concrete Brief coverage, DAG/ports, one work CC per node, required stage placement, resource/effect authority and policy ceilings. Unknown suggested checks warn/drop without granting authority; refs: M1-005/B03, M1-005/AC-002, M1-005/AC-003, M1-005/AC-004, M1-005/AC-006; also serves US2; after M1-005/T004, M1-005/B01:implementation, M1-005/B02:implementation, M1-002/B04:implementation, M1-002/B06:implementation, M1-005/T002, M1-005/T003; provider/check prerequisites: M1-002 actual shared binder/check registry/gate before connected checks; M1-004 exact research ports/admitted carriers/resources before graph integration and full V11; M1-001 actual executor/D45 Builder credential and M1-003 accepted Brief before V11; paths: `jiuwenswarm/research/planning.py`, `jiuwenswarm/research/binding.py`, `jiuwenswarm/research/checks/policy.py`. C008: where this work item implements proposal validation/handoff, consume the shared aggregate library, node/run reservation and unchanged whole-plan validation without another ceiling authority; preserve PlanNode-to-NodeContract copy.

- [ ] M1-005/T013 [US1] Use the shared declaration/proposal-only semantic assessment and per-output/node gate, then protected binder acceptance/freeze and existing scheduler. Enforce at most 12 research nodes and exact planned/static time/call/memory/max-attempt policy; do not add another schema/gate/binder or let proposal notes waive checks; refs: M1-005/B03, M1-005/AC-002, M1-005/AC-003, M1-005/AC-004, M1-005/AC-006; also serves US2; after M1-005/T012; paths: `jiuwenswarm/research/planning.py`, `jiuwenswarm/research/binding.py`.

### Block verification - US1

- [ ] M1-005/T014 [US1] Execute M1-005/V03 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-005/B03, M1-005/AC-003, M1-005/AC-004, M1-005/V03; also serves US2; after M1-005/T004, M1-005/T013; paths: `tests/unit_tests/research/test_plan_validation.py`, `docs/code/Missions/M1/M1-005/evidence/<RUN_ID>/manifest.json`.

- [ ] M1-005/T015 [US1] Execute M1-005/V04 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-005/B03, M1-005/AC-003, M1-005/AC-004, M1-005/V04; also serves US2; after M1-005/T004, M1-005/T013; paths: `tests/unit_tests/research/test_plan_review.py`, `docs/code/Missions/M1/M1-005/evidence/<RUN_ID>/manifest.json`.

### Block M1-005/B04 - US2

- [ ] M1-005/T016 [US2] Implement immutable source plan outcomes and protected transactional depth/idempotency linkage: only eligible first planned infeasibility creates one new Compiler run carrying Brief/all reasons/prior outcome; second halts, and static/model/runtime/budget faults never auto-link or switch mode; refs: M1-005/B04, M1-005/AC-005, M1-005/AC-006; also serves US1; after M1-005/T005, M1-005/B03:implementation, M1-002/B09:implementation, M1-003/B04:implementation, M1-005/T004; provider/check prerequisites: M1-002 protected state/control and M1-003 actual compiler intake lineage before V10; Qualified M1-001 live model bridge for actual first/second outcomes; no external router required; paths: `jiuwenswarm/research/planning.py`, `jiuwenswarm/research/control.py`.

- [ ] M1-005/T017 [US2] Expose separate factual Planner implementation/integration/verification and dependency status through existing protected inspection data for M1-006/System; retain original failure and new-run identities without human wait, repair, third attempt or acceptance inferred from a status label; refs: M1-005/B04, M1-005/AC-005, M1-005/AC-006; also serves US1; after M1-005/T016; paths: `jiuwenswarm/research/planning.py`.

### Block verification - US2

- [ ] M1-005/T018 [US2] Execute M1-005/V05 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-005/B04, M1-005/AC-005, M1-005/V05; also serves US1; after M1-005/T005, M1-005/T017; paths: `tests/unit_tests/research/test_plan_outcome.py`, `docs/code/Missions/M1/M1-005/evidence/<RUN_ID>/manifest.json`.

### Connected boundaries - US1

- [ ] M1-005/T019 [US1] Execute M1-005/V07 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-005/B01, M1-005/B03, M1-005/AC-001, M1-005/AC-004, M1-005/V07; also serves US2; after M1-005/T002, M1-005/T006, M1-005/T013; provider/check prerequisites: M1-005/B01; M1-005/B03; M1-002/B04; M1-003 accepted Brief; M1-004 admitted research carriers; paths: `tests/integration/research/test_plan_binding.py`, `docs/code/Missions/M1/M1-005/evidence/<RUN_ID>/manifest.json`.

- [ ] M1-005/T020 [US1] Execute M1-005/V08 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-005/B03, M1-005/AC-002, M1-005/AC-003, M1-005/AC-004, M1-005/V08; also serves US2; after M1-005/T004, M1-005/T013; provider/check prerequisites: M1-005/B03; M1-002 actual runner/check/gate/binder; Independent source-bound asset profiles; paths: `tests/integration/research/test_plan_adversarial.py`, `docs/code/Missions/M1/M1-005/evidence/<RUN_ID>/manifest.json`. C008: execute real adversarial aggregate ceiling/reservation/stale-pin controls before effects; retain exact new library/template refs and unchanged source selection.

- [ ] M1-005/T021 [US1] Execute M1-005/V09 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-005/B02, M1-005/B03, M1-005/AC-002, M1-005/AC-003, M1-005/AC-006, M1-005/V09; also serves US2; after M1-005/T003, M1-005/T009, M1-005/T013; provider/check prerequisites: M1-005/B02; M1-005/B03; Installed exact OpenJiuwen + qualified live M1-001 bridge; M1-002 admitted profiles/catalog and M1-003 accepted Brief; paths: `tests/integration/research/test_planner_live.py`, `docs/code/Missions/M1/M1-005/evidence/<RUN_ID>/manifest.json`.

### Connected boundaries - US2

- [ ] M1-005/T022 [US2] Execute M1-005/V10 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-005/B04, M1-005/AC-005, M1-005/V10; also serves US1; after M1-005/T005, M1-005/T017; provider/check prerequisites: M1-005/B04; M1-003/B04; M1-002/B02; M1-002/B09; M1-001 actual model bridge; paths: `tests/integration/research/test_plan_retry_boundary.py`, `docs/code/Missions/M1/M1-005/evidence/<RUN_ID>/manifest.json`.

### Connected boundaries - US1

- [ ] M1-005/T023 [US1] Execute M1-005/V11 exactly as the final plan procedure after its actual providers are ready; retain expanded command, exact candidate, fixtures, counts, raw outcomes and limitations. Required skips or missing prerequisites are not passes; refs: M1-005/B01, M1-005/B02, M1-005/B03, M1-005/B04, M1-005/AC-004, M1-005/AC-006, M1-005/V11; also serves US2; after M1-005/T004, M1-005/T006, M1-005/T009, M1-005/T013, M1-005/T017; provider/check prerequisites: M1-005 all blocks; M1-001 actual restricted executor and dedicated D45 credential; M1-002 actual governance/native runtime; M1-003 real accepted Brief; M1-004 all seven real research CCs and fixed scientific resources; M1-SYSTEM same-candidate journey inputs; paths: `tests/integration/research/test_planned_research.py`, `docs/code/Missions/M1/M1-005/evidence/<RUN_ID>/manifest.json`.

## Acceptance and Evidence Matrix

| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [M1-005/AC-001](spec.md) | M1-005/B01; M1-IF-002@r2; M1-IF-003@r1; M1-IF-004@r1; M1-IF-005@r1; M1-IF-006@r1 | M1-005/T006 | M1-005/V01 / M1-005/T007; M1-005/V07 / M1-005/T019 | NOT_RUN | None / NOT_BUILT | Initial; no reusable runtime evidence |
| [M1-005/AC-002](spec.md) | M1-005/B01; M1-005/B02; M1-005/B03; M1-IF-001@r1; M1-IF-002@r2; M1-IF-003@r1; M1-IF-004@r1; M1-IF-006@r1 | M1-005/T006; M1-005/T008; M1-005/T009; M1-005/T012; M1-005/T013 | M1-005/V02 / M1-005/T010; M1-005/V06 / M1-005/T011; M1-005/V08 / M1-005/T020; M1-005/V09 / M1-005/T021 | NOT_RUN | None / NOT_BUILT | Initial; no reusable runtime evidence |
| [M1-005/AC-003](spec.md) | M1-005/B03; M1-IF-001@r1; M1-IF-002@r2; M1-IF-003@r1; M1-IF-004@r1; M1-IF-005@r1; M1-IF-006@r1 | M1-005/T012; M1-005/T013 | M1-005/V03 / M1-005/T014; M1-005/V04 / M1-005/T015; M1-005/V08 / M1-005/T020; M1-005/V09 / M1-005/T021 | NOT_RUN | None / NOT_BUILT | Initial; no reusable runtime evidence |
| [M1-005/AC-004](spec.md) | M1-005/B03; M1-IF-001@r1; M1-IF-002@r2; M1-IF-003@r1; M1-IF-004@r1; M1-IF-005@r1; M1-IF-006@r1 | M1-005/T012; M1-005/T013 | M1-005/V03 / M1-005/T014; M1-005/V04 / M1-005/T015; M1-005/V07 / M1-005/T019; M1-005/V08 / M1-005/T020; M1-005/V11 / M1-005/T023 | NOT_RUN | None / NOT_BUILT | Initial; no reusable runtime evidence |
| [M1-005/AC-005](spec.md) | M1-005/B04; M1-IF-001@r1; M1-IF-002@r2; M1-IF-003@r1; M1-IF-004@r1; M1-IF-006@r1 | M1-005/T016; M1-005/T017 | M1-005/V02 / M1-005/T010; M1-005/V05 / M1-005/T018; M1-005/V10 / M1-005/T022 | NOT_RUN | None / NOT_BUILT | Initial; no reusable runtime evidence |
| [M1-005/AC-006](spec.md) | M1-005/B02; M1-005/B03; M1-005/B04; M1-IF-001@r1; M1-IF-002@r2; M1-IF-003@r1; M1-IF-004@r1; M1-IF-005@r1; M1-IF-006@r1 | M1-005/T008; M1-005/T009; M1-005/T012; M1-005/T013; M1-005/T016; M1-005/T017 | M1-005/V06 / M1-005/T011; M1-005/V09 / M1-005/T021; M1-005/V11 / M1-005/T023 | NOT_RUN | None / NOT_BUILT | Initial; no reusable runtime evidence |

### Individual required check results

| V ID / plan link | Execution work ID | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- |
| [M1-005/V01](plan.md) | M1-005/T007 | NOT_RUN | None / NOT_BUILT | Initial; no execution |
| [M1-005/V02](plan.md) | M1-005/T010 | NOT_RUN | None / NOT_BUILT | Initial; no execution |
| [M1-005/V03](plan.md) | M1-005/T014 | NOT_RUN | None / NOT_BUILT | Initial; no execution |
| [M1-005/V04](plan.md) | M1-005/T015 | NOT_RUN | None / NOT_BUILT | Initial; no execution |
| [M1-005/V05](plan.md) | M1-005/T018 | NOT_RUN | None / NOT_BUILT | Initial; no execution |
| [M1-005/V06](plan.md) | M1-005/T011 | NOT_RUN | None / NOT_BUILT | Initial; no execution |
| [M1-005/V07](plan.md) | M1-005/T019 | NOT_RUN | None / NOT_BUILT | Initial; no execution |
| [M1-005/V08](plan.md) | M1-005/T020 | NOT_RUN | None / NOT_BUILT | Initial; no execution |
| [M1-005/V09](plan.md) | M1-005/T021 | NOT_RUN | None / NOT_BUILT | Initial; no execution |
| [M1-005/V10](plan.md) | M1-005/T022 | NOT_RUN | None / NOT_BUILT | Initial; no execution |
| [M1-005/V11](plan.md) | M1-005/T023 | NOT_RUN | None / NOT_BUILT | Initial; no execution |

## Dependency Order and Execution Notes

An earlier blocked operation is not a global stop: continue work whose explicit prerequisites are satisfied. In particular, evidence/report derivation may describe incomplete/blocked upstream results truthfully; it cannot improve those results.

### User stories and independent criteria

User Story 1 - Obtain the supported outcome (Priority: P1): **Independent Test**: Use frozen source-valid inputs through the actual supported provider/consumer boundary and independently reconcile effects, exact identities, accepted artifacts and persisted evidence. Source/schema fixtures alone cannot establish real external connections.

User Story 2 - Understand a failed or blocked attempt (Priority: P1): **Independent Test**: Supply a frozen invalid/boundary counterpart and inspect actual effects, terminal outcome and retained evidence against an independent expectation.

References ending :implementation require that provider's implementation, not its live acceptance. Runtime resources are check-specific. Intra-feature work keys require construction/implementation before mapped verification. Final renderer must assign native T IDs and retain these edges.

B01 -> B02 -> B03 -> B04. B02 extends M1-002/native.py only after its B07 implementation; B03 extends shared binder/check files only after their owners' implementation; B04 extends control.py after M1-002/B09 and M1-003/B04.; Shared native.py, planning.py, binding.py, policy.py and control.py edits are serial. Pure proposal fixture design can be prepared independently once exact contracts are adopted, but no initial [P] flag bypasses prerequisite readiness.; Native compatibility and live one-call/zero-tool proof require the actual installed pin and audited existing transport; mocked model-client construction is not live native acceptance.; Full V11 waits for M1-004 scientific resources/all CCs and the M1-001 D45 credential; no provider or resource substitution. Earlier proposal/check/binder work proceeds independently.; M1-SYSTEM consumes current V09-V11 evidence and derives separate implementation/integration/verification reporting. No child schema/status claim implies full product completion.

V07: M1-005/B01; M1-005/B03; M1-002/B04; M1-003 accepted Brief; M1-004 admitted research carriers; V08: M1-005/B03; M1-002 actual runner/check/gate/binder; Independent source-bound asset profiles; V09: M1-005/B02; M1-005/B03; Installed exact OpenJiuwen + qualified live M1-001 bridge; M1-002 admitted profiles/catalog and M1-003 accepted Brief; V10: M1-005/B04; M1-003/B04; M1-002/B02; M1-002/B09; M1-001 actual model bridge; V11: M1-005 all blocks; M1-001 actual restricted executor and dedicated D45 credential; M1-002 actual governance/native runtime; M1-003 real accepted Brief; M1-004 all seven real research CCs and fixed scientific resources; M1-SYSTEM same-candidate journey inputs

Each work item names its implementation/test paths and satisfied-before-execution dependencies. Definition-time source/IF preparation is distinct from live provider readiness. Missing authentication, dedicated Builder credential, catalogs, isolation, protected custody or native hardware constrains affected execution only; do not turn it into a global preparation gate. Source thresholds, exact schemas, repeats and commands remain in spec/plan/owning IFs.

Parallel examples: once generated contract definitions and required providers are ready, independent fixture/test construction for the supported-outcome and failure stories may proceed in disjoint files; after shared core seams are implemented, separate router, RSI, research CC and shell modules may be developed independently. Shared files in the plan have one editor at a time. A static Phase1 path is the first integrated increment; all other requested work stays required.

## Current Verification Conclusion

- Candidate identity: NOT_BUILT; exact relevant uncommitted execution inputs must be captured before runs.
- Required work complete: 0 / 23.
- Required coverage: 6 ACs / 4 blocks / 11 V procedures mapped; all runtime results NOT_RUN.
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


### M1-I032 direct planned-execution consumer reconciliation

IF001r2 and IF003r3 retain the original public plan/proposal/node/subnode/model fields and ordinary r1 semantics consumed by this Planner. IF016 has no direct producer/consumer reference in the current Planner native records, and this path cannot claim private evaluation authority. Pre-plan Planner remains its exact 120-second/one-call/zero-tool worker plus independent reserved review, without a planned RunPlan lease inspector or new scientific resource grant. The accepted Brief/library/resource/policy identities, frozen snapshot timing and graph/source/budget/coverage checks remain unchanged. A model proposal or PlanNode resource label never acquires a native lease or authority. For full planned scientific execution in existing V11, the actual002 Scheduler/Runner and004 scientific host adapters MUST consume owning001 IF001r2 before first whole-parent worker/start, use the shared physical-resource ledger across static/planned/ordinary/private aliases, and retain ownership through whole-attempt terminal plus actual cessation. Planned mode cannot bypass this via an alternate runner, call-time lock, new execution ID or static fallback. Missing actual native/resource/Builder/kernel services blocks the required journey and cannot pass from a valid graph or model-only Planner component.

The single field/behavior authorities remain owning001 IF001r2 and owning002 IF003r3/IF016r2, not a duplicated Planner agreement. Existing AC003/004/006 and T012/T013/T019/T023, V07/V08/V11 preserve their source obligations; construct independent no-bypass/zero-start negatives before dependent integration, and require current actual resources for V11. New protocol checks remain NOT_RUN/UNBUILT and earlier component evidence stays scoped. Spec r3 and owned IF006r1 are unchanged; no new product/source field, threshold, AC, T or V ID is introduced.

2026-10-20 linked ordinary input capture adoption: Existing M1-005/B04/T016 (AC005), M1-004/B01/B02 T013/T014 and M1-006 execution coordination: source-only correction captures the one genuinely newly allocated linked ordinary replan against the exact original authenticated Principal and frozen pre-capture protected context retained by its fresh submit caller. Reconstruct/compare the actual parent context from its durable binding; use the separately prepared base inventory and original base read ceiling without guessing/subtracting overlaps. Derive only linked request/docs/new buffer and preserve all scientific resources, policy/configuration and IF001r3 proof semantics/fresh buffer-inventory-binding-plan-dispatch order. Start linked run evidence before scheduling; capture/start failures halt the allocated linked run with original diagnostic evidence and no worker. Duplicate/reconcile performs no new capture; missing original in-memory caller remains an inspectable refusal with no inferred grant/replay. Source AST/compile only; all runtime, tests, hard-loss, acceptance and connected verification remain NOT_RUN under C010. No native IDs/IF/schema or checkboxes changed.


2026-10-20 final integrated actual-function build set: four existing production targets (app, benchmark sidecar, RSI controller/custodian and RSI worker broker), linux/amd64, frozen candidate `1715f76e0206ec0b0d9e33a3a0e961eb4ae2f48f9c243adf648e9f3cfdb5c81f`, completed as BUILT_BUILD_ONLY at 2026-10-20T16:15:14.796560+00:00. Exact receipt `.test_logs/m1/resume-20261020-01/functional-production-build-02b/receipt.json`, SHA256 `bf10fa54e7f0f7aee4706e5677676b39d2693e1afc583e1a65ffffb810684c6d`. The same frozen public ZIP/context produced all targets; post-build source changes are absent. This candidate includes the original CLI/web/Search/actual-start increments, I033 exact per-run input/science mapping, fresh linked replan input capture, exact RSI interrupted signed-history restoration and exclusive atomic record installation. Four benchmark case implementations remain present with current shared observers. No tests, collection, benchmarks/scoring, smoke, browser, application startup, runtime-inspection container, model call, scientific/native security/cessation, GPU/ARM64/GB10 or full-system qualification ran. Those checks remain NOT_RUN under user-directed C010; builds establish artifact production only. Protected operation prerequisites and explicit source limitations remain unchanged. Older functions01 images/evidence and the original incomplete functions02 set receipt are preserved. That original02 orchestration stopped because tagging changed mutable RepoDigests; its exact app image was reused after immutable ID/platform/label/config comparison. No checkbox, AC/V or full-M1 acceptance is promoted.

| Target | Local tag | Exact image ID |
| --- | --- | --- |
| app-production | `ai4r-m1-app:20261020-functions02` | `sha256:d318cce326138947420851e1dd632a3e9227fdca020790cdf06abe81d7eb252a` |
| sidecar-production | `ai4r-m1-sidecar:20261020-functions02` | `sha256:5b297b6278f7eedbc203c0ecb8d65a583acd43e63cdb91f732ec29fc2791c376` |
| rsi-production | `ai4r-m1-rsi:20261020-functions02` | `sha256:f8821a84e8f66d20d984f4e46c278ed5711342a5f3837ee8eabf12a77dfb0570` |
| rsi-worker | `ai4r-m1-rsi-worker:20261020-functions02` | `sha256:66a85b875bec65435f2e28e8123388c7e77120fdc200957f0120a51bd50abb38` |

Separate ARM64 build-only follow-on outcome: `BLOCKED_BUILD_PREREQUISITE`; original receipt `.test_logs/m1/resume-20261020-01/functional-production-build-03-arm64/receipt.json`, SHA256 `6d6952a7566459566a0bb2aced82d4be0477249baf0b31c2138fcecc5d1b24cb`. Original blocker: `DEFAULT_LOCAL_BUILDER_ARM64_NOT_ADVERTISED_OR_METADATA_UNAVAILABLE`; advertised platforms: linux/amd64, linux/amd64/v2, linux/amd64/v3. Zero ARM builds were dispatched when the required platform was absent; no QEMU/binfmt installation, builder bootstrap or native GB10/GPU qualification follows.


2026-10-20 Root functional source integration at High: Existing B03/T012/T013 AC003/004/006 now reject planned research node IDs already occupied by pre-plan work through the original structure check before freeze. intention_compiler is occupied in both modes; planner only in planned mode. Existing protected planned infeasibility/link depth and static no-link behavior remain unchanged. This correction covers identity collisions only; raw malformed-proposal custody remains separate ongoing implementation. Exact four-source adoption and isolated source/native/caller pins: `.test_logs/m1/resume-20261020-01/functional-corrections-root-adoption-01/receipt.json`. Source AST/compilation only; no imports or product execution. All runtime, model, native/scientific, permissions, benchmark, security/cessation and AC/V acceptance remain NOT_RUN under user-directed C010. Four benchmark implementations are preserved. No IF/schema/native revision, checkbox or historical outcome changes. Functions02 images and checkpoint03 are the preceding historical source candidate; a new build is required.


2026-10-20 Root Planner candidate-capture integration, existing B02/T009, B03/T012/T013 and B04/T016 AC002/003/005/006: completed returned-text parser/schema failures are now retained as exact raw ProducedArtifact bytes for the existing Runner capture-before-validation, deterministic FAIL, Gate rejection, Coordinator plan_infeasible and bounded linked Compiler path. Valid bounded INFEASIBLE handling remains; actual missing schema/model/runtime/budget faults still propagate without invented proposals or automatic linkage. The existing Runner failed/schema diagnostic is retained; no Runner, client, wire, IF or schema change was made. Authored Planner advances m1-1 to m1-2 with exact body/carrier/check-claim/declaration/catalog hashes, as required when body changes. Existing protected checking compatibility, admission/calibration where applicable and explicit standing are still required; no installed state or same-version admission was overwritten, migrated or auto-qualified. Existing embedded checking-asset descriptive IDs are not their content-addressed Store Ref identities; new target-version bytes receive distinct Refs through unchanged put_record semantics. This completes the source correction previously recorded as separate pending raw-proposal custody, not runtime acceptance. Exact three-file adoption: `.test_logs/m1/resume-20261020-01/planner-candidate-root-adoption-02/receipt.json`; isolated original/raw-flow/release pins remain in planning-functions-high-02. AST compilation and static release-byte consistency only; all behavior, actual admission/model/native/scientific/benchmark and AC/V acceptance remain NOT_RUN under user-directed C010. Four benchmark implementations remain; native revisions, work/check/AC IDs, checkboxes and historical results are unchanged. Functions02/checkpoint03 precede these sources.


2026-10-20 current functional build set functions04: four fresh linux/amd64 production targets completed BUILT_BUILD_ONLY at 2026-10-20T16:33:54.209322+00:00, frozen candidate `27419313e0bea335499e88502cd59050b52fc57b6cbb9ddcece0d300600e187b` (4595 exact source files). Original receipt `.test_logs/m1/resume-20261020-01/functional-production-build-04/receipt.json`, SHA256 `0350d84e343a6bff771a9ac6861b262697069bff6012074df30ab8b0cfb58996`. One frozen public ZIP/context produced the app, benchmark sidecar, RSI controller/custodian and RSI worker broker; final source, image and parent identities stayed exact. This candidate adds the High functional corrections to previous CLI/web/Search/input/start/history work: production-umask-compatible new scientific preparation/read-only asset directories, pinned Capsule declaration context/family routing constraints, protected pre-plan node-ID collision rejection and byte-exact malformed Planner candidate handling in authored release m1-2. The new Planner release still needs existing protected checking compatibility, applicable admission/calibration and standing; no installed admission or frozen old version was overwritten. All four benchmark case implementations remain present; no case was executed or scored. No application/model/native scientific startup, runtime-inspection container, tests/collection/smoke/browser, benchmark/security/cessation or full-system qualification ran. All such current checks and AC/V acceptance remain NOT_RUN under C010, never PASS. ARM64 remains unavailable under the preserved03 build-prerequisite observation (builder advertised only AMD64 variants); no new ARM metadata attempt/build or GB10/GPU qualification was performed. Current science remains CPU-only; operational RSI independent qualification and complete offline installation closure remain incomplete. Earlier01/02/02b/03 evidence and images/checkpoint03 remain historical; no checkbox, native identity/revision or full-M1 acceptance is advanced.

| Target | Local tag | Image ID |
| --- | --- | --- |
| app-production | `ai4r-m1-app:20261020-functions04` | `sha256:8702e96ea28dc036e75e2544ac6506d7e10c83246afeb1c8de8a8ccdd1ecdf32` |
| sidecar-production | `ai4r-m1-sidecar:20261020-functions04` | `sha256:ac7e57bcb19eca8e4c7bcdb1d69b81880362d24ddafd3c0a77e8006c5a0d14f4` |
| rsi-production | `ai4r-m1-rsi:20261020-functions04` | `sha256:f4685729513385600571f507ad850a25014d31e94ed106ccb7983b99338fceed` |
| rsi-worker | `ai4r-m1-rsi-worker:20261020-functions04` | `sha256:3e63acfa084495620707ec69f3fc9fd2042b14cf245e4ea507a001b48cef2a60` |


2026-10-20 current functional build functions05: four fresh linux/amd64 app/benchmark-sidecar/RSI-controller/RSI-worker targets completed BUILT_BUILD_ONLY at 2026-10-20T17:02:59.955250+00:00, frozen candidate `fac1db7c7c87098370a51905cdab00bd972c3e1dd665113e4b3b432d6b798208` (4596 exact source files). Receipt `.test_logs/m1/resume-20261020-01/functional-production-build-05/receipt.json`, SHA256 `d2e3e147d1ab1beeefac9085be8a9bbef4ba5c9839a91a397ba24061a938c9c4`. This exact candidate adds I034 original ordinary interrupted startup history and I035 actual Running/Evaluating transitions to the prior integrated CLI/web/Search/input/Capsule/router/Planner/RSI functions. Final source/context/ZIP/image/parent identities remained exact. Linked restart ownership closure remains incomplete; missing originals stay unknown, effects never replay and no lease release is inferred. The four benchmark cases remain implemented and packaged. Their execution and other new tests/collection/benchmark/scoring/smoke/browser/application/model/scientific/security/cessation/full-system checks remain NOT_RUN under user C010. ARM64 remains blocked by preserved03 builder metadata with no new attempt; science is CPU-only, and protected operation/Planner m1-2 admission/RSI qualification/offline closure prerequisites remain incomplete. Older01/02/02b/03/04 source/images/receipts/checkpoints remain historical and unchanged. This build-only progress promotes no checkbox, V/AC or full-M1 acceptance.

| Target | Local tag | Image ID |
| --- | --- | --- |
| app-production | `ai4r-m1-app:20261020-functions05` | `sha256:5bc86e9f252193bbdb94a69fd4f84519f9a2af74a8286843014567b8a207a8e6` |
| sidecar-production | `ai4r-m1-sidecar:20261020-functions05` | `sha256:eddb01906a58e17340abbb5a873c6d601f0dd5e99a6c031ab4a5679f739da933` |
| rsi-production | `ai4r-m1-rsi:20261020-functions05` | `sha256:3e96fb81fe3503234b5fdb4aecae40360efdc8f397bb4078647b4262e7ebc9ff` |
| rsi-worker | `ai4r-m1-rsi-worker:20261020-functions05` | `sha256:171a91095fd69c43b02314ca1a3a0e74f74b2728cf8773ddfc94100203ab8cc2` |


2026-10-20 current functional build functions06: four fresh linux/amd64 app/benchmark-sidecar/RSI-controller/RSI-worker targets completed BUILT_BUILD_ONLY at 2026-10-20T17:20:45.957016+00:00, frozen candidate `5d4db99740b0922c2dc1f63ba665929163dac7bb9a29910233edd4ec1402dc87` (4596 exact source files). Receipt `.test_logs/m1/resume-20261020-01/functional-production-build-06/receipt.json`, SHA256 `f7d5799018e93c607d2a28aa1ae77819ad8fe9ded31c231bdb4186f391336c8d`. This exact candidate includes I036 original bounded linked-allocation recovery ownership and I037 read-only actual allocation inspection with literal legacy compatibility, plus I034 ordinary interrupted startup history and I035 actual Running/Evaluating transitions, alongside the integrated CLI/web/Search/input/Capsule/router/Planner/RSI functions. Final source/context/ZIP/image/parent identities remained exact. The exact original ordinary planned depth1-to-depth2 linked allocation is now supported; missing/corrupt/unsupported original closure stays unknown, effects never replay and no lease release is inferred. The four benchmark cases remain implemented and packaged. Their execution and other new tests/collection/benchmark/scoring/smoke/browser/application/model/scientific/security/cessation/full-system checks remain NOT_RUN under user C010. ARM64 remains blocked by preserved03 builder metadata with no new attempt; science is CPU-only, and protected operation/Planner m1-2 admission/RSI qualification/offline closure prerequisites remain incomplete. Older01/02/02b/03/04/05 source/images/receipts/checkpoints remain historical and unchanged. This build-only progress promotes no checkbox, V/AC or full-M1 acceptance.

| Target | Local tag | Image ID |
| --- | --- | --- |
| app-production | `ai4r-m1-app:20261020-functions06` | `sha256:4c3c908a5abd3f2f1e805f0548e226fb8cc3f2e1ca169089c5eb5803a505f170` |
| sidecar-production | `ai4r-m1-sidecar:20261020-functions06` | `sha256:b037d5beb15145a561a25a430c5df947243c8139971dbeef57a538c7b9737470` |
| rsi-production | `ai4r-m1-rsi:20261020-functions06` | `sha256:3106eb2820f9400eb038e89bad79b27999a27106cc256359ef57c381b08d8bcf` |
| rsi-worker | `ai4r-m1-rsi-worker:20261020-functions06` | `sha256:439bc6adeda8c7926a7adc94ac8089fadcc05a0e766fd6f89d2763f42e243ce1` |
