# Handoff record: AI4R-001

Template: [HANDOFF_TEMPLATE](../../code/code_sop/templates/HANDOFF_TEMPLATE.md). Recorded on 2026-09-28. This handoff covers the accepted M1 browser demo; the full subscription conversion remains open.

## 1. Handoff snapshot — required

- Sender / recipient / time and timezone: Codex assistant for Xiaoyang / Xiaoyang and the four team-branch users / 2026-09-28, America/Toronto; exact acceptance message time was not retained.
- Task goal and approved scope: personal subscription operation of JiuwenSwarm. This delivery is the staged login/basic-chat demo and its SOP/Spec Kit records.
- Live task state: [AI4R-001 in CURRENT_STATUS](../../governance/CURRENT_STATUS.md).
- State at handoff and snapshot time: In progress; user-accepted M1 prepared for direct publication on 2026-09-28. The full task is not Done.
- Risk level and main reasons: High; authentication, session routing and replacement of the model runtime.
- Most important current fact: Xiaoyang accepted localhost:5173 and explicitly instructed publication to the five team branches, with a browser demo guide.
- Receipt confirmation: Xiaoyang's demo acceptance is recorded; other team members have not acknowledged receipt. No messages were sent to them.

## 2. Locations and versions needed to resume — required

| Item | Actual location / identifier |
| --- | --- |
| Repository working directory / remote URL | `D:\research\ai_for_research\jiuwenswarm` / https://github.com/Stellven/jiuwenswarm.git |
| Current working branch / HEAD | `ai4r_xiaoyang`; implementation commit `97c1bd6930497c2a97cedeca82c49b62650b56c8`, followed by documentation-only publication records |
| Target branch / verified baseline B | `ai4r_main_branch` / `dc9e6afdbacdc78a5d2eede3b4ab0dd1347e7483`, fetched on 2026-09-28 before publication |
| Verified implementation C / integration version | `97c1bd6930497c2a97cedeca82c49b62650b56c8`; risk-based post-commit verification in TEST_REPORT |
| Working-tree state | Implementation committed; this handoff and acceptance/evidence updates form a subsequent records-only commit |
| Task registry / artifact mode | [TASK](TASK.md), including the dated publication decision / Spec Kit |
| Acceptance source | [spec.md v0.2](../../../specs/AI4R-001-codex-subscription/spec.md); AC-01–04 and AC-06–08 remain the whole-project criteria; AC-05 retired |
| Technical design and implementation authorization | [plan.md v0.3](../../../specs/AI4R-001-codex-subscription/plan.md), [write_code v0.9](write_code.md), and TASK's explicit demo acceptance/publication decision |
| Global and applicable local rules | [Root AGENTS](../../../AGENTS.md), [web AGENTS](../../../jiuwenswarm/channels/web/AGENTS.md), [frontend AGENTS](../../../jiuwenswarm/channels/web/frontend/AGENTS.md) |
| Ordered work and progress | [tasks.md v0.3](../../../specs/AI4R-001-codex-subscription/tasks.md); M005/M006 evidence boundaries and broader T001–T033 |
| Spec Kit feature context | `specs/AI4R-001-codex-subscription`, rooted at this repository, on `ai4r_xiaoyang`; Specify 1.0.12 and setup evidence in [ENVIRONMENT](../../governance/ENVIRONMENT.md) |
| Verification evidence | [TEST_REPORT](TEST_REPORT.md), especially the publication verification rows |
| AI and human review | [review.md](review.md); user accepts the demo and requests direct push, without an independent/function-level review claim |
| PR / other evidence | No PR: explicit direct-push instruction. Destination refs: `ai4r_main_branch`, `ai4r_xiaoyang`, `ai4r_saurav`, `ai4r_ramika`, `ai4r_muk`. Browser guide: [CODEX_DEMO](../../code/CODEX_DEMO.md) |

## 3. Completed work and author understanding — required

See [FILE_MAP](FILE_MAP.md) and [IMPLEMENTATION_CHECKLIST](IMPLEMENTATION_CHECKLIST.md) for the authoritative function-level inventory.

| File or file group | Completed behavior / responsibility | Related functions and calls | Verification evidence | Limitations |
| --- | --- | --- | --- | --- |
| Subscription backend and adapter | Managed login, text streaming, exact stop routing, ordinary-chat history | service.stream/interrupt, adapter, facade and gateway | TEST_REPORT on C | Tools/teams/media and restart continuation remain incomplete |
| Frontend subscription controls | Login/readiness, model selection, streamed chat and stop integration | CodexSubscriptionPanel, webClient, useWebSocket | Frontend tests/build and Xiaoyang's demo acceptance | No independently recorded browser-case transcript |
| Launcher and guide | Dedicated local profile and reproducible browser startup | codex_start, Start-Codex.cmd, CODEX_DEMO | Launcher/socket evidence and inspected setup instructions | Fresh installation on another person's machine has not been independently executed |
| SOP and Spec Kit | Templates, feature registration, native spec/plan/tasks and evidence | TASK and linked workflow | Document/link checks | Broader design and capability gaps remain explicit |

- Decisions already made and reasons: plan M1 addendum and TASK publication decision.
- Design deviations and authority: direct publication follows Xiaoyang's explicit request, superseding the earlier proposed PR gate for this demo only. No force push or acceptance-scope expansion.
- Function-level review actually completed by the Code Lead: not claimed; acceptance of a running demo is recorded separately from code understanding.

## 4. Reproducible verification — required

| Working directory | Preconditions / environment | Actual command | Actual result | Version and evidence |
| --- | --- | --- | --- | --- |
| Repository root | Python 3.11.3, locked codex/test dependencies | Four-suite pytest command and socket probe in TEST_REPORT publication rows | See exact results there | Implementation C and retained local logs |
| Frontend directory | Node 22.23.3, npm 10.9.9, npm ci dependencies | `npm.cmd run test:codex-subscription`; `npm.cmd run build` | See exact results in TEST_REPORT | Same implementation C |

- Acceptance and performance: Xiaoyang accepted the localhost:5173 demo. No performance benchmark or full AC-08 pass is inferred.
- Changes after C: acceptance, evidence, status and handoff records only; no implementation, configuration, test, contract or spec change.
- Approval applicability: user authorization covers direct publication of the current staged demo. The goal-poll compatibility correction was unit-tested; the running preview was not restarted during sign-in, so no user-observed verification of that specific correction is claimed.

## 5. Remaining work, blockers, and risks — required

| Type | Item and impact | Concrete next action | Owner | Dependency / completion criterion |
| --- | --- | --- | --- | --- |
| To do | Detailed personal-account scenario evidence is not independently recorded | Capture model, streamed result, confirmed stop and refreshed history per M006 | Xiaoyang with AI assistance | Evidence tied to the published implementation; user acceptance is already recorded |
| Risk | Full backend restart/account switch blocks continuation of old runtime bindings | Implement and verify account-scoped restart reconciliation for AC-07; meanwhile create a new chat after restart | Xiaoyang | Isolation and restart scenarios pass |
| To do | Tools, teams, auxiliary tasks, retrieval and media are not equivalent yet | Resume capability inventory and T001–T033 in dependency order | Xiaoyang | Each affected requirement and capability has evidence |
| Human decision | Independent review and personal function understanding not recorded | Arrange these for the broader delivery; do not invent reviewer approval | Xiaoyang | Actual reviewer and covered version recorded |

## 6. Resumption steps and completion criteria — required

1. Read TASK, spec, plan, tasks, write_code and applicable AGENTS; preserve local edits and fetch the current team baseline.
2. To run this demo, follow [CODEX_DEMO](../../code/CODEX_DEMO.md). Use your own local login. No second service copy is needed while localhost:5173 is already running.
3. Restore Spec Kit context in the shell running its commands:

```powershell
$env:SPECIFY_FEATURE_DIRECTORY = 'specs/AI4R-001-codex-subscription'
$env:SPECIFY_FEATURE_NO_PERSIST = '1'
& ./.specify/scripts/powershell/check-prerequisites.ps1 -PathsOnly -Json
```

4. Next development action: complete the explicit M006 evidence record, then resolve the next capability/runtime gap in the existing plan. Do not regenerate the spec or tasks merely to resume.
5. Completion criteria: demo publication is a bounded delivery. Whole-task Done still requires the active spec criteria, remaining capability evidence, applicable review and final integration checks.

- Details the recipient should not need to guess: startup/build commands, profile directory, default ports, personal sign-in and restart behavior are all in CODEX_DEMO.
- Human decisions still needed and reasons: later capability tradeoffs and broader final review; no repeated approval is required for this explicitly authorized demo push.

### Confirmed publication

Atomic fast-forward push succeeded for all five destination branches at `295470d6d9f07cc3d81fe674e118abd453405ef1`. A subsequent `git ls-remote --heads origin ai4r_main_branch ai4r_xiaoyang ai4r_saurav ai4r_ramika ai4r_muk` returned that identical SHA for every branch. The existing local Web UI returned HTTP 200. This follow-up updates publication records only; implementation C is unchanged. No PR, force push, remote history deletion, credential upload or message to another person was performed.
