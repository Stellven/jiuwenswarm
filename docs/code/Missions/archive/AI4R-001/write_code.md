# write_code.md — AI4R-001: Personal Codex subscription runtime

Maintainer and issuer: Xiaoyang, Code Team Lead. Drafted by Codex assistant from existing user instructions.
Template: [WRITE_CODE_TEMPLATE](../../code_sop/templates/WRITE_CODE_TEMPLATE.md).
Revision 0.9 authorizes the presented M1 product milestone: managed subscription login and ordinary chat in the existing frontend/backend. Earlier research authority remains historical. Whole-project acceptance and final delivery remain open.

## 1. Issue and authorization

| Field | Record |
| --- | --- |
| TASK-ID / author / module owner | AI4R-001 / Xiaoyang / affected module owners awaiting confirmation; Xiaoyang coordinates |
| Artifact mode / registered feature directory | Spec Kit / `docs/code/Missions/AI4R-001/` |
| Document revision | 0.9; plan/tasks v0.3 M1 addendum |
| Working branch / integration branch | `ai4r_xiaoyang` / `ai4r_main_branch` |
| Main branch baseline SHA | `dc9e6afdbacdc78a5d2eede3b4ab0dd1347e7483` |
| Approved design version and decision evidence | Plan v0.3 records the presented login/basic-chat milestone authorized by the latest user instruction. Unpresented details are implementation choices, not claimed human review. G1-G3 remain for later features. See [TASK Section 4](TASK.md#4-design-and-implementation-authority--required) for actual existing preparation authority |
| Registered acceptance source / approved work-item scope | Registered spec.md v0.2, AC-01–AC-08; native plan.md/tasks.md v0.3 M1 registered; T001-T033 retain broader gates; M001-M006 are the authorized staged product work. R001-R004 bounded research is authorized; preparation groups are defined in Section 4 below |
| Lead approval of this implementation scope, time, and evidence | R001-R004 research plus M001-M006 login/basic-chat authorized by the latest user continuation in TASK Section 4. Exact message times are not recorded; no version-specific production approval fabricated |
| Related change request | [CR-01](CHANGE_REQUEST-01.md): user-directed fresh-start scope; legacy-data migration removed |

## 2. Required reading

| Material | Actual path / version | Relevant sections for this task |
| --- | --- | --- |
| Root AGENTS and local AGENTS along affected paths | [Root](../../../../AGENTS.md); [web](../../../../jiuwenswarm/channels/web/AGENTS.md); [frontend](../../../../jiuwenswarm/channels/web/frontend/AGENTS.md) | Scope, durable context, existing local conventions, verification |
| TASK register and authoritative AC identifiers | [TASK v0.8](TASK.md); [spec.md v0.2](spec.md) | Artifact registry, decisions, user stories, requirements, AC-01–AC-08 |
| Design, architecture, and ADR | Native plan.md v0.3 contains the authorized M1 addendum; broader architecture/ADR v0.1 remain proposed; [research v0.4](research.md) is investigation only | Trace existing code and identify design decisions; do not infer architecture from module names |
| Provider/consumer contracts | Runtime contract v0.3 defines the implemented M1 subset and labels later proposals; inspect actual and proposed boundaries | Authentication, event/state ownership, tool execution, cancellation, model routing |
| Technical design, ordered work, and file map | Native plan.md/tasks.md v0.3 exist; [research and M1 FILE_MAP](FILE_MAP.md) drafted; production file understanding remains pending; proposed files in plan Section 4 and current evidence in research.md | Establish concrete file/function scope and dependencies during Stage 2 |
| Environment and testing methods | [ENVIRONMENT](../../../governance/ENVIRONMENT.md), [TEST_REPORT v0.8](TEST_REPORT.md), [SOP](../../Code_SOP.md) | Runtime selection, reproducible commands, actual baseline evidence, human gates |
| Existing failures, constraints, and handoff | TEST_REPORT Sections 3 and 6; [CURRENT_STATUS](../../../governance/CURRENT_STATUS.md) | Initial runtime failures, missing subscription validation, capability coverage; no completed handoff |

Active acceptance IDs exclude retired AC-05; follow [CR-01](CHANGE_REQUEST-01.md). The user confirmed spec v0.2 and requested the proposal; plan Section 8 remains the design approval record.

## 3. Goals, permitted scope, and boundaries

- Observable behavior to implement: ultimate behavior is defined only by spec.md v0.2 AC-01–AC-08. Current product scope is login, status/logout, ordinary streamed chat, interruption and history through the existing UI.
- Out of scope: whole-project completion claims before capability evidence; remote force pushes; copied credentials; automatic Git/commit hooks; model turns without a defined validation scenario.
- Paths permitted for addition/modification: root `AGENTS.md`, adopted `.specify/` and `.agents/skills/speckit-*/`, registered `docs/code/Missions/AI4R-001/`, preparation/governance records under `docs/`; project dependencies and build/test output in existing ignored locations. Standalone tool installations remain outside the repository. Production additions/edits for M1 are permitted in common profile/schema, server runtime/agent and gateway adapters, agent_ws_server.py, gateway web handlers, channels/web/frontend, the staged codex_start launcher/Start-Codex.cmd, AgentServer startup and Gateway cancellation routing, and scoped tests. Isolated research scripts may be added under docs/code/Missions/AI4R-001/verification/; temporary profiles/logs go under LOCALAPPDATA/ai4r-tools/evidence/AI4R-001/.
- Interfaces, data, or dependencies that require confirmation before changing: material changes beyond the M1 contract in plan v0.3, such as enabling host tools, alternate providers or migrating old profiles; dependency upgrades require separate evidence.
- Invariants and compatible behavior to preserve: seven SOP principles; one authority for each fact; personal branch mapping; existing user work/data; credential boundaries; honest test evidence and no silently removed capabilities.
- Cross-module owner confirmation: Xiaoyang owns this cross-module milestone as author/Lead under his explicit frontend/backend request; no other person is assigned or claimed to have approved. Independent final review remains required.

## 4. Implementation sequence

Native tasks.md v0.3 owns progress. M001-M006 authorize the login/basic-chat slice; broader T001-T033 remain proposed. The following groups describe already authorized preparation, not a duplicate implementation progress register. Production order/progress belongs only in tasks.md. R001-R004 are the authorized bounded research items in native tasks.md; real login-link creation/cancellation is now verified; actual account sign-in and model execution remain unexecuted. The historical R002 process probe must use a fresh isolated CODEX_HOME and allow only initialization plus read-only account/status protocol operations, with no login, token reads, model turns or application startup.

| Step / authorized native task IDs | Inputs and prerequisites | Files/functions and expected outcome | Verification / stop conditions |
| --- | --- | --- | --- |
| M001-M006: real product slice | User continuation after concrete milestone presentation; plan v0.2 M1 | Backend managed transport/account/session adapter, real frontend account controls and original chat/history integration; exact files in plan addendum | Tests before code; no provider fallback; no secret logging; live account evidence remains required; whole-project completion prohibited |
| Preparation: environment and registry; no native IDs | Existing start, branch-reset, and installation instructions in TASK Section 4 | Adopt pinned tooling, install locked environments, register exact feature, record baseline | Validate versions, scope, branch, local pointer, and baseline checks; retain failures honestly |
| Preparation: template correction; no native IDs | Explicit user template instruction | TASK, this directive, and TEST_REPORT match their source templates | Required sections/fields present; explain N/A and preserve actual pending decisions |
| R001/R002: isolated feasibility verification | User confirmation recorded in TASK Section 4; pinned dependencies and plan v0.1 | Offline tests of real installed harness boundaries and a fresh-home App Server protocol/process probe; scripts under the registered feature verification directory | Record exact commands/results in TEST_REPORT; no credentials, model turns, production edits or remote push; unresolved G1-G4 remain explicit |
| R003/R004: guard prototype and frontend contract | User continuation and frontend/SOP instruction; R001 counterexamples | Isolated approval broker, strict SDK hook check, curated process launch and frontend approval-state fixtures under the feature verification directory | Malformed/stale/cross-session/duplicate decisions fail without provider forwarding; launch lacks fabricated provider secrets; frontend keeps errors and unknown delivery honest. Tests and signed-out smoke only |
| Design investigation and drafting; no production IDs | Registered spec v0.2, constitution, implementation/callers, pinned dependencies | Research and native plan.md, supporting artifacts, then tasks.md; incorporate DESIGN and PLAN template coverage | Resolve capability/protocol questions; identify unresolved blockers and owners; no production implementation before applicable design/directive approval |

## 5. Verification requirements

| AC / risk | Required check | Working directory and exact command | Pass criterion / threshold basis |
| --- | --- | --- | --- |
| Wrong branch / baseline | Verify personal branch and recorded team ref | Repository root: `git status --short --branch`; `git rev-parse HEAD`; `git rev-parse origin/ai4r_main_branch` | Actual branch and baseline match TASK; preserve pending preparation files |
| Wrong Spec Kit feature / leaked selector | Resolve native paths and confirm local ignore | Repository root with ENVIRONMENT selectors: `& ./.specify/scripts/powershell/check-prerequisites.ps1 -PathsOnly -Json`; `git check-ignore .specify/feature.json` | Exact registered paths; selector ignored; no unexpected branch operations |
| Setup regressions, preparatory to AC-01–AC-08 | Relevant unchanged-baseline tests and build | Exact backend and frontend commands in TEST_REPORT Section 3; environments in ENVIRONMENT | Tests actually collected and passed; build succeeds; not acceptance proof |
| Incorrect task records | Template headings/fields, links, English UTF-8, seven-principle comparison | Repository-root documentation inspection described in TEST_REPORT Section 3 | Required template coverage retained, no broken local links, no fabricated approval/results |
| AC-01–AC-08 production acceptance | Design the end-to-end and failure-case verification | M1 offline and signed-out checks are recorded in TEST_REPORT; live account and whole-project scenarios remain unrun | Criteria remain in registered spec v0.2; M1 authorization identifies the staged scope; no whole-project pass follows from it |

- Regression and cross-module checks: baseline evidence in TEST_REPORT; bounded profile/account/facade/history fixtures now run; full startup/socket/browser and signed-in scenarios remain unrun.
- Performance/model/data reproducibility: no performance improvement claim. Real model/data fixtures, repetition methods, and applicable thresholds remain design work before acceptance.
- Missing environment/data and owners: dependencies installed; actual account/protocol feasibility and complete capability fixtures remain unverified. Xiaoyang owns resolution before the affected checks.
- Verification result location: [TEST_REPORT](TEST_REPORT.md); native task progress must not duplicate measured results.

## 6. Stops, changes, and exceptions

If a core contract is missing, a design assumption fails, scope expands materially, criteria must change, or an unauthorized external side effect would occur, record the issue and pause affected implementation. Independent authorized preparation may continue. Use the SOP CHANGE_REQUEST template for material changes; do not lower acceptance requirements unilaterally.

Existing start/install authorization is reusable. Ordinary setup choices do not require another start approval. Record runtime failures and their resolution without weakening tests. Any proposed verification exception must identify risks, actual human decision, follow-up owner/condition, and recovery; none is approved here.

## 7. Required deliverables

- Current milestone: M1 product changes, risk-based tests and template-conformant evidence, in addition to completed preparation.
- Stage 2: native design and supporting research/contracts as applicable, work items with necessary verification, identified blockers, and a concrete version for Lead review.
- Production delivery after the applicable gate: implementation mapped to ACs, necessary tests, final diff, and author file/function explanation.
- Updated authoritative design/work records and SOP checklist; architecture/contracts and file map as affected.
- AI review/finding dispositions, independent human review, PR description, known limitations, recovery, and handoff material at their respective stages.

These later deliverables are obligations, not claims that they exist. Reports reference tested implementation/baseline versions and distinguish subsequent documentation-only updates from changes requiring new verification.

### Subsequent explicit publication authority (2026-09-28)

Xiaoyang accepted the running localhost:5173 demo and requested direct publication to the five team branches and a browser guide. TASK Section 4 records the exact scope. This supersedes earlier pending-delivery statements for this M1 publication only; it does not authorize force pushes, fabricate independent review, or close broader acceptance.
