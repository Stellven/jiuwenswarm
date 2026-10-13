# Implementation Plan: Personal Codex Subscription Runtime

**Branch**: `ai4r_xiaoyang` | **Date**: 2026-09-28 | **Spec**: [spec.md v0.2](spec.md)
**Version / status**: 0.3 / M1 login/basic-chat implementation authorized; whole-project delivery remains gated by G1–G4.
**Input**: User-confirmed spec v0.2; fresh first use, personal local accounts, no legacy-data migration. Requirements confirmation is not design approval.

## Summary

Introduce a subscription-only execution boundary in the local backend, using the locked Codex App Server runtime. Reuse OpenJiuwen's CodexHarness and HarnessIOAdapter for conversational agent runs, preserve Jiuwen's application sessions, scheduler, team coordination and tool authorization, and replace the existing direct account-auth/catalog path with App Server account operations.

This is a concrete proposed architecture, not a claim of complete feasibility. The main/supervisor adapter needs a compatibility proof; embeddings, media and several specialist pipelines have no demonstrated subscription equivalent. They remain required by AC-08 and block whole-project delivery. A successful chat demo does not close those gaps. See the authoritative capability inventory in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.11.3 verified locally; repository range >=3.11,<3.14. TypeScript/React; Node 22.23.3/npm 10.9.9 selected for checks.
**Primary Dependencies**: OpenJiuwen 0.1.18 at 9e3390195a9ea15235b2b5f7412cb2aa440622cc; openai-codex and packaged CLI 0.144.4; existing application transport and Vite. No upgrade proposed merely to match IDE Codex 0.155.
**Storage**: Existing Jiuwen session/project persistence in a separate new data root; App Server thread/checkpoint state in a dedicated Codex home; credentials remain owned by Codex.
**Testing**: pytest, existing frontend Node tests and TypeScript/Vite build; proposed fake-App-Server protocol tests and explicit live local-account scenarios.
**Target Platform**: Windows local application/web first; Chrome 107 UI baseline. Existing desktop/CLI/ACP and other supported OS paths remain inventory obligations, not implicitly dropped.
**Project Type**: Existing local application with separate web/gateway/agent-server processes.
**Performance Goals**: No improvement claim or invented acceptance threshold. Measure first-token/total duration, cancellation latency, queueing and memory on matched fixtures; agree quantitative budgets before final performance acceptance if relevant.
**Constraints**: No model-provider keys, external-provider fallback, token copying, legacy import, or destructive profile reset. Whole-project coverage required.
**Scale/Scope**: One person's local installation/account, multiple conversations and team members. Start with bounded run admission; choose resource limits from G1 measurements rather than assuming unbounded App Server processes.

## Constitution Check

Before research: preparation/design explicitly authorized; personal branch and baseline identified; native artifacts are authoritative; no optional hooks installed.
After drafting: seven principles retained; native/SOP mapping below completed; requirements approval recorded; no application implementation or human design approval fabricated. Production work remains gated.

| Gate | Current result | Resolution / owner |
| --- | --- | --- |
| Scope, template conformance and artifact authority | Pass for design drafting | Maintain native plan/tasks and template mapping; Xiaoyang |
| Lead design/directive approval | Pending | Review specific plan/contract/ADR/tasks versions after gaps are resolved or an explicit bounded research scope is approved |
| G1: main agent and team-leader harness parity | Unproven | Prove tool ownership, rail/budget/memory/permission behavior and all interaction modes at the real adapter seam; Xiaoyang |
| G2: auxiliary model callers | Unproven | Prove text/JSON and required tool-call semantics without a generic API-client substitution assumption; Xiaoyang |
| G3: embeddings/media/search/specialist capability coverage | Blocking gap | Establish key-free equivalents and evidence or obtain an explicit scope change; Xiaoyang |
| G4: account/process/approval isolation | Unproven | Verify pinned runtime, sanitized launch, fail-closed approvals, logout races and concurrency; Xiaoyang |

The native plan workflow cannot be declared fully ready while these research gates remain open. The documents below are reviewable proposals with explicit dependent work, not a completed feasibility verdict.

## Project Structure

### Documentation (this feature)

```text
docs/code/Missions/AI4R-001/
  spec.md                 # approved requirements v0.2; AC-05 retired
  plan.md                 # technical design authority
  research.md             # code evidence, capability inventory, decisions
  data-model.md           # proposed entities and lifecycle
  contracts/runtime.md    # draft application/runtime boundary
  quickstart.md           # validation instructions, not executed acceptance
  tasks.md                # sole ordered work/progress record
```

Shared context: [architecture overview](https://github.com/Stellven/jiuwenswarm/blob/343a77dbd5e6dcd18de2e57794cc992d36c2f35c/docs/architecture/OVERVIEW.md), [proposed ADR](../../../adr/0001-codex-subscription-runtime.md), [TASK](TASK.md). Existing aspirational Capsule/M1 diagrams remain separate planning material; this change does not declare them implemented.

### Source Code (repository root)

```text
jiuwenswarm/
  common/                    # configuration, profile, CLI packaging
  gateway/channel_manager/web/
  server/runtime/agent_adapter/
  agents/swarm/
  symphony/
  channels/web/frontend/src/
tests/unit_tests/
```

**Structure Decision**: Add a backend `jiuwenswarm/server/runtime/codex_subscription/` package and a thin adapter at the existing adapter factory. Reuse the application's web/session layers. Do not replace the entire gateway or treat App Server as an OpenAI-compatible HTTP completion endpoint.

## Complexity Tracking

No approved principle exception. Additional account coordination and capability gates are required by the existing process boundary and whole-project objective. Do not add a competing orchestration loop or generic model-client bridge unless G1/G2 demonstrates it is necessary and the design is revised.

## 1. Design control — required

| Field | Record |
| --- | --- |
| TASK-ID | AI4R-001 |
| Author / module owner / Code Lead | Xiaoyang with AI drafting support / assignments not confirmed; Xiaoyang coordinates / Xiaoyang |
| Design version | 0.1 |
| Design status | Draft; readiness blockers G1–G4 |
| Code baseline | ai4r_main_branch at dc9e6afdbacdc78a5d2eede3b4ab0dd1347e7483 |
| Task register and artifact mode | docs/code/Missions/AI4R-001/TASK.md; Spec Kit |
| Requirements source and version | spec.md v0.2; active AC-01–04 and AC-06–08 |
| Implementation directive | docs/code/Missions/AI4R-001/write_code.md; preparation/design authority only |
| Ordered work and progress | tasks.md v0.1 |
| Related architecture / contracts / ADRs | OVERVIEW v0.1, feature contracts/runtime.md v0.1 and ADR-0001 v0.1; all proposals, no new shared contract effective yet |

## 2. Problem and scope — required

- Current behavior and evidence: frontend account mode calls OpenAIAccountAuthManager directly; main agent uses Model/DeepAgent; CodexHarness is available for external members; background/Symphony/media have additional model paths. Exact symbols and coverage are in research.md.
- Target behavior: spec v0.2 User Stories 1–3 and active ACs, with all model work routed through the chosen subscription architecture.
- In scope: real consumer inventory, frontend sign-in/settings, local runtime/auth, main/code/team/background execution, auxiliary LLM consumers, session/interaction mapping, packaging and verification.
- Out of scope: legacy import and migration records (CR-01), shared-account hosting, unrelated Capsule roadmap implementation. Unsupported capability rows are gaps, not exclusions.
- Known constraints: runtime/SDK versions must match; individual subscription availability and capabilities require real verification. New-profile isolation must precede path caching.

## 3. Acceptance-to-design mapping — required

| Registered acceptance ID / section | Design mechanism / section | Verification method / test location | Relevant boundaries and failure paths |
| --- | --- | --- | --- |
| AC-01 / spec Success Criteria | §4 account service and fresh profile | Proposed tests/unit_tests/common/test_codex_profile.py and gateway/test_codex_subscription_handlers.py; quickstart Q1 | Signed out, interrupted login, restart, stale login completion |
| AC-02 | §4 session adapter/event mapping | Proposed runtime/test_codex_session_adapter.py plus existing frontend streaming suites; Q2 | Partial output vs terminal state, duplicate events |
| AC-03 | §4 tools/approvals/control | Proposed runtime/test_codex_tool_bridge.py and session adapter tests; Q3 | Denial, stale decision, cancel during tool effect, steering |
| AC-04 | §4 typed errors/lifecycle | Proposed runtime/test_codex_lifecycle.py; Q4 | Auth/quota/network/runtime failure; no replay after ambiguous effects |
| AC-06 | §4 subscription policy/launch/redaction | Proposed runtime/test_codex_subscription_policy.py; Q1/Q4/Q6 | Ambient keys, custom provider overrides, raw account/WS logs |
| AC-07 | §4 identity/persistence | Session adapter tests; existing session-input/history tests; Q5 | Two simultaneous sessions, account switch, process restart |
| AC-08 | research capability inventory plus G1–G4 | Per-row fixtures/evidence in TEST_REPORT; Q6 | Any unresolved or unsupported row blocks completion |
| AC-05 | Retired by CR-01 | N/A; no migration test | Preserve new-profile data; no legacy import |

Performance method: fixed public fixture set, identical code/config/hardware and model selection, one warm-up and at least five measured runs per representative task; record individual samples and median/range, and separate startup from model duration. Compare account quota/network conditions explicitly. Do not label subscription token usage as API spend. Measurement budgets require Lead agreement if they become acceptance criteria.

## 4. Proposed approach — required

### Entry points and current flow

Frontend `useWebSocket.sendMessage` sends `chat.send`; `web_connect.py` forwards it into the gateway. `app_web_handlers._chat_send` is an acknowledgment handler, not the execution owner. `agent_adapters.create_adapter` chooses `JiuWenSwarmDeepAdapter` or the code adapter. The current deep path constructs a Model and DeepAgent; team assembly and Symphony introduce additional calls.

### Main flow and component ownership

1. **Fresh profile bootstrap.** Select an absolute AI4R data directory before importing/caching workspace paths, using the existing JIUWENSWARM_DATA_DIR mechanism. Default proposed sibling: `~/.jiuwenswarm-ai4r`. Seed missing defaults only; reuse this same root on later starts. Put an application-owned Codex home beneath it. Do not inspect/import old profile data or call initialization with force/overwrite.
2. **Subscription account service.** Agent-server process owns an account control client, catalog and account-generation counter. Gateway delegates account operations to that owner through the existing control-service architecture. Browser gets sanitized status and short-lived login instructions, never refresh/access tokens or raw auth files. Default login is App Server managed ChatGPT browser login; device-code login is supported only when runtime/account permits it. App authentication remains separate.
3. **Run admission.** Reject key/provider/base-URL configuration at all operational entry points, including direct backend callers. Read the live catalog; validate model/reasoning selection instead of hardcoding an IDE model. Ready requires a healthy compatible process, ChatGPT auth mode and usable catalog; it does not promise remaining quota.
4. **Session runtime.** Add CodexSessionAdapter implementing the existing application AgentAdapter boundary. Reuse CodexHarness + HarnessIOAdapter behind a checked wrapper. Map each profile/account-generation/session/agent instance to its own thread; one active turn per binding. Maintain independent application execution IDs and transport ACKs. Publish existing app event envelopes, preserving session/agent/turn identity.
5. **Host tools.** Expose existing authorized Jiuwen tools to the harness through a session-scoped local MCP bridge. Tool arguments never establish session authority; server context determines session/workspace/permissions. Keep one executor for each logical tool. Do not register overlapping native/host tool names with ambiguous ownership. Prove equivalent authorization and side effects before enabling a tool. Existing direct internal tools are not automatically compatible with MCP.
6. **Team and background operation.** Keep Jiuwen team membership, scheduling and message routing. Replace leader and worker execution only after G1 proves the MemberRuntime seam and restored rail behavior. Cron/heartbeat background work uses the same admission policy; signed-out work becomes visibly blocked and never opens interactive login automatically. Preserve scheduler run IDs in the session binding.
7. **Auxiliary text/JSON calls.** Add a narrow CodexTextService for proven one-shot text/structured-output consumers, including suitable Symphony calls. Use an isolated ephemeral thread, explicit output schema when required, no host tools and verified restrictions on built-in tools/network/files. Do not claim a generic Model.invoke replacement: callers expecting a tool-call/ToolMessage loop need separate parity proof or a native-runtime redesign.
8. **Terminal output and persistence.** Application owns project/history and event ordering; Codex owns its thread history. Persist thread/checkpoint identity atomically with application execution state. A process crash does not automatically replay a potentially side-effecting turn. Reconcile with thread state and report interruption/unknown delivery when it cannot be proven.

### Authentication and policy details

- Pin the packaged executable explicitly. Validate supported methods against generated 0.144.4 schema. The SDK and harness expose external endpoints and fallback_model: application policy rejects them, including nested config overrides.
- Dedicated CODEX_HOME uses `forced_login_method="chatgpt"`; reject non-ChatGPT account modes and custom modelProvider values. Disallow automatic model fallback; an unavailable selected model produces a selectable error.
- Child launch must use a sanitized environment and controlled config. The SDK currently starts from os.environ and merges overrides, so harness `inherit_process_env=False` alone does not prove isolation. A tested application launcher/transport wrapper must remove model credentials and unintended provider overrides; never edit installed site-packages.
- Account mutation is serialized. Logout first closes admission and invalidates the generation, cancels pending login, interrupts/waits for active runs and pending interactions, closes run clients, then logs out. Late callbacks cannot restore readiness. Switching account does not resume another account's threads.
- Redact short-lived login codes/URLs as well as tokens from frontend dev WS logging and backend logs. Only the initiating UI sees login material; no broadcast, analytics or persisted store.
- Preserve normal browser/OS login; do not copy IDE auth tokens into the application profile.

### Bounded prototype evidence and frontend boundary

R003/R004 (TASK decision record) implement research-only approval guards, direct process launch and a headless frontend controller. TEST_REPORT T-24-T-26 establishes their narrow behavior. Each permission decision carries an opaque single-use ticket plus session_id, execution_id, thread_id, turn_id, generation, request_id, call_id and an exact boolean approved. Approval messages never share the ordinary chat input path. Gateway caller authorization and production RPC binding are still required; possession of a JSON payload alone is not application authentication.

Frontend submission disables both actions until a matching acknowledgment arrives. Stale responses expire the request; ambiguous delivery requires reconciliation rather than automatic resend. Session/account changes invalidate older callbacks. The eventual UI must queue multiple approvals and render bilingual states using existing components/test IDs. Headless controller results do not satisfy the browser/settings/history/streaming checks in tasks.md. The prototype's direct launcher is not yet connected to the full SDK/harness lifecycle.

### Failure paths, controls and invariants

Control requests carry session, execution and target operation IDs. Reject stale cancel/approval with a conflict response; never apply them to the latest unrelated turn. Permission answers resolve once and require an explicit boolean decision; empty/malformed payloads fail closed. Reject stale replies before HarnessIOAdapter.send, which otherwise converts unmatched interaction replies into provider input. R001 reproduced both behaviors; these are product adapter requirements, not implemented fixes. The pinned Codex harness does not advertise PAUSE_RESUME; its adapter rejects that unsupported capability. Proposed application pause/resume must instead interrupt, reconcile and explicitly resume persisted context, subject to G1 equivalence tests and an honest UI description; do not call it suspended computation or existing harness support.

Persist the account generation atomically with a profile-local opaque account fingerprint, never credentials. Before admitting or resuming work after startup, reconcile managed account/read with that record. A verified identity match preserves the generation; a changed or unprovable identity blocks old-thread resume, advances the durable generation and requires an explicit new binding. Never infer identity from a model name or reset the generation counter on restart. G4 must prove the pinned account metadata can support this comparison without copying raw auth files; otherwise this is an unresolved release blocker. Preserve application history even when its previous runtime binding cannot resume.

Proposed local control timeouts: 30 seconds per ordinary RPC, 60 seconds startup, 180 seconds inactivity excluding an explicit wait for a user decision. At most one reconnect attempt before a turn is accepted; after acceptance/side effects, reconcile instead of blind replay. These are operational defaults for validation, not measured performance promises.

Do not use the upstream automatic approval defaults. Check that the expected approval handler is installed; unsupported SDK hooks must fail startup. Unexpected server requests fail closed. Code tools remain inside selected workspace permissions. Shutdown closes MCP endpoints, streams and processes; a timed-out interrupt is shown as unconfirmed and its worker process is stopped before another run is admitted for that binding.

Invariants: no API fallback; no cross-session routing; one active turn per binding; no duplicate host tool execution; no full-message credential logging; no data-root deletion; no silent capability loss.

### Affected boundaries

| Component / module | Proposed change | Provided / consumed interface | Affected callers | Owner |
| --- | --- | --- | --- | --- |
| Profile/config | Subscription-only defaults and isolated data root | Existing utils/config + proposed profile helper | All launchers, settings, runtime | Xiaoyang; module confirmation pending |
| Account/control | Managed login, catalog and run admission | Draft runtime contract | Gateway/frontend/runtime workers | Xiaoyang |
| Main/code runtime | Codex session adapter | AgentAdapter ↔ HarnessIOAdapter | Agent server, chat, code mode | Xiaoyang |
| Team/scheduler | Native-runtime leader/workers, same policy | MemberRuntime and existing scheduling APIs | Swarm, cron, heartbeat | Xiaoyang; G1 |
| Auxiliary model services | Narrow text/JSON port | Existing Symphony consumers ↔ App Server | Router/evaluation/background callers | Xiaoyang; G2 |
| Frontend | Subscription onboarding/settings, preserved events | Existing chat WS + new codex RPCs | Chat/session/settings UI | Xiaoyang |

### Files and dependencies — required

All added paths are proposed; exact final changes must be reflected in FILE_MAP before formal review.

| File / directory | Add / modify / delete | Responsibility and proposed change | Dependencies / callers | Related AC |
| --- | --- | --- | --- | --- |
| jiuwenswarm/common/codex_profile.py | Add | Select/validate new profile before path caching | utils.py, launcher entry points | AC-01/06/07 |
| jiuwenswarm/common/utils.py; jiuwenswarm/init_workspace.py; jiuwenswarm/start_services.py | Modify | Non-destructive initial defaults and stable data-root propagation | CLI/desktop/web startup | AC-01/07 |
| jiuwenswarm/server/runtime/codex_subscription/ | Add | policy.py, service.py, session.py, tools.py, text.py for the defined boundaries | Pinned SDK/harness, control service | All active |
| jiuwenswarm/server/runtime/agent_adapter/interface_codex.py; agent_adapters.py | Add / modify | Implement/select Codex adapter; prohibit old-provider default/fallback | Existing AgentAdapter contract | AC-02/03/06/07 |
| jiuwenswarm/server/runtime/agent_adapter/interface_deep.py; interface_code.py; team_helpers.py | Modify scoped extraction/callers | Preserve required host rails/tools; remove reachable direct model paths for this distribution | G1 parity evidence | AC-03/08 |
| jiuwenswarm/agents/swarm/assembly.py; server/agent_ws_server.py; symphony/llm.py | Modify | Team/scheduled/auxiliary calls use the new boundary | G1/G2; existing scheduler/team state | AC-06/08 |
| jiuwenswarm/server/control/config_service.py; gateway/channel_manager/web/app_web_handlers.py | Modify | Route sanitized codex account RPC; reject provider-key config | Runtime service, existing gateway auth | AC-01/04/06 |
| jiuwenswarm/common/config_panel/models_handlers.py; model_config_validation.py; resources/ | Modify | Subscription model settings/defaults and readiness | Catalog/policy; no fake keys | AC-01/06 |
| jiuwenswarm/channels/web/frontend/src/features/settings/{services,modules/models}/; features/modelSetupGuide/; App.tsx | Modify | New subscription controller and first-use flow | Draft runtime contract | AC-01/04/06 |
| jiuwenswarm/channels/web/frontend/src/{hooks/useWebSocket.ts,services/webClient.ts,stores/chatStore.ts,stores/sessionStore.ts} | Modify as required | Preserve identity/ACKs; handle typed state; redact auth traffic | Session adapter | AC-02/03/04/07 |
| pyproject.toml; packaging/launch resources as discovered | Modify only after dependency decision | Ship codex extra and exact binary consistently | Locked versions; platform checks | AC-01/08 |
| tests/unit_tests/{common,gateway,runtime}/test_codex_*.py; frontend/tests/ | Add/modify | Protocol, policy, lifecycle, UI and isolation fixtures | Contract, quickstart | All active |

Embedding/media/specialist paths are identified in research.md; concrete replacement edits depend on G3. Do not mark that work covered by this file table.

### M1 implementation addendum (v0.2)

Xiaoyang authorized the presented real-product subscription login and ordinary-chat milestone by replying "Execute according to SOP" after that specific next step. This is staged delivery under spec v0.2, not removal of teams/tools/media or approval of whole-project completion. Unchecked requirements checklist entries stay unchanged. G1-G3 still gate their affected features; M1 provides a narrow G4 integration proof.

Use the existing AgentAdapter seam, Gateway forwarding/authentication, chat events and application history. A small owned stdio JSON-RPC transport replaces the unsafe inherited-environment SDK launch for this milestone; it uses the pinned packaged 0.144.4 executable and generated protocol schema, without altering installed dependencies. Chat runs in a dedicated empty read-only workspace with shell, web search and external tools disabled; unexpected server requests fail closed. No host tool or team parity is claimed. Unsupported modes fail explicitly.

Provide an explicit `python -m jiuwenswarm.codex_start` staged launcher that selects `codex_subscription` and a fresh profile before importing the application. It never reads/copies the old profile and never deletes a data root. The existing legacy launcher remains during development; this is not the final distribution/default conversion or AC-06/AC-08 completion.

A per-profile OS file lock prevents two runtime owners. The current pinned account/read response has no workspace/account identifier, so persisted threads cannot be safely resumed across process restarts or explicit account changes: M1 preserves application history but requires a new conversation. This is an explicit AC-07 gap to resolve, not a waived acceptance criterion. A transport failure ends active streams and invalidates their bindings; it never replays a turn.

The backend owns managed ChatGPT sign-in, cancellation, status, logout, models, thread bindings, one turn per session, transport failure, and interruption. Account changes cannot resume older bindings. Chat uses existing `chat.delta`, `chat.final`, and `chat.error` envelopes. The frontend adds a bilingual subscription panel to the original chat page, handles pending/error/disconnected states, and suppresses API-key setup for this launcher. Logs exclude account/login payloads. Verification includes subprocess isolation, protocol/session failure fixtures, facade/history routing, frontend interaction tests/build, signed-out runtime smoke, and live personal-account validation when Xiaoyang is available.

### M1 integration refinements (v0.3)

- The UI polls goal status even during ordinary chat. M1 returns an empty goal snapshot for read-only polling and rejects goal mutations without calling the provider; this does not implement goal execution.

- The explicit subscription launcher seeds missing files noninteractively with overwrite=False. Start-Codex.cmd provides a Windows entry point. The old installation is preserved.
- Real startup exposed legacy API modality probing. Subscription startup now skips native model probes, alternate catalogs and unsupported background/asset/MCP/personal-context startup. These are visible M1 gaps, not completed replacements. Ordinary chat/session/history services remain active.
- Account RPCs belong to both Gateway forwarding sets, preventing a premature local METHOD_NOT_FOUND response after dispatch.
- Cancellation retains the exact original chat request ID through Gateway, awaits the matching provider terminal event (including an early stop before start acknowledgment), and persists partial text. Rejected stale cancellation does not stop the current frontend stream. Confirmed cancellation allows another turn on the same runtime thread.
- The subscription panel owns model selection; the old chat model selector is hidden in this mode. Full legacy Settings replacement remains later work.
- Real Gateway/AgentServer socket fixtures cover synthetic login, streaming, stale/valid cancellation, continuation and history after reconnect. They substitute only the model/auth transport in a dedicated test child/profile and do not establish live subscription or browser acceptance.
- Current actual-model acceptance is the user-requested local journey with a short harmless chat followed by a deliberately long reply to stop. User completes personal sign-in; no credential values are requested or copied.

## 5. Contracts, compatibility, and data — conditional

- Interface changes: proposed `codex.auth.*` and `codex.models.list` RPCs; existing chat/session envelopes retained. Draft [runtime contract](contracts/runtime.md) defines the boundary. It is not yet an effective shared contract.
- Compatibility strategy: fresh installation defaults to subscription-only. Existing key-based setup and alternate CLI provider execution must be unreachable in the shipped flow. Retaining old source during development is not operational fallback.
- Data/state: [data-model.md](data-model.md). Legacy-data migration N/A under CR-01. New-profile restart/history is required. No forced reinitialization.
- Security/privacy: backend-owned account lifecycle, sanitized process launch and log output, scoped tools and run identities; account changes invalidate old runtime bindings.

## 6. Alternatives and risks — required, scale to complexity

| Alternative | Main benefits | Costs / constraints | Reason selected or rejected |
| --- | --- | --- | --- |
| Relabel existing OpenAIAccount provider | Small UI change | Direct token/HTTP path; additional model-key consumers remain | Rejected: does not meet selected App Server architecture |
| Generic ModelClient wrapping App Server | Preserves DeepAgent callers | Nested tool-loop/pending-turn semantics, tool duplication and cancellation unproven | Not selected; revisit only with a successful explicit bridge proof |
| Native harness at AgentAdapter/MemberRuntime seam + narrow auxiliary port | Reuses actual App Server integration and host session/coordination layers | Rail/team leader parity and specialist coverage require work | Proposed, gated by G1–G4 |
| Rewrite all orchestration inside Codex | One agent runtime | Discards established scheduler/team semantics; much broader regressions | Rejected as initial approach |

| Risk / unresolved question | Impact | Resolution or mitigation | Owner | Condition for starting affected implementation |
| --- | --- | --- | --- | --- |
| G1: native harness skips DeepAgent rails | Permissions, plan mode, budgets, memory/evolution may regress | Explicit rail matrix and leader/main proof; preserve or port each applicable behavior | Xiaoyang | Proof reviewed and design updated |
| G2: auxiliary structured/tool callers | Main chat works while internal services still fail | Consumer-specific contract fixtures and text/JSON/no-tool proof; no hidden Model fallback | Xiaoyang | Every caller assigned a viable port |
| G3: embeddings/media/specialists | Cannot claim entire project works without keys | Resolve each capability row; local replacements would require behavior/quality review; any removal needs user scope change | Xiaoyang | Equivalent solution established or explicit requirements change |
| G4: SDK private hooks and inherited environment | Auto-approval or wrong credential/provider path | Fail-closed wrapper and contaminated-environment/race tests | Xiaoyang | Reproducible proof on pinned versions |
| Multiple processes and account mutations | Logout while workers remain active | Central lifecycle owner, generation fence, IPC cancellation acknowledgments | Xiaoyang | Integration test across gateway/agent-server/workers |
| Existing platform/package paths | Local Windows success overstates portability | Inventory actual shipped launchers; test each intended platform before its support claim | Xiaoyang | Platform-specific evidence or explicit scope decision |

## 7. Verification and delivery plan — required

- AC checks and dependencies: §3 and [quickstart](quickstart.md). Baseline evidence remains in [TEST_REPORT](TEST_REPORT.md); no new subscription test has passed.
- Rollback/recovery: preserve separate profiles. Reverting experimental code never converts credentials/data or automatically re-enables key execution in this product. A failed release stops model work and surfaces a recovery state; any older installation remains separately managed by the user.
- Documents to update: architecture overview, ADR, runtime contract, ENVIRONMENT, FILE_MAP, applicable module AGENTS and SOP checklist; instantiate missing process records from their templates at the relevant stage.
- Completion evidence: TEST_REPORT, future task review.md and HANDOFF.md, PR targeting ai4r_main_branch, independent human review, and post-merge checks. Those later records do not yet exist.

| When | AC / affected boundary | Command or inspection method | Working directory / environment prerequisites | Pass criterion source | Result location |
| --- | --- | --- | --- | --- | --- |
| Baseline | Existing model/runtime/session behavior | Recorded backend/Node commands | ENVIRONMENT selected runtimes | Baseline comparison, not feature acceptance | TEST_REPORT |
| Feasibility | G1–G4 | Reproducible bounded protocol/rail/capability proofs; no production deployment | Pinned schema + isolated profile | §6 resolution conditions | research and TEST_REPORT |
| Per story / final | Active ACs | Proposed pytest codex tests, frontend scripts and Q1–Q6 | Implemented tests; own account for live checks | spec v0.2 | TEST_REPORT |
| Post-merge | Integration and fresh-start smoke | Rerun affected baseline + Q1/Q2/Q5 against actual merged SHA | Confirmed integration base and profile | spec v0.2 and approved verification scope | TEST_REPORT/HANDOFF |

Pre-existing environment failures and selected-runtime successes are in TEST_REPORT. Legacy import tests are inapplicable. Live account tests, full capability fixtures and supported-platform checks remain unrun; Xiaoyang owns their prerequisites.

## 8. Approval record — required

| Design version | Code baseline SHA | Code Lead | Decision | Time and timezone | Evidence location / exact decision | Conditions |
| --- | --- | --- | --- | --- | --- | --- |
| 0.1 | dc9e6afdbacdc78a5d2eede3b4ab0dd1347e7483 | Xiaoyang | Pending | Pending | TASK records actual spec confirmation and request to write this proposal; neither approves this unwritten-at-the-time design | Resolve G1–G4 or explicitly authorize bounded proofs; identify contracts/tasks/directive versions before production work |

| 0.1, presented summary only | dc9e6afdbacdc78a5d2eede3b4ab0dd1347e7483 | Xiaoyang | Scope/direction/gap handling confirmed; details unreviewed | 2026-09-28 America/Toronto; exact message time not retained | TASK Section 4 records acceptance of the three-row review table and clarification that unpresented items are unknown | No blanket authorization of detailed design, all tasks, verification code or live account tests. Present the concrete next execution scope before relying on this as its approval; existing read-only research may continue |

| 0.1, bounded verification scope | dc9e6afdbacdc78a5d2eede3b4ab0dd1347e7483 | Xiaoyang | R001/R002 authorized | Current conversation, 2026-09-28 America/Toronto; exact time not retained | Subsequent user accepts presented verification steps 1 and 2; TASK Section 4 / write_code v0.6 | Isolated offline fixtures and signed-out protocol/process check only; no login/model turns or production conversion in this stage |

| 0.1, isolated protection prototype | dc9e6afdbacdc78a5d2eede3b4ab0dd1347e7483 | Xiaoyang | R003/R004 authorized | Current conversation, 2026-09-28 America/Toronto; exact time not retained | User continues the presented prototype step and requires frontend coverage and SOP adherence; TASK Section 4 / write_code v0.7 | Isolated guards, frontend state/contract fixtures and signed-out probe; full product/UI/account acceptance remains open |

| 0.2, M1 addendum | dc9e6afdbacdc78a5d2eede3b4ab0dd1347e7483 | Xiaoyang | Presented login/basic-chat milestone authorized | 2026-09-28 America/Toronto; exact message time not retained | User: "Execute according to SOP", following the concrete product milestone proposal; TASK Section 4 | Scope is M001-M006; technical details are author choices within that scope, not a claim that the user reviewed unseen details; full-project and live validation gates remain |

## 9. Revision history — when revised

| Date | Version | Change and reason | Effect on existing approval | Follow-up |
| --- | --- | --- | --- | --- |
| 2026-09-28 | 0.3 | Resolve startup, account routing and terminal-confirmed cancellation during M005 integration | Within explicitly continued M1 scope; no requirement or acceptance change | Actual account/browser acceptance remains |
| 2026-09-28 | 0.2 | Add user-authorized staged login/basic-chat implementation and conservative restart behavior | Applies only to presented M1 scope; whole-project requirements unchanged | M005/M006 verification and later capability work |
| 2026-09-28 | 0.1 | First source-grounded proposal under spec v0.2 | No existing design approval | Review gaps and feasibility sequence |
| 2026-09-28 | 0.1 decision addendum | Record confirmation of the presented summary and the user's explicit limit to presented items | Summary confirmed; no technical content or implementation approval changed | Present concrete next-step scope |

## Template coverage mapping

| Source template section | Authoritative destination |
| --- | --- |
| DESIGN 1–9 | This document §1–§9, preserving required fields and tables |
| PLAN 1 Baseline/objectives | Technical Context, §1–§2; task registry and ENVIRONMENT links |
| PLAN 2 Files/dependencies | §4 file table, boundary table, tasks dependencies |
| PLAN 3 Execution steps | tasks.md phases; sole progress authority |
| PLAN 4 Verification | §3 and §7; quickstart command/scenario detail |
| PLAN 5 Discoveries/decisions | research.md evidence and proposed ADR; tasks.md records execution impacts |
| PLAN 6 Remaining work/handoff | tasks.md remaining-work section |
| PLAN 7 Closure | tasks.md closure section; still incomplete |
