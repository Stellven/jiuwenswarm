# Tasks: Personal Codex Subscription Runtime

Historical source note: T030 retains its original architecture path and recorded scope. Its [original architecture reference](https://github.com/Stellven/jiuwenswarm/blob/343a77dbd5e6dcd18de2e57794cc992d36c2f35c/docs/architecture/OVERVIEW.md) is historical; current M1 product/design input starts at [build-package](../../docs/architecture/build-package/README.md). This routing note does not change task identities, progress or evidence.

**Version**: 0.3, M1 authorized; production tasks remain proposed; bounded verification status is recorded below.
**Input**: [plan v0.3](plan.md), [spec v0.2](spec.md), research.md, data-model.md, contracts/runtime.md and quickstart.md.
**Prerequisites**: write_code v0.9 authorizes M001-M006 following the presented product milestone. Broader T001-T033 still depend on their applicable G1–G4 gates; task generation does not close them.
**Tests**: Required by FR-008 and the SOP; include protocol, policy, lifecycle, settings/session, fresh-profile and real-account checks.
**Organization**: User stories match the three P1 stories in spec v0.2. AC-05 is retired. Owner for all proposed work: Xiaoyang, supported by AI; collaborator assignments require actual confirmation.

## Format: `[ID] [P?] [Story] Description`

[P] marks only disjoint work that can run together after shared prerequisites. A checked task must link actual evidence; adding code alone is insufficient. Only separately authorized R001-R004 have completion evidence; production tasks remain unchecked.

## Path Conventions

Paths are repository-relative when qualified. In a list, unqualified sibling filenames inherit the preceding directory. The frontend source prefix is jiuwenswarm/channels/web/frontend/src/; frontend tests and package.json are relative to jiuwenswarm/channels/web/frontend/. New codex_subscription modules and test_codex_* files below are proposed additions. Existing source paths were inspected; do not invent dependency patches in installed site-packages. Any necessary upstream fix must enter an explicitly tracked adapter or reviewed dependency revision.

## Authorized bounded verification

The user approved the presented verification steps 1 and 2; see TASK Section 4 and write_code v0.6. These research substeps contribute to T001/T002/G4 but cannot close their full acceptance obligations.

- [x] R001 Exercise installed harness approval, interaction identity, pause and event projection boundaries with offline fixtures in verification/test_boundaries.py; record proven behavior and counterexamples. Status: Complete within bounded scope; TEST_REPORT T-20/T-21 contains evidence; G1-G4 remain open.
- [x] R002 Exercise packaged App Server initialization and signed-out account read in a fresh isolated home using verification/probe_app_server.py; verify owned-process cleanup without login or model turns. Status: Complete within bounded scope; TEST_REPORT T-20/T-21 contains evidence; G1-G4 remain open.

- [x] R003 Build isolated approval/launch guards against the R001 counterexamples in verification/guard_prototype.py, verify failure and race cases, and rerun a signed-out App Server probe through the guarded launcher. Complete in isolated scope; TEST_REPORT T-24/T-26. G4 and production acceptance remain open.
- [x] R004 Add frontend approval-state/contract prototype and Node fixtures under verification/; exercise shared JSON payloads against the Python guard. Include disabled duplicate actions, session changes, stale errors and unknown delivery. Complete for headless state and cross-language contract; TEST_REPORT T-24/T-25. Real React/browser acceptance remains in T010/T013/T025/T027.

## Phase 1: Setup (Shared Infrastructure)

Purpose: finish feasibility and scope decisions before dependent production work. Research fixtures may be drafted under preparation authority; executing live model scenarios or implementing production code requires its defined scope.

- [ ] T001 Prove G1 main-agent and team-leader integration using bounded fixtures for jiuwenswarm/server/runtime/agent_adapter/agent_adapters.py and jiuwenswarm/agents/swarm/assembly.py; document each skipped rail/permission/budget/memory behavior and its equivalent in specs/AI4R-001-codex-subscription/research.md; pass only with single tool execution and correct session/control output (AC-02/03/07/08).
- [ ] T002 [P] Prove G2 auxiliary text/JSON semantics for jiuwenswarm/symphony/llm.py and enumerate every remaining direct consumer C06–C13/C18 in specs/AI4R-001-codex-subscription/research.md; reject unsupported controls and autonomous tool use (AC-06/08).
- [ ] T003 [P] Resolve G3 for jiuwenswarm/agents/harness/common/memory/embeddings.py and jiuwenswarm/agents/harness/common/tools/{image_tools.py,audio_tools.py,video_gen_tools.py,search_tools.py} and grouped specialist/platform rows in specs/AI4R-001-codex-subscription/research.md; provide per-capability equivalent fixtures or an explicit requirements-change decision, never silent removal (AC-08).
- [ ] T004 Record concrete plan/contract/ADR/task scope and Lead decision in docs/tasks/AI4R-001/TASK.md and write_code.md; confirm affected owners and G1–G3 dispositions before production phases. No implementation authorization inferred from spec confirmation.

Checkpoint: G1–G3 resolved or a separately bounded research directive issued; production tasks remain gated. T004 cannot label unresolved full coverage approved by omission.

## Phase 2: Foundational (Blocking Prerequisites)

Purpose: establish subscription policy and lifecycle before story integration. Depends on T004 and applicable research outcomes.

- [ ] T005 Add failing policy/process tests in tests/unit_tests/runtime/test_codex_subscription_policy.py for contaminated parent environment, external provider/fallback configs, absent approval hook, automatic approval defaults, malformed/empty approval payloads, stale control-message forwarding and unexpected server requests; assert zero legacy-provider construction/outbound calls (G4, AC-03/06).
- [ ] T006 [P] Add failing identity/state tests in tests/unit_tests/runtime/test_codex_session_adapter.py for data-model.md constraints: “schema_version=1”, “runtime_mode=codex_subscription”, “generation monotonic integer”, “one active turn”, required thread_id after start and exact pending-interaction matching; assert durable generation/fingerprint reconciliation across same-account, changed-account and unverifiable-account restarts, and that duplicate/stale requests cannot cross sessions (AC-03/07).
- [ ] T007 Implement jiuwenswarm/server/runtime/codex_subscription/policy.py and service.py with explicit pinned binary, sanitized actual child launch, ChatGPT-only managed auth, registered worker cleanup, safe catalog and fail-closed approvals; make T005 pass and record G4 evidence in TEST_REPORT (AC-01/04/06).
- [ ] T008 Implement session binding/receipts in jiuwenswarm/server/runtime/codex_subscription/session.py using ApplicationProfile, AccountConnection, SessionBinding, Execution, PendingInteraction and ToolReceipt validation from data-model.md; make T006 pass (AC-02/03/07).

Checkpoint: no story uses a permissive provider fallback or unvalidated approval path.

## Phase 3: User Story 1 — Start without a model API key (Priority: P1)

Goal: fresh first use, managed login/catalog and explicit readiness.
Independent test: quickstart Q1a, plus isolated mocked auth races; main-chat/team completeness not claimed.

### Tests for User Story 1

- [ ] T009 [US1] Add tests/unit_tests/common/test_codex_profile.py and tests/unit_tests/gateway/test_codex_subscription_handlers.py covering new-root selection before caching, no force overwrite/import, signed-out/pending/ready states, catalog errors and scoped login responses (AC-01/06).
- [ ] T010 [P] [US1] Add jiuwenswarm/channels/web/frontend/tests/codexSubscription.test.mjs and jiuwenswarm/channels/web/frontend/package.json test:codex-subscription entry for onboarding/login failure/status/signout, no key fields and auth-frame log redaction (AC-01/04/06).

### Implementation for User Story 1

- [ ] T011 [US1] Add jiuwenswarm/common/codex_profile.py and adapt jiuwenswarm/common/utils.py, jiuwenswarm/init_workspace.py and launcher entry points to select a persistent separate root and seed only missing defaults; pass T009 profile cases (AC-01/07).
- [ ] T012 [US1] Adapt jiuwenswarm/server/control/config_service.py and jiuwenswarm/gateway/channel_manager/web/app_web_handlers.py to proxy proposed codex.auth.* and codex.models.list operations to the lifecycle owner; prohibit old operational key-provider mutation (AC-01/06).
- [ ] T013 [US1] Update frontend features/settings/services/settingsContract.ts, modules/models/OpenAIAccountField.tsx, modelAdapters.ts, features/modelSetupGuide/ and App.tsx to use subscription readiness/catalog; preserve shared settings UI, Chrome107, test IDs and both locales; sanitize services/webClient.ts auth traffic (AC-01/04/06).
- [ ] T014 [US1] Run Q1a for login/catalog/readiness without model execution; record actual auth/restart/logout behavior in docs/tasks/AI4R-001/TEST_REPORT.md without tokens or login codes; compare settings UI in browser (AC-01/06).

Checkpoint: first-use capability is independently demonstrated; this is an internal milestone, not whole-project completion.

## Phase 4: User Story 2 — Complete existing work using the subscription (Priority: P1)

Goal: main/code/team/background and supporting capabilities use the required execution path.
Independent test: Q2/Q3/Q6 across agreed inventory with provider-construction and outbound traps. Depends on foundation; live tests also depend on US1.

### Tests for User Story 2

- [ ] T015 [US2] Extend tests/unit_tests/runtime/test_codex_session_adapter.py with start/resume/stream/final, steering, late ACK and two-session fixtures preserving existing application session/execution envelopes (AC-02/07).
- [ ] T016 [P] [US2] Add tests/unit_tests/runtime/test_codex_tool_bridge.py for scoped MCP schema/authorization, denial, duplicate receipts, cancellation, stale answers and ambiguous external effects (AC-03).
- [ ] T017 [P] [US2] Add tests/unit_tests/runtime/test_codex_auxiliary.py for validated text/JSON, unavailable model/unsupported parameters, provider traps and no autonomous tool execution; include Symphony and background consumers assigned by T002 (AC-06/08).

### Implementation for User Story 2

- [ ] T018 [US2] Add jiuwenswarm/server/runtime/agent_adapter/interface_codex.py and adapt agent_adapters.py to select the subscription adapter for main/code modes; implement the G1-approved host rail equivalence and make T015 pass (AC-02/03/07/08).
- [ ] T019 [US2] Add jiuwenswarm/server/runtime/codex_subscription/tools.py implementing the session-scoped local MCP bridge and fail-closed interaction mapping; preserve single logical executor and make T016 pass (AC-03).
- [ ] T020 [US2] Adapt jiuwenswarm/agents/swarm/assembly.py, jiuwenswarm/server/runtime/agent_adapter/team_helpers.py and jiuwenswarm/server/agent_ws_server.py using the G1-reviewed leader/member/scheduler path; demonstrate budget/permission/plan/memory behavior and prohibit cached/direct Model fallback (AC-02/03/06/08).
- [ ] T021 [US2] Add jiuwenswarm/server/runtime/codex_subscription/text.py and convert jiuwenswarm/symphony/llm.py, jiuwenswarm/symphony/skill_retrieval/runtime.py and all T002-registered auxiliary call sites to the proven port; make T017 pass without silently dropping required controls (AC-06/08).
- [ ] T022 [US2] Implement only the T003-approved capability solutions in jiuwenswarm/agents/harness/common/memory/embeddings.py and jiuwenswarm/agents/harness/common/tools/{image_tools.py,audio_tools.py,video_gen_tools.py,search_tools.py}, plus registered specialist paths; attach per-row fixtures to TEST_REPORT. Block if equivalence remains unresolved; no mock/disabled-feature completion claim (AC-08).
- [ ] T023 [US2] Execute Q1b after T018/T019 and required runtime integration, then Q2/Q3/Q6 and relevant existing model/settings/stream/ACK/permission suites; update every C01–C20 row with actual evidence in docs/tasks/AI4R-001/TEST_REPORT.md (AC-02/03/06/08).

Checkpoint: every agreed capability has evidence; unresolved G3 rows keep US2 incomplete.

## Phase 5: User Story 3 — Recover from failures without hidden API use (Priority: P1)

Goal: honest failure/recovery and persistent, isolated new-profile sessions.
Independent test: Q4/Q5 with fake quota/network faults and controlled runtime restart.

### Tests for User Story 3

- [ ] T024 [US3] Add tests/unit_tests/runtime/test_codex_lifecycle.py for expiry/quota/network/process loss, logout generations, cleanup, ambiguous execution and no replay/fallback (AC-04/06/07).
- [ ] T025 [P] [US3] Extend frontend tests/codexSubscription.test.mjs and existing sessionInput/history fixtures for stale decisions, account changes, restart restoration and two-session failure isolation (AC-04/07).

### Implementation for User Story 3

- [ ] T026 [US3] Implement typed failure, bounded reconnection/reconciliation and account-generation lifecycle in jiuwenswarm/server/runtime/codex_subscription/service.py and session.py; no blind retry after accepted turns or side effects; make T024 pass (AC-04/06/07).
- [ ] T027 [US3] Adapt frontend hooks/useWebSocket.ts, services/sessionEventGate.ts and stores/chatStore.ts/sessionStore.ts only where required to preserve delivery-unknown, pending interaction and restart states; make T025 pass (AC-02/03/04/07).
- [ ] T028 [US3] Execute Q4/Q5 with two new-profile sessions and a runtime restart, preserving project/history and confirming signed-out background blocking; record results in docs/tasks/AI4R-001/TEST_REPORT.md (AC-04/06/07).

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T029 Make pyproject.toml and verified launch/package resources ship the selected Codex runtime/extra; test each intended launcher/platform in research C20, retain no operational key-provider default, and record environment revisions in docs/governance/ENVIRONMENT.md (AC-01/06/08).
- [ ] T030 Update docs/architecture/OVERVIEW.md, approved contracts/ADR, module AGENTS, docs/code-map/FILE_MAP.md and docs/tasks/AI4R-001/IMPLEMENTATION_CHECKLIST.md from their templates; author explains changed functions and call chains.
- [ ] T031 Run the complete agreed regression/acceptance scope, frontend build and settings visual checks; measure representative performance if required by the approved design; record C/B, fixture/model versions, counts and limitations in docs/tasks/AI4R-001/TEST_REPORT.md.
- [ ] T032 Conduct actual diff-based AI review using REVIEW_TEMPLATE in docs/tasks/AI4R-001/review.md, resolve findings, then obtain the independent qualified human's review for the current version; prepare PR description targeting ai4r_main_branch.
- [ ] T033 After authorized integration, verify the actual merge result, complete docs/tasks/AI4R-001/HANDOFF.md and update docs/governance/CURRENT_STATUS.md; do not mark Done before remaining checks and receipt are complete.

## Dependencies & Execution Order

### Phase Dependencies

T001–T003 are independent research tracks; T004 depends on their applicable outcomes. Foundation T005/T006 may run together after authorization; T007 follows T005, T008 follows T006 and T007. Production phases cannot bypass unresolved prerequisite gates.

US1: T009/T010 -> T011/T012/T013 -> T014; backend depends on foundation, UI can use contract fixtures while backend develops.
US2: T015/T016/T017 -> T018/T019/T020/T021/T022 -> T023; T020 depends on T018/T019, T022 depends on approved T003 outcomes, T023 requires all relevant implementations and live login.
US3: T024/T025 -> T026/T027 -> T028, after US1/US2 integration surfaces exist.
T029–T031 precede formal T032; T033 follows authorized integration.

### User Story Dependencies

All stories have mock-driven independent tests. Live US2 needs US1 sign-in; live US3 needs run/history behavior. They are not falsely described as fully independent production deliveries.

### Within Each User Story

Write meaningful failing fixtures first, implement only approved behavior, run tests and record evidence. Never change expected outcomes merely to make tests green.

### Parallel Opportunities

Disjoint research and test files marked [P] can be worked on concurrently after prerequisite completion. Shared service.py/session.py and frontend controller/store edits must be coordinated sequentially. Branch ownership and actual staffing remain governed by the SOP.

## Parallel Example: User Story 1

T009 backend profile/auth fixtures and T010 frontend mock-controller fixtures can run together after the draft contract is approved. T012/T013 integration follows agreed payloads. For US2, T016 tool fixtures and T017 auxiliary fixtures are disjoint; for US3, T024 backend failure tests and T025 frontend state tests are disjoint.

## Implementation Strategy

### MVP First (User Story 1 Only)

Use US1 as a local milestone for login/readiness and no-key setup. Do not release or describe it as the complete objective.

### Incremental Delivery

Resolve feasibility -> enforce policy/lifecycle -> first-use -> main/code/team/auxiliary/capabilities -> failure/concurrency -> full verification/review/integration. Keep operational defaults subscription-only at delivery; temporary development staging is not a user-visible provider fallback.

### Parallel Team Strategy

No additional human owner is assigned by this document. Xiaoyang may assign independent files after identifying owners and authorized branches; no concurrent shared-file editing is implied.

## Discoveries and decisions

| Time | Discovery / decision | Evidence and rationale | Effect on steps / AC / authority | Next action / owner |
| --- | --- | --- | --- | --- |
| Design stage | Native harness exists but skips native rails; direct account path differs | research R1/R4 | T001/T005 prerequisite; no blanket replacement claim | Xiaoyang |
| Design stage | No established embedding/media equivalence | C12–C18 | T003/T022 block AC-08 | Xiaoyang |
| Current conversation | User confirms spec v0.2 and asks for proposal | TASK decision record | Design drafting authorized, no production approval inferred | Xiaoyang reviews concrete design |

## Remaining work and handoff

| Incomplete item | Cause / blocker | Concrete next action | Owner | Deadline / resumption condition |
| --- | --- | --- | --- | --- |
| Feasibility and coverage | G1–G4 unproven | T001–T003 and scoped G4 tests | Xiaoyang | Before dependent implementation; no fabricated calendar deadline |
| Broader design/directive approval | M1 authorized; other capability gates remain | Resolve affected G1-G4 items before later capability work | Xiaoyang | Before each dependent scope |
| M1 verification and full acceptance | M1 code exists; live/browser/full-stack checks incomplete | Finish M005/M006, then remaining capability work | Xiaoyang | Browser available and personal account sign-in |
| Independent review/delivery | Reviewer unassigned | Identify reviewer and follow T032/T033 | Xiaoyang | Before formal final review/integration |

Read before resuming: root/local AGENTS, TASK, write_code, spec v0.2, plan/tasks v0.3, research and contract. Current M1 source is uncommitted; its hash manifest is in TEST_REPORT; recorded 87 backend/51 frontend baseline passes are not new feature passes.

## Plan closure

Final outcome and acceptance evidence: not complete. Deviations: none accepted beyond CR-01's fresh-start scope. Post-merge checks and handoff: not performed. All T001-T033 production/feasibility-gate checkboxes remain unchecked; R001-R004 completion does not imply those broader gates passed.

## Template coverage

Native tasks-template phases, story labels, dependencies, parallel example and delivery strategy retained. SOP PLAN §3/5/6/7 map to phases, discoveries, remaining work and closure here. PLAN §1/2/4 technical content remains in plan.md and quickstart; no duplicate design or results table.

## M1: Authorized product login and ordinary-chat slice

Authority: TASK Section 4 and write_code v0.9. Execution order below specializes the authentication/chat parts of T005-T018; it does not mark those broader tasks complete or waive G1-G3. User acceptance of this staged scope permits proceeding despite the three future readiness checklist items. The checklist remains read-only.

- [x] M001: Establish protocol, profile, account/session and failure tests before production transport code.
- [x] M002: Implement sanitized App Server transport and managed account/chat service under `server/runtime/codex_subscription/`.
- [x] M003: Connect real AgentAdapter, authenticated gateway RPC, fresh-profile launcher and existing history/event flow.
- [x] M004: Add bilingual original-chat subscription controls, no-key onboarding, secret-free dev traffic logging and frontend interaction tests.
- [ ] M005: Run backend/frontend integration checks, build and signed-out smoke; inspect browser UI; update template-conformant report/file map/review.
- [ ] M006: Xiaoyang signs in on his own machine; verify actual streaming, cancellation and refreshed history, then review remaining whole-project work. No claim of completion without this evidence.

M001-M004 record implementation and fixture completion only. M005 startup, actual Gateway/AgentServer socket journey, tests/build and documentation are verified; browser inspection remains unavailable, so M005 stays unchecked. M006 requires personal sign-in and real subscription/model acceptance. The actual preview is started locally; native work-item completion is not release approval. Results and historical failed attempts are in TEST_REPORT. No active AC is declared fully passed.

### M1 user acceptance and publication update (2026-09-28)

Xiaoyang accepted the running localhost:5173 demo and explicitly requested direct publication to the five team branches. Post-commit backend/frontend/build/socket checks pass in TEST_REPORT. This supersedes earlier pending-user-acceptance and uncommitted-source statements. Detailed live scenario traces and independent visual review remain unrecorded, so M005/M006 checkboxes retain their stricter evidence meaning; they do not revoke the user's explicit demo publication instruction. Broader T001–T033 and whole-project ACs remain open.
