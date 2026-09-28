# AI4R-001 — Run JiuwenSwarm through a personal Codex subscription

Version: 0.8 | Updated: 2026-09-28 | Maintainer: Xiaoyang
Template: [TASK_TEMPLATE](../../code/code_sop/templates/TASK_TEMPLATE.md). This revision registers the user-confirmed requirements and the M1 product implementation scope and evidence.

## 1. Task entry points — required

| Field | Record |
| --- | --- |
| TASK-ID / author / module owner | AI4R-001 / Xiaoyang / affected module ownership not yet confirmed; Xiaoyang coordinates confirmation before cross-module implementation |
| Code Lead / independent human reviewer | Xiaoyang / unassigned; an authorized independent reviewer is required before final review because the Lead is also the author |
| Live task status | [AI4R-001 row in CURRENT_STATUS](../../governance/CURRENT_STATUS.md); current task state is maintained only there |
| Workflow path and rationale | High risk — frontend/backend interfaces, authentication, model execution, fresh-profile initialization, and capability compatibility |
| Artifact mode | Spec Kit, explicitly requested by Xiaoyang |
| Feature directory and branch mapping | `specs/AI4R-001-codex-subscription/` on `ai4r_xiaoyang`; the feature folder is independent of the Git branch |
| Tooling version and setup evidence | Specify CLI 1.0.12, source `e77daa9021d20db26b878f7dfa5640fe5a42d04e`; Codex/PowerShell integration; [ENVIRONMENT](../../governance/ENVIRONMENT.md), [setup metadata](../../governance/SPEC_KIT_SETUP.json), [TEST_REPORT](TEST_REPORT.md) |
| Manual fallback decision, if required | N/A — tooling is installed and Xiaoyang explicitly selected Spec Kit; team-wide default adoption/pilot is not declared complete |
| Affected modules / code paths | Existing `jiuwenswarm/common/config_panel/`, `common/model_config_validation.py`, `common/external_cli_catalog.py`, `common/external_cli_runtime.py`, `server/runtime/agent_adapter/`, `server/control/config_service.py`, `agents/swarm/assembly.py`, `symphony/llm.py`, `channels/web/frontend/src/`, resources, packaging, and relevant tests; shortened paths share the `jiuwenswarm/` prefix. Exact proposed additions await design; see [research](../../../specs/AI4R-001-codex-subscription/research.md) |
| Working branch / team-main baseline | `ai4r_xiaoyang`, tracking `origin/ai4r_xiaoyang` / `origin/ai4r_main_branch` at `dc9e6afdbacdc78a5d2eede3b4ab0dd1347e7483`; origin is Stellven/jiuwenswarm |
| Prerequisite tasks / external dependencies | No predecessor task registered. Locked application dependencies installed. Xiaoyang owns resolution of Codex App Server coverage/protocol compatibility and personal-account validation before affected implementation/acceptance |
| Applicable AGENTS | [Root AGENTS](../../../AGENTS.md), [web AGENTS](../../../jiuwenswarm/channels/web/AGENTS.md), [frontend AGENTS](../../../jiuwenswarm/channels/web/frontend/AGENTS.md); inspect further subtree instructions before expanding edits |

### Register the authoritative artifacts

| Information | Actual source and version |
| --- | --- |
| Requirements, scope, non-goals, and AC identifiers | [spec.md](../../../specs/AI4R-001-codex-subscription/spec.md), v0.2 |
| Technical design | [plan.md](../../../specs/AI4R-001-codex-subscription/plan.md), v0.3 M1 addendum; [research.md](../../../specs/AI4R-001-codex-subscription/research.md), v0.4; G1-G4 unresolved |
| Ordered work, dependencies, and progress | [tasks.md](../../../specs/AI4R-001-codex-subscription/tasks.md), v0.3; broader T001-T033 remain gated; M001-M006 track the staged product slice |
| Human implementation authorization | [write_code.md](write_code.md), v0.9; existing preparation authority is recorded in Section 4 below; M001-M006 login/basic-chat authorized; whole-project gates remain |
| File understanding and SOP gates | Initial static inventory in research.md; [research and M1 FILE_MAP](FILE_MAP.md) drafted; whole-project file understanding remains pending; [implementation checklist](IMPLEMENTATION_CHECKLIST.md) records current gates. Xiaoyang must complete applicable records before implementation/formal review; no completed gate implied |
| Verification and review evidence | [TEST_REPORT.md](TEST_REPORT.md), v0.8; [specification checklist](../../../specs/AI4R-001-codex-subscription/checklists/requirements.md). M1 self-review and remaining gates in [review.md](review.md); independent final review pending |

## 2. Problem, goal, and non-goals — required

- Problem and source: [spec.md v0.2, Input and User Scenarios & Testing](../../../specs/AI4R-001-codex-subscription/spec.md#user-scenarios--testing); current implementation evidence is in research.md.
- Target behavior: [spec.md v0.2, User Scenarios & Testing](../../../specs/AI4R-001-codex-subscription/spec.md#user-scenarios--testing).
- In scope: [spec.md v0.2, Functional Requirements](../../../specs/AI4R-001-codex-subscription/spec.md#functional-requirements).
- Non-goals: [spec.md v0.2, Assumptions](../../../specs/AI4R-001-codex-subscription/spec.md#assumptions).
- Known risks and assumptions: requirement assumptions remain in that specification. Coordination risks: module confirmations and independent final reviewer are unresolved; Xiaoyang owns assignment before their respective gates.

## 3. Acceptance criteria — required; one authoritative source

The sole acceptance source is [spec.md v0.2, Success Criteria](../../../specs/AI4R-001-codex-subscription/spec.md#success-criteria), AC-01 through AC-08, with SC-001 through SC-004. Xiaoyang confirmed spec v0.2 before requesting the design. No separate acceptance table is maintained here.

Design, work items, tests, and review must reference those identifiers. Performance methods and any additional thresholds must be established during design before implementation; preparation tests do not satisfy subscription acceptance.

## 4. Design and implementation authority — required

- Requirements source and version: registered spec.md v0.2.
- Technical design: [native plan.md v0.3](../../../specs/AI4R-001-codex-subscription/plan.md) includes the authorized M1 addendum; broader design gates remain.
- Implementation directive: [write_code.md](write_code.md), v0.9; current scope includes the M1 real-product login/basic-chat milestone.

| Approved object and version | Code Lead / authorized delegate | Decision | Time and timezone | Explicit decision evidence and conditions |
| --- | --- | --- | --- | --- |
| Task initiation, author/Lead assignment, Spec Kit selection | Xiaoyang | Authorized | 2026-09-28, America/Toronto; exact message time not recorded | Current conversation: user identifies Xiaoyang, themselves as Lead, task start, Spec Kit, and their approval of starting |
| Product objective and deployment constraint | Xiaoyang | Authorized objective | Same conversation/date; exact time not recorded | User requires Codex App Server and subscription operation replacing model-provider API keys; clarification confirms each person runs locally and signs in independently. This does not approve an unwritten technical design |
| Local branch alignment | Xiaoyang | Authorized and performed | Same conversation/date; exact time not recorded | User explicitly requests personal branch force-alignment with team main; applies to that local reset, not remote force push |
| Missing tooling/dependencies and baseline setup | Xiaoyang | Authorized | Same conversation/date; exact time not recorded | User explicitly requests installation if missing; covers isolated tooling, locked dependencies, and compatible runtime verification |
| Template conformance | Xiaoyang | Required | Current conversation; exact time not recorded | User requires strict use of each card's template; this revision preserves its sections and mandatory fields |
| Native design, production work-item IDs, and implementation directive covering those versions | Xiaoyang | Pending approval | Pending | Historical broader design gate; plan/tasks now v0.3 with separately authorized M1 addendum. The design decision record is plan Section 8; no blanket whole-project approval |
| Spec v0.2 and design preparation | Xiaoyang | Requirements confirmed; design drafting requested | Current conversation; exact time not recorded | User said the current spec is good and asked what comes next, then explicitly requested writing the proposal. Does not approve future design or production code |
| Presented scope, approach and gap-handling summary | Xiaoyang | Confirmed only as presented | Current conversation, 2026-09-28 America/Toronto; exact time not retained | User accepted the three-row review table, then clarified that unpresented items are unknown. Confirmation covers local personal accounts/fresh start/no legacy migration/retained functionality; preserving UI, sessions, teams and permissions while replacing model execution; reporting equivalence gaps for a user decision. It is not blanket approval of detailed design, all 33 tasks, verification code or live subscription tests. See plan Section 8 |
| Presented next-step verification 1 and 2 | Xiaoyang | Authorized bounded verification | Current conversation, 2026-09-28 America/Toronto; exact time not retained | After the assistant presented isolated verification code and a separate local App Server smoke test, user said these are good and asked for the next step. Covers R001/R002 in native tasks and write_code v0.6: offline boundary tests plus an isolated signed-out protocol/process check. Personal login/model turns, production conversion and remote delivery remain later stages |
| Isolated guard prototype and frontend contract coverage | Xiaoyang | Authorized continuation | Current conversation, 2026-09-28 America/Toronto; exact time not retained | User requests the presented next step, adds frontend coverage, and explicitly requires plan/SOP adherence. R003/R004 cover isolated guard code, frontend approval-state/contract fixtures, offline tests and a signed-out process recheck. No product integration, personal login/model turn or remote delivery is inferred |
| Product login and ordinary-chat milestone (plan/tasks v0.2 M1; directive v0.8) | Xiaoyang | Authorized staged implementation | 2026-09-28 America/Toronto; exact time not retained | User replies "Execute according to SOP" after the assistant explicitly proposes backend App Server chat, frontend login/stream/errors and login-to-history validation. Includes frontend/backend code and tests; does not waive whole-project capability gaps or fabricate personal login evidence |
| Final implementation verification and merge | Independent reviewer / authorized Lead delegate not yet assigned | Not performed | Pending | No final implementation, formal review, PR, or merge |

This is the authoritative record of the existing conversation decisions; other artifacts reference it. New requirements/design versions need appropriate scope-specific decisions, without re-requesting unchanged start authorization.

Scope update: [CR-01](CHANGE_REQUEST-01.md) records Xiaoyang's explicit fresh-start instruction. Active criteria are AC-01 through AC-04 and AC-06 through AC-08; AC-05 is retired. The user subsequently confirmed spec v0.2 and requested the design; the subsequently presented three-row summary is confirmed, while unpresented technical details remain unreviewed.

| End-to-end M1 continuation | Xiaoyang | Authorized | Current conversation, 2026-09-28; exact time not retained | User explicitly requests SOP execution through open app, own-account login, send/receive, stop and refreshed history. Extends existing M1 execution evidence; no whole-project acceptance or merge approval. Personal sign-in remains user-owned |

### Demo acceptance and publication decision (2026-09-28)

Xiaoyang stated that the localhost:5173 version is accepted and explicitly requested publication to the team main and all four personal branches, together with a browser demo guide. This authorizes direct fast-forward publication of the current M1 demo to `ai4r_main_branch`, `ai4r_xiaoyang`, `ai4r_saurav`, `ai4r_ramika`, and `ai4r_muk`; no force push is authorized. The explicit user direction controls this bounded publication despite the earlier proposed PR/independent-review workflow. No independent review, function-level understanding, or whole-project AC completion is inferred. The previously tested goal-poll correction is also in the source tree; the preview process was not restarted while the user was logging in, so that correction has unit evidence rather than user-observed evidence. Broader requirements remain unchanged.

Browser instructions: [CODEX_DEMO](../../code/CODEX_DEMO.md). Publication evidence and remaining work: [HANDOFF](HANDOFF.md).

## 5. Plan and implementation checklist — required; may reference separate records

[Native plan.md v0.2](../../../specs/AI4R-001-codex-subscription/plan.md) owns technical design; [tasks.md v0.2](../../../specs/AI4R-001-codex-subscription/tasks.md) owns ordered work, dependencies, and progress. Do not create parallel DESIGN or execution-plan documents.

- Author file-level understanding: initial evidence is in research.md; [research and M1 FILE_MAP](FILE_MAP.md) now exists; [implementation checklist](IMPLEMENTATION_CHECKLIST.md) records current gates; broader production file understanding and review remain pending.
- Findings / decisions / remaining work: current technical questions are in research.md. The draft plan and tasks identify G1-G4 and the concrete evidence needed to resolve them. Current task state remains in CURRENT_STATUS.

## 6. Verification record — required; may reference a separate record

See [TEST_REPORT.md v0.8](TEST_REPORT.md) for tested implementation C, team baseline B, environment, working directories, exact commands, original failures, retained logs, and missing checks. This high-risk task keeps results there rather than duplicating them here. Uncommitted scaffold/document validation is work-in-progress evidence.

## 7. Review and delivery entry points — required

- AI and human review: [M1 self-review](review.md) records findings and pending final gates, following [REVIEW_TEMPLATE](../../code/code_sop/templates/REVIEW_TEMPLATE.md). No review approval is implied.
- PR: not created; intended base: `ai4r_main_branch`.
- Handoff: [HANDOFF](HANDOFF.md) records the accepted demo, publication evidence, recipients and remaining work.
- Post-merge verification and state update: no merge SHA or post-merge evidence exists. The CURRENT_STATUS row remains authoritative; do not mark Done before required review, integration checks, and handoff.
