# Review record: AI4R-001

Version: 0.2. Template: [REVIEW_TEMPLATE](../../code/code_sop/templates/REVIEW_TEMPLATE.md). This is a bounded M1 AI self-review, not final review or merge approval.

## 1. Review target — required

- Task registry / artifact mode / author / module: [TASK v0.8](TASK.md); Spec Kit; Xiaoyang with AI assistance; M1 subscription login/basic chat.
- Risk level and rationale: High; account lifecycle, process ownership, session routing and frontend/backend integration.
- Working branch: `ai4r_xiaoyang`.
- Target branch: `ai4r_main_branch`.
- Reviewed implementation C: pending implementation commit. HEAD is `dc9e6afdbacdc78a5d2eede3b4ab0dd1347e7483`; it does not contain the uncommitted M1 changes.
- Target baseline B: `dc9e6afdbacdc78a5d2eede3b4ab0dd1347e7483`, fetched from origin/ai4r_main_branch on 2026-09-28; exact time not retained.
- Actual diff / working directory / command reviewed: repository root `D:\research\ai_for_research\jiuwenswarm`; `git diff --` for the tracked M1 integration files and direct reads of new runtime, adapter, launcher, component and test files. `git status --short` includes earlier preparation/SOP work. This is not a review of every earlier change.
- Implementation or integration version actually tested: uncommitted M1 files identified in `%LOCALAPPDATA%\ai4r-tools\evidence\AI4R-001\m1-journey-code-sha256.json`; [TEST_REPORT v0.8](TEST_REPORT.md). No separate integration commit.
- Acceptance source: [spec.md v0.2](../../../specs/AI4R-001-codex-subscription/spec.md), AC-01–AC-04 and AC-06–AC-08; AC-05 retired by CR-01.
- Design authorization: [plan.md v0.3](../../../specs/AI4R-001-codex-subscription/plan.md) M1 addendum and [write_code v0.9](write_code.md); Xiaoyang's presented-milestone continuation in TASK Section 4. Unpresented details are not claimed to have human review.
- Ordered work and progress reviewed: [tasks.md v0.3](../../../specs/AI4R-001-codex-subscription/tasks.md), M001-M006; broader T001-T033 remain incomplete.
- Verification evidence: TEST_REPORT Sections 3-7; mocked provider tests, React DOM tests, build and real signed-out process probes only.
- Author file-level understanding: [FILE_MAP](FILE_MAP.md), Sections 2-4; human understanding remains pending.

## 2. AI review — complete first

- Execution time / tool or model: Codex assistant, 2026-09-28 America/Toronto; exact review times not retained.
- Files and scope actually read: M1 runtime/transport, adapter/facade interruption, account gateway/forwarding, launcher, frontend panel/store/client, integration tests and linked design/contract. File list in FILE_MAP.
- Commands actually executed and results: TEST_REPORT T-28 onward records final 25 affected backend cases, preceding 89-case regression, five subscription frontend cases, six existing WebSocket ACK cases, frontend build, real Gateway/AgentServer synthetic-provider journey and real login-link creation/cancel. Commands and limitations are not replaced by this summary.
- Coverage: fail-closed authentication, exact cancellation identity, logout generation fencing, fresh profile preservation, event routing and history fixtures. No performance claim.
- Unreviewed areas and limits: actual browser journey and live subscription/model, visual/browser/Chrome107 checks, tools/team/auxiliary/media capability equivalence, whole proposed diff and independent human review.

### Findings

| ID | Severity | File / function / location | Trigger and actual impact | Verifiable evidence | Recommendation | Finding status |
| --- | --- | --- | --- | --- | --- | --- |
| R-01 | Important | agent_adapter/interface.py::_process_interrupt | A stale cancellation rejected by the adapter still reached facade task cancellation | Dedicated facade test in test_codex_integration.py | Return on rejected Codex control before canceling outer task | Fixed in uncommitted M1; regression passed |
| R-02 | Important | codex_subscription/service.py logout and stream cleanup | An old stream's finally block could close the replacement transport after logout | Logout-during-stream fixture | Fence cleanup by process epoch | Fixed in uncommitted M1; regression passed |
| R-03 | Important | test_codex_integration.py history fixture | Initial fixture isolated history but not metadata, creating one synthetic fixture-session metadata directory in the default data root | Inspected sole metadata.json; isolated both roots and reran | Keep fixture writes in temporary roots | Fixed; synthetic directory moved reversibly to local evidence, no pre-existing data removed |
| R-04 | Blocking | M1 session restart / spec AC-07 | Restart invalidates runtime epoch; old thread continuation is refused because pinned account/read lacks durable workspace identity | Restart fixture expects NEW_SESSION_REQUIRED; contract v0.2 | Establish supported identity/recovery before AC-07 acceptance; retain history | Open; owned by Xiaoyang, before acceptance |
| R-05 | Blocking | Browser/live product acceptance and spec AC-01/02/06/08 | Mock tests and signed-out protocol checks do not prove real product operation or whole-project replacement | Startup and real socket fixture journey now pass; actual signed-in model and browser journey still unrun | Complete M005/M006 and capability work before acceptance | Open; AI handles available integration work, Xiaoyang supplies personal sign-in |


| R-06 | Important | codex_start.main | Interactive initializer prompts on startup then fails with EOF when no terminal input is available | T-39 original traceback | Use incremental noninteractive prepare_workspace | Fixed; startup and regression pass |
| R-07 | Important | app_web_handlers forwarding sets | Account RPC reaches AgentServer but Gateway emits METHOD_NOT_FOUND first | T-40 actual socket reproduction | Register account methods as forwarded with no local handler | Fixed; actual status/login/cancel RPC and fixture pass |
| R-08 | Blocking | AgentServer startup and modality warmup | Ordinary startup triggers native API image probes despite subscription selection | T-39 initial startup log; synthetic template request, not user chat | Skip legacy provider probes/alternate catalog and unsupported background startup in M1; retain capability gaps | Fixed for M1 startup; full capability/outbound acceptance remains R-05 |
| R-09 | Important | Gateway cancellation, service.interrupt, frontend interrupt_result | Gateway loses original target ID, announces success early and cancels the stream before terminal/history handling | T-41 real socket fixture; T-44 early-ACK/partial/continuation regression | Preserve target; await provider terminal; preserve partial result; ignore rejected stop in UI | Fixed within tested scope; live model stop still pending |

AI conclusion: Recommend continued implementation and verification first. No whole-project completion or merge recommendation. Passing tests establish only the stated bounded scope.

## 3. Author response and revalidation — required; explain N/A if no findings

| Finding ID | Response or disagreement | Fix commit | Revalidation command / result / evidence | Additional AI review | Human disposition |
| --- | --- | --- | --- | --- | --- |
| R-01/R-02 | Corrected stale-control and cleanup ownership | Uncommitted; M1 manifest | TEST_REPORT final affected backend suite: 20 passed; preceding broad run: 85 passed | Corrected branches and fixtures read | Pending human review |
| R-03 | Flush asynchronous history writes and isolate both metadata/history collaborators | Uncommitted; M1 manifest | Real facade/history fixture passed in final suite; evidence directory m1-test-metadata-isolation | Fixture cleanup and roots inspected | Pending human review |
| R-06-R-09 | Startup/routing/stop fixes applied and reviewed; no spec waiver | Uncommitted journey manifest | T-39-T-46 startup/socket/regression/build evidence | Actual touched call chains inspected | Pending human review |
| R-04/R-05 | Retain explicit limitations and unchecked acceptance; do not weaken spec | N/A: unresolved | No final acceptance evidence | Recorded in contract/report/tasks | Pending; no waiver |

## 4. Code Lead function-level review — human confirmation required

| File / function / call chain | Relationship to approved design | Inputs/outputs / invariants / failure paths | Callers and cross-module impact | Test and performance evidence | Human review opinion |
| --- | --- | --- | --- | --- | --- |
| codex_start -> profile -> application launcher | Fresh first use | Separate marked root; no deletion/import; full startup pending | Existing service launchers | Full startup, profile fixture and --help; new convenience launcher shares this entry point | Pending |
| UI -> codex.auth.* -> service -> App Server transport | Per-user subscription account | No key fallback; scoped login attempt and process ownership | Frontend/web gateway/runtime | DOM and wire tests; real Gateway status/login-link/cancel; real sign-in pending | Pending |
| chat.send -> facade -> Codex adapter -> service -> history | AC-02/03/07 | Session/thread/turn identity; stale interrupt rejected; restart gap explicit | Original chat/history consumers | Actual Gateway/AgentServer sockets with fake provider verify stop/continued chat/history; no live model | Pending |

- Author understanding checked: AI explanations exist in FILE_MAP; Xiaoyang's understanding has not been confirmed.
- Unresolved findings and tradeoffs: R-04/R-05 remain open; shared transport failure can terminate other active streams. No risk acceptance invented.
- Affected module owners' opinions: Xiaoyang coordinates the authorized frontend/backend scope; no other owner's opinion recorded.
- Compliance with approved regression, compatibility, and measured-performance requirements: partial verification only; browser/platform and full acceptance remain pending; no performance measurements.

## 5. Final human decision — required; initially pending

- Decision: **Pending approval**.
- Code Lead or authorized independent reviewer / time and timezone: independent reviewer not assigned; Xiaoyang is author/Lead. No final review time.
- Approval evidence: None for merge. Existing continuation authorizes M1 implementation only.
- Covered implementation C / baseline B / integration result and registered artifact versions: pending final C; B as above; spec v0.2, plan/tasks v0.3, directive v0.9, report v0.8. No final integration result.
- Conditions and owners: resolve blocking findings and required acceptance; Xiaoyang coordinates independent human review and personal account validation.
- Deferred items and follow-up: no formal check deferral or acceptance waiver. Later work remains incomplete, not approved for omission.

## 6. Version check before merge — required

| Check | Current facts and evidence | Effect on original approval | Required action / completion |
| --- | --- | --- | --- |
| Commits and files changed after C | No implementation commit; uncommitted M1 manifest plus documentation; git status/diff inspected | No merge approval exists | Commit and review actual final tree at delivery |
| Current target baseline versus B | Latest fetch this turn matches B | No integration change observed at that fetch | Recheck before delivery |
| Revalidation and additional review | Final affected backend/React/build results and document checks in report | Preserves bounded evidence only | Live/browser/capability verification and independent human review pending |

Merge eligibility at this review time: **No**. Recorder: Codex assistant, 2026-09-28. Live task state is maintained in [CURRENT_STATUS](../../governance/CURRENT_STATUS.md).

Journey review addendum: the user now explicitly authorizes the full bounded journey and has agreed to perform personal sign-in. Login completion is not yet confirmed. Startup and account RPCs were exercised against the actual local preview; synthetic wire tests use an isolated profile and cannot authenticate a real account. The previous manifest is retained for historical checks; current 32-file manifest covers new startup, Gateway, frontend and probe changes. No final human review/merge approval is inferred.
