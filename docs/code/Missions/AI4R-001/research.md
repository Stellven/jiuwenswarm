# AI4R-001 — Code and protocol investigation

Version: 0.4 | Baseline: dc9e6afdbacdc78a5d2eede3b4ab0dd1347e7483 | Date: 2026-09-28
Requirements: [spec v0.2](spec.md). Design authority: [plan v0.1](plan.md).
Research is sufficient for a concrete proposal, not a completed whole-project feasibility proof. G1–G4 remain open.

## Evidence sources and limits

Static source inspection of application and installed OpenJiuwen 0.1.18 / SDK 0.144.4; no account credentials inspected, model calls made, or application source changed. Subsequent R001/R002 execution is recorded below; it goes beyond static inspection but not into authenticated acceptance. Existing baseline test evidence is in TEST_REPORT. Official [App Server documentation](https://learn.chatgpt.com/docs/app-server) describes managed account login, thread/turn events and experimental dynamic tools. Official [authentication documentation](https://learn.chatgpt.com/docs/auth) documents a ChatGPT-only login restriction. Current documentation can differ from the locked runtime; generated local schema is the protocol baseline.

Executed the packaged binary's `app-server generate-json-schema --out <local-evidence-directory>`, then repeated with `--experimental`; both exited 0. Experimental generation produced 337 JSON files. ClientRequest exposes 122 distinct methods. ThreadStartParams contains dynamicTools; TurnStartParams contains outputSchema; login variants include chatgpt and chatgptDeviceCode. These fields establish syntax availability, not successful subscription execution. No generic embedding/audio/video service method was found in that generated client-method inventory; that absence does not prove every possible model/tool capability is unavailable.

Local evidence: `%LOCALAPPDATA%/ai4r-tools/evidence/AI4R-001/protocol-0.144.4/` and `protocol-0.144.4-fingerprints.json`. No generated protocol dump needs to be shipped as application source at this stage.

## Actual request and control flow

1. Frontend `hooks/useWebSocket.ts::sendMessage` sends chat.send; `features/sessionInput.ts` preserves request/execution identity and late ACK states.
2. `gateway/channel_manager/web/web_connect.py` registers session/request and forwards a Message to the gateway callback. `app_web_handlers.py::_chat_send` only acknowledges transport.
3. `server/runtime/agent_adapter/agent_adapters.py::create_adapter` selects main/code adapters. `interface_deep.py::_create_model` calls build_model_from_entry; create_instance/_create_instance builds a DeepAgent with tools/rails/subagents/workspace.
4. `services/webClient.ts`, `services/sessionEventGate.ts`, `stores/chatStore.ts` and `stores/sessionStore.ts` route stream/history by application session and execution.
5. Existing account RPCs are OPENAI_ACCOUNT_RPC in settingsContract.ts; app_web_handlers invokes OpenAIAccountAuthManager and OpenAIAccountModelCatalog directly. modelAdapters.ts carries a direct Codex backend URL. This path is not App Server.
6. Installed `openjiuwen/harness_providers/codex/harness.py::CodexHarness` uses AsyncCodex, thread start/resume, turn stream/steer/interrupt and MCP. `harness_providers/io_adapter.py::HarnessIOAdapter` maps protocol output and interactions onto OutputSchema.
7. Installed `agent_teams/agent/agent_configurator.py::setup_agent` can adopt a MemberRuntime while retaining coordination; it skips native DeepAgent/rails/memory construction. Existing team assembly converts nonleader external templates; replacing a worker does not prove leader coverage.

## Capability inventory — authoritative coverage register

All paths below are under jiuwenswarm/ unless prefixed by the installed package name. Status is static evidence plus proposed disposition; no row is a passed subscription scenario.

| ID | Existing capability and concrete evidence | Proposed subscription treatment | Gap / verification required |
| --- | --- | --- | --- |
| C01 | Login/catalog: gateway/channel_manager/web/app_web_handlers.py; frontend OpenAIAccountField.tsx | App Server managed auth/catalog service | Auth races, sanitized transport, no direct token client |
| C02 | Main chat: server/runtime/agent_adapter/interface_deep.py::_create_model, _create_instance, process_message_stream_impl | Native harness at AgentAdapter seam | G1: full event/tool/rail parity |
| C03 | Code mode: interface_code.py; agent_adapters.create_adapter | Same subscription adapter with explicit code-mode behavior | File changes, review/plan mode, permission equivalence |
| C04 | Team leader/workers: agents/swarm/assembly.py::_apply_agent_group; team_helpers.py | Keep team coordination; replace execution for all roles | G1: leader injection, budgets, evolution, memory/rails skipped by external runtime |
| C05 | Cron/heartbeat: gateway/cron/scheduler.py::_run_unary_cron_job, _run_stream_cron_job, _run_team_stream_job; agent_ws_server.py model cache | Shared admission/runtime; no background interactive login | Correct scheduler/session identity, expired account, no hidden cached Model |
| C06 | Symphony: symphony/llm.py::LLMConfig.create_model, JiuwenSwarmChatClient._invoke | Narrow text/JSON service where semantics match | G2: structured output, usage/error mapping, unsupported sampling controls |
| C07 | Skill retrieval: symphony/skill_retrieval/runtime.py::_llm_config constructs CoreLLMConfig | Explicit injectable auxiliary completion | G2: dependency builder adaptation, ranking behavior |
| C08 | Background extraction: agents/harness/common/rails/eternal_conversation/background_agents.py::BackgroundAgentRunner.call_json | Scoped auxiliary completion | Validation/retry/background evidence preserved |
| C09 | Recommendation: agents/harness/common/recommendation/proactive_actions.py::_get_model, gradient_updater.py, calendar_source.py | Auxiliary completion per consumer | G2: complete call inventory and task-specific fixtures |
| C10 | Recap/repair/compression: interface_deep.py::_call_model_for_recap, repair_model_response, compact_partial | Explicit text/JSON tasks or verified native replacement | Context/summary/history equivalence; no double compaction |
| C11 | RSI/evaluation: agents/harness/common/rsi/model_resolver.py::_default_model_builder; auto_harness/service.py | Subscription-only factory/adapters | G2/G3: evaluation assumptions and model-dependent settings; no dummy pass |
| C12 | Vector memory: agents/harness/common/memory/embeddings.py::OpenAICompatibleEmbeddingProvider.embed_documents; interface_deep embedding setup | No equivalent selected yet | G3 blocker: generic embeddings unproven; random MockEmbeddingProvider is not acceptable semantic retrieval |
| C13 | Memory/background specialists: memory/dreaming/sweeper.py; TTSE setup in interface_deep.py | Inventory LLM vs vector needs separately | G2/G3: preserve retrieval and consolidation quality |
| C14 | Images: agents/harness/common/tools/image_tools.py::_invoke_openai_vision and generation settings | Assess image input and generation independently | G3: text chat success proves neither modality |
| C15 | Audio: agents/harness/common/tools/audio_tools.py::_create_openai_client_for_audio, audio_question_answering | No equivalent selected yet | G3: speech/transcription/tool contracts require proof |
| C16 | Video: agents/harness/common/tools/video_gen_tools.py::_get_video_gen_api_credentials; extensions/video_duplex/backend/ | No equivalent selected yet | G3: external vendor generation/duplex cannot be relabeled Codex |
| C17 | Search: agents/harness/common/tools/search_tools.py::run_free_search_structured, run_paid_search_structured | Evaluate existing free search or Codex-backed search; no unapproved removal | G3: free DDG/Bing is not automatically equivalent to paid providers |
| C18 | Additional model tools/hooks: tools/wiki_tools.py, tools/web_fetch_tools.py, server/hooks/executor.py, model compiler/routing/cache helpers | Assign each direct caller to runtime/text/unsupported categories | G2/G3: must enumerate remaining call sites and use provider-construction/outbound traps |
| C19 | Host tools, plugins and interactions | Session-scoped MCP with single tool executor; reuse UI and host permissions | Tool schema/name, cancellation/idempotency and permission coverage |
| C20 | Profile/storage/packaging/platforms: common/utils.py, init_workspace.py, common/external_cli_runtime.py, pyproject.toml entry points | Separate persistent profile and explicit binary; inspect every shipped launcher | No force initialization; Windows-first evidence does not imply other platforms/CLI/ACP support |

Inventory must grow if further executable paths are found. AC-08 requires every agreed row to have observable equivalent behavior and evidence; code disabled behind an error is not successful replacement. Changes to capability scope require a user decision.

## Decisions, rationale and alternatives considered

### R1 — Reuse native harness, not a transparent completion adapter

**Decision proposed:** preserve app/session/team layers; introduce CodexSessionAdapter using CodexHarness/HarnessIOAdapter and scoped host MCP tools.
**Rationale:** these already model App Server turns and interactions. A BaseModelClient returns tool calls for DeepAgent to execute on later invocations, whereas App Server owns an ongoing tool-interaction turn.
**Alternatives considered:** generic held-turn ModelClient bridge (unproven cancellation/tool ownership); replacing all team orchestration (larger regression surface). G1 must establish native rail/team parity before selecting production implementation.

### R2 — One account lifecycle owner with explicit worker registration

**Decision proposed:** account/control service in agent-server; gateway proxies; per-session harness clients register with the service. All share only a dedicated app-owned Codex home, not an IDE token export.
**Rationale:** SDK/harness currently owns client processes; centralizing ownership of sign-in/out and generation fencing avoids pretending one login client can stop all independent workers automatically.
**Alternatives considered:** independent account control per frontend/session (race-prone); one global harness shared across sessions (identity leak and serialized work risk).

### R3 — Fresh profile, persistent thereafter

**Decision:** user-directed CR-01 removes legacy migration.
**Evidence:** get_user_workspace_dir resolves a cached path, then JIUWENSWARM_DATA_DIR, then the default root. init_user_workspace(overwrite=True)/run_init(force=True) can delete a workspace.
**Treatment proposed:** choose separate root before caching; initialize only absent defaults. No --force, old-root import, or launch-time deletion.

### R4 — Fail closed around existing permissive defaults

CodexHarnessConfig accepts external provider/api_base/api_key and fallback_model; _maybe_activate_fallback can reconnect externally. HarnessIOAdapter defaults to auto_approve_tools=True; ExternalHarnessMemberRuntime sets it true. _install_approval_handler can warn and allow automatic approval if private SDK hooks are unavailable. SDK child launch merges os.environ even when an upstream environment was curated. These are implementation facts requiring policy wrappers and tests, not reasons to weaken permissions.

**Decision proposed:** reject external/fallback settings, validate approval integration before launch, explicitly disable automatic tool approvals, sanitize actual child environment/config, and redact frontend logDevWsTraffic (which forwards raw frames).
**Alternative considered:** trust the optional external-agent defaults unchanged; rejected under AC-03/06.

## Outstanding research gates and closure evidence

| Gate | Required evidence | Owner / resumption condition |
| --- | --- | --- |
| G1 | Real main+leader fixture, host-tool execution once, plan/budget/memory/permission rail matrix, pause/steer/cancel/history results | Xiaoyang; resolve before dependent runtime production work |
| G2 | All auxiliary consumers enumerated; pure text/JSON without autonomous tools; schema validation, errors and required controls proven | Xiaoyang; resolve before each consumer conversion |
| G3 | Concrete equivalent for C12–C18 and platform/capability evidence; otherwise an explicit spec change | Xiaoyang; unresolved rows block full coverage |
| G4 | Pinned schema/SDK checks plus sanitized launch, approval rejection, login/logout/account-generation and process cleanup tests | Xiaoyang; resolve before account/runtime release |

No research gate is closed by drafting this file. There is no actual account/model execution evidence yet.

## Bounded execution evidence after user confirmation

R001/R002 are complete within their explicit offline/signed-out scope. Authoritative commands, results and artifact fingerprints are in [TEST_REPORT v0.5](TEST_REPORT.md), T-20/T-21. No broader research gate is closed.

| Evidence | Actual observation | Design consequence / remaining gap |
| --- | --- | --- |
| R001: installed HarnessIOAdapter permission fixtures | Default auto-allow and an empty object both allow; explicit denial/cancellation deny; duplicate pending ID rejected | Require explicit boolean decisions and complete identity checks before adapter.send; never pass malformed/stale replies through |
| R001: stale input fixture | Answer for an absent request becomes provider FOLLOW_UP input while current approval remains pending | Product boundary must reject stale control messages before the generic adapter; otherwise old decisions may become new user instructions |
| R001: session/output fixtures | Separate adapters isolate pending IDs; final snapshot does not duplicate deltas | Reusable primitives only; application session routing, concurrency and real stream not proven |
| R001: capability/seam fixtures | Running pause rejected; dynamic calls declined; injected leader runtime skips native memory/construction | Explicit pause mapping and scoped MCP remain required; real leader rails/coordination still unproven because workspace collaborators were mocked |
| R001: SDK/approval-hook fixtures | Curated harness env is re-inherited by SDK child launch; missing approval hook warns instead of refusing | Validate the actual spawn environment and approval installation before admitting runs; wrappers are still to implement |
| R002: real binary with isolated home | Two initialize/account-read cycles return signed-out and exit cleanly via EOF | Pinned local protocol/process lifecycle works in this narrow scope; no account eligibility/model/capability conclusion |

Next verification requirements: malformed decision rejection, stale decision rejection without provider forwarding, actual child-environment filtering, and missing-hook startup refusal must become failing product tests before implementation. This is a refinement of existing AC-03/06/07, not an acceptance waiver or scope expansion. Real local login/model checks await the user's availability.

## Isolated protection prototype and frontend evidence

R003/R004 exercise fixes in feature-local research code, without product integration. [TEST_REPORT v0.6](TEST_REPORT.md) T-23-T-26 owns actual commands and results: final Python suite 29 passed, frontend controller eight passed, guarded signed-out probe two cycles passed.

- ApprovalBroker creates single-use tickets bound to session/execution/thread/turn/generation/request/call. Exact boolean decisions only; stale/duplicate/malformed controls are rejected. GuardedIOAdapter separates chat and approval input and propagates cancellation/stop to pending waiters.
- Strict approval-hook installation can refuse a supplied startup callback. Curated direct Popen launch excludes inherited model-provider credentials/overrides. The original SDK.start is NOT patched; joining these primitives to the full SDK/harness is still a G4 obligation.
- The frontend controller consumes scoped approval notices, disables repeat actions during submission, rejects obsolete sessions and retains delivery_unknown after ambiguous failures. Node-generated JSON is accepted by the Python broker for both allow and deny; no real React/browser/WS behavior is claimed.
- Limitations: one displayed pending request per controller; the eventual UI must queue additional requests explicitly. One broker per immutable execution; gateway authorization, durable generation, signed-in restart, expiry, concurrent real agents and actual tool execution remain unproven. Permission-only prototype does not implement user questions, MCP or pause/resume.

These observations refine the existing design, without removing any capability or closing G1-G4. Complete frontend work remains explicitly scheduled alongside backend implementation, including bilingual settings/onboarding, session stream/history, stable test IDs and browser visual checks.
