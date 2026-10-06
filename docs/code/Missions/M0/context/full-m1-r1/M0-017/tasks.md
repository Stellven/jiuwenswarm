---
description: "TASK-native work and acceptance/evidence correspondence"
---
# Tasks: M0-017 — Operational workstation shell and ordinary evaluation client

**TASK**: [TASK.md](TASK.md) | **Spec / Plan revisions**: r1 / r1
**Feature directory**: docs/code/Missions/M0/M0-017/

Verification work is required by spec and plan. This is the sole implementation work list. Preparing these artifacts does not complete product work or establish runtime acceptance.

## Work Items

### Foundation / shared definitions

- [ ] T001 [US1] Read all allocated exact source clauses/global restrictions and owning IFs; freeze independent fixture labels, dependency/runtime prerequisites and relevant dataset/profile/source identities; all B/AC/V; docs/code/Missions/M0/M0-017/plan.md and evidence/fixture-manifest.json.
- [ ] T002 [US1] Implement the owned/consumed r1 boundary representations and validated fixtures without authority duplication; all B/AC/V; Existing: pyproject.toml [project.scripts] and optional dependency tui; distribution metadata currently names workswarm, so PRD pip install jiuwenswarm compatibility must be reconciled rather than assumed.; Existing: Dockerfile.claw; packages/jiuwenswarm-tui/pyproject.toml; jiuwenswarm/start_services.py; jiuwenswarm/init_workspace.py; jiuwenswarm/debug_launcher.py.; Existing: jiuwenswarm/channels/cli/main.py; jiuwenswarm/channels/process_cli/{main.py,machine_entry.py,machine_io.py,machine_result.py,protocol/model.py,protocol/jsonl.py}; current machine protocol is a reuse anchor, not an implemented AI4Research client contract.; Existing: jiuwenswarm/channels/web/app_web.py; jiuwenswarm/gateway/channel_manager/web/web_http_auth.py; jiuwenswarm/common/auth/session_store.py; jiuwenswarm/channels/web/frontend/src/stores/sessionStore.ts; jiuwenswarm/channels/web/frontend/src/components/ArtifactsPanel/artifactCollection.ts.; Existing: jiuwenswarm/channels/tui/frontend/src/core/commands/builtins/{swarmflow.ts,swarmflows.ts}; jiuwenswarm/channels/tui/frontend/src/core/supervision/protocol.ts; jiuwenswarm/agents/harness/team/handlers/workflow_state.py.; Existing: jiuwenswarm/observability/{config.py,store.py}; jiuwenswarm/gateway/channel_manager/web/trajectory_http.py; tests/unit_tests/test_start_services_ready_hint.py; tests/unit_tests/process_cli/; tests/unit_tests/channel/test_web_channel_ws_sessions.py.; Existing: jiuwenswarm/channels/web/AGENTS.md and frontend/AGENTS.md; retain native controls, locale resources, Chrome 107 support, semantic theme tokens and test-ID naming rules. Trajectory edits also require its subtree AGENTS.md.; Proposed: jiuwenswarm/ai4research/shell/{client.py,cli.py,doctor.py,bootstrap.py,presentation.py,tmux.py} consuming owned application agreements; exact functions are implementation choices.; Proposed: deployment/ai4research/{compose.yaml,benchmarker.py} for one workflow application and optional ordinary client, with independently owned state/artifact and campaign volumes.; Proposed: tests/unit_tests/ai4research/test_shell.py; tests/integration_tests/ai4research/test_shell.py; tests/journeys/ai4research/test_operational_shell.py; narrowly added native frontend/TUI fixtures where necessary..

### Block B01 — FR-001

- [ ] T003 [US1] Provide supported Python distribution installation and a single jiuwenswarm-start bootstrap without introducing desktop binaries or additional execution hosts; reconcile the requested pip distribution name with current workswarm metadata through a registered packaging decision. B01, AC-001; `pyproject.toml; jiuwenswarm/start_services.py; jiuwenswarm/ai4research/shell/bootstrap.py (proposed)`.
- [ ] T004 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V01; AC-001, B01; `tests/unit_tests/ai4research/test_shell.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B02 — FR-002

- [ ] T005 [US1] Provision idempotent workspace, state/evidence, library and offline-RSI directories using the owning tasks' formats and custody boundaries; keep durable account/profile storage and hidden fixture-oracle material outside workspace deletion and the public repository. B02, AC-002; `jiuwenswarm/init_workspace.py; jiuwenswarm/common/auth/session_store.py; jiuwenswarm/ai4research/shell/bootstrap.py (proposed)`.
- [ ] T006 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V03; AC-002, B02; `tests/unit_tests/ai4research/test_shell.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B03 — FR-003

- [ ] T007 [US1] Expose separate liveness and doctor/readiness results that consume actual model authentication, IPC, storage, registered CC pins, frozen configuration, static-DAG validation and required-security capabilities. B03, AC-003; `jiuwenswarm/start_services.py; jiuwenswarm/server/runtime/codex_subscription/service.py; jiuwenswarm/ai4research/shell/doctor.py (proposed)`.
- [ ] T008 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V05; AC-003, B03; `tests/unit_tests/ai4research/test_shell.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B04 — FR-004

- [ ] T009 [US1] Route scriptable CLI submission, status, retrieval and explicit cancellation through the ordinary application boundary; provide a non-interactive headless mode with stable machine results and no human_session wait. B04, AC-004; `jiuwenswarm/channels/process_cli/machine_entry.py; jiuwenswarm/channels/process_cli/protocol/model.py; jiuwenswarm/ai4research/shell/cli.py and jiuwenswarm/ai4research/shell/client.py (proposed)`.
- [ ] T010 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V07; AC-004, B04; `tests/unit_tests/ai4research/test_shell.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B05 — FR-005

- [ ] T011 [US1] Serve the native web assets and ordinary control API on one loopback host endpoint, with protected session authentication on all workflow operations, consuming M0-002's token lifecycle and M0-001's protected model IPC. B05, AC-005; `jiuwenswarm/channels/web/app_web.py; jiuwenswarm/gateway/channel_manager/web/web_http_auth.py; Dockerfile.claw; jiuwenswarm/ai4research/shell/bootstrap.py (proposed)`.
- [ ] T012 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V09; AC-005, B05; `tests/unit_tests/ai4research/test_shell.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B06 — FR-006

- [ ] T013 [US1] Project protected run status, node/gate decisions, blockers, time/call budgets and permitted static trace/scorecard exports through existing native CLI/web/run-tree widgets without making UI state authoritative. B06, AC-006; `jiuwenswarm/agents/harness/team/handlers/workflow_state.py; jiuwenswarm/observability/store.py; jiuwenswarm/ai4research/shell/presentation.py (proposed)`.
- [ ] T014 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V11; AC-006, B06; `tests/unit_tests/ai4research/test_shell.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B07 — FR-007

- [ ] T015 [US1] Package/expose the native TUI and route full-product interactive blocking failures to correlated native human_session triage while retaining identical non-advancing gate policy in web, CLI/TUI and headless modes. B07, AC-007; `packages/jiuwenswarm-tui; jiuwenswarm/channels/tui/frontend/src/core/commands/builtins/swarmflow.ts; jiuwenswarm/ai4research/shell/presentation.py (proposed)`.
- [ ] T016 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V13; AC-007, B07; `tests/unit_tests/ai4research/test_shell.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B08 — FR-008

- [ ] T017 [US1] Manage POSIX tmux sessions/panes as owned local operational surfaces, separate from authoritative run state and process confinement. B08, AC-008; `jiuwenswarm/start_services.py; jiuwenswarm/ai4research/shell/tmux.py (proposed)`.
- [ ] T018 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V15; AC-008, B08; `tests/unit_tests/ai4research/test_shell.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B09 — FR-009

- [ ] T019 [US1] Expose final accepted reports, accepted artifacts and allowed Run Bundles through native artifact viewers and scoped retrieval while preserving scientific-negative results and audience boundaries. B09, AC-009; `jiuwenswarm/channels/web/frontend/src/components/ArtifactsPanel/artifactCollection.ts; jiuwenswarm/channels/web/app_web.py; jiuwenswarm/ai4research/shell/presentation.py and jiuwenswarm/ai4research/shell/client.py (proposed)`.
- [ ] T020 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V17; AC-009, B09; `tests/unit_tests/ai4research/test_shell.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B10 — FR-010

- [ ] T021 [US1] Provide an optional sequential Compose platform benchmarker as an ordinary scoped authenticated client using the same submit/status/retrieve/cancel contract, not as a second research execution service. B10, AC-010; `deployment/ai4research/compose.yaml and deployment/ai4research/benchmarker.py (proposed); jiuwenswarm/ai4research/shell/client.py (proposed)`.
- [ ] T022 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V19; AC-010, B10; `tests/unit_tests/ai4research/test_shell.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B11 — FR-011

- [ ] T023 [US1] Make the product launcher enforce its frozen allowlist and scope exclusions through owned security/configuration agreements without deleting unrelated platform capabilities or treating UI controls as policy enforcement. B11, AC-011; `jiuwenswarm/start_services.py; jiuwenswarm/ai4research/shell/bootstrap.py (proposed)`.
- [ ] T024 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V21; AC-011, B11; `tests/unit_tests/ai4research/test_shell.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Block B12 — FR-012

- [ ] T025 [US1] Verify the assembled operational shell on an identified candidate using connected client journeys, separately accounting for documentation/static checks, mocked wiring and real model/security/platform observations. B12, AC-012; `tests/journeys/ai4research/test_operational_shell.py (proposed); jiuwenswarm/channels/web/frontend/package.json; tests/unit_tests/process_cli`.
- [ ] T026 [US1] Implement independent normal/invalid/failure/recovery assertions and execute block V23; AC-012, B12; `tests/unit_tests/ai4research/test_shell.py`; retain `evidence/RUN-ID.md` and raw outcomes.

### Connected boundaries

- [ ] T027 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V02; inject `Dependency/bootstrap failure or foreign ownership blocks readiness; no guessed process kill, duplicate launch or silent system installation.` and check recovery; B01, AC-001; `tests/integration_tests/ai4research/test_shell.py`, `evidence/RUN-ID.md`.
- [ ] T028 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V04; inject `Invalid permissions, unsafe path, missing authored asset or inability to enforce a mandatory boundary blocks affected readiness and prevents work dispatch.` and check recovery; B02, AC-002; `tests/integration_tests/ai4research/test_shell.py`, `evidence/RUN-ID.md`.
- [ ] T029 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V06; inject `A missing prerequisite yields environment-blocked status; evidence-write failure never becomes a passed check.` and check recovery; B03, AC-003; `tests/integration_tests/ai4research/test_shell.py`, `evidence/RUN-ID.md`.
- [ ] T030 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V08; inject `Headless blocking outcomes terminate with non-zero status without reading stdin, opening prompts or bypassing checks.` and check recovery; B04, AC-004; `tests/integration_tests/ai4research/test_shell.py`, `evidence/RUN-ID.md`.
- [ ] T031 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V10; inject `Unsafe host exposure or absent authentication blocks this product launch; native source web mode's desktop-token exemption cannot be assumed sufficient.` and check recovery; B05, AC-005; `tests/integration_tests/ai4research/test_shell.py`, `evidence/RUN-ID.md`.
- [ ] T032 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V12; inject `Unavailable projection is visible but cannot modify/reconstruct an advancing verdict; malformed candidate text is rendered as data.` and check recovery; B06, AC-006; `tests/integration_tests/ai4research/test_shell.py`, `evidence/RUN-ID.md`.
- [ ] T033 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V14; inject `Triage remains a control-plane action, never a replacement node, gate override or permission escalation.` and check recovery; B07, AC-007; `tests/integration_tests/ai4research/test_shell.py`, `evidence/RUN-ID.md`.
- [ ] T034 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V16; inject `Ownership mismatch or unavailable tmux produces an actionable terminal-feature failure; no guess-based takeover.` and check recovery; B08, AC-008; `tests/integration_tests/ai4research/test_shell.py`, `evidence/RUN-ID.md`.
- [ ] T035 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V18; inject `Missing/corrupt/restricted output has explicit status; the shell cannot substitute a different candidate or manufacture bundle success.` and check recovery; B09, AC-009; `tests/integration_tests/ai4research/test_shell.py`, `evidence/RUN-ID.md`.
- [ ] T036 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V20; inject `A failed workflow halts; only campaign policy permits the client to proceed to its next separate case. Gate-disabled ablations are labeled invalid-for-product/admission and cannot alter production standing.` and check recovery; B10, AC-010; `tests/integration_tests/ai4research/test_shell.py`, `evidence/RUN-ID.md`.
- [ ] T037 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V22; inject `Prohibited configuration yields stable non-success and no side effect; no silent downgrade to an insecure or mock route.` and check recovery; B11, AC-011; `tests/integration_tests/ai4research/test_shell.py`, `evidence/RUN-ID.md`.
- [ ] T038 [US2] Execute connected verification against actual provider/consumer with required custody/guard/contract and real service where specified; V24; inject `A successful frontend build, unit fixture or HTTP liveness response cannot fill missing visual, account, confinement or supported-platform checks.` and check recovery; B12, AC-012; `tests/integration_tests/ai4research/test_shell.py`, `evidence/RUN-ID.md`.

### System contribution

- [ ] T039 [US3] Integrate the exact component/IF/profile and evidence manifest into M0-SYSTEM, execute affected connected stage/complete-journey checks, and reassess invalidated evidence; all AC/B/V; `docs/code/Missions/M0/M0-SYSTEM/tasks.md`.

## Acceptance and Evidence Matrix

| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md) | B01; M0-IF-017@r1 | T001, T002, T003 | V01 / T004; V02 / T027 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-002](spec.md) | B02; M0-IF-017@r1 | T001, T002, T005 | V03 / T006; V04 / T028 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-003](spec.md) | B03; M0-IF-017@r1 | T001, T002, T007 | V05 / T008; V06 / T029 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-004](spec.md) | B04; M0-IF-017@r1 | T001, T002, T009 | V07 / T010; V08 / T030 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-005](spec.md) | B05; M0-IF-017@r1 | T001, T002, T011 | V09 / T012; V10 / T031 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-006](spec.md) | B06; M0-IF-017@r1 | T001, T002, T013 | V11 / T014; V12 / T032 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-007](spec.md) | B07; M0-IF-017@r1 | T001, T002, T015 | V13 / T016; V14 / T033 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-008](spec.md) | B08; M0-IF-017@r1 | T001, T002, T017 | V15 / T018; V16 / T034 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-009](spec.md) | B09; M0-IF-017@r1 | T001, T002, T019 | V17 / T020; V18 / T035 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-010](spec.md) | B10; M0-IF-017@r1 | T001, T002, T021 | V19 / T022; V20 / T036 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-011](spec.md) | B11; M0-IF-017@r1 | T001, T002, T023 | V21 / T024; V22 / T037 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |
| [AC-012](spec.md) | B12; M0-IF-017@r1 | T001, T002, T025 | V23 / T026; V24 / T038 | NOT_RUN | None; runtime NOT_BUILT | Initial generated preparation; no runtime evidence reused |

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
