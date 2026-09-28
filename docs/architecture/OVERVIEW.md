# Project Architecture Overview

Version: 0.1 | Scope: AI4R-001 execution boundaries, not a replacement for the broader Capsule roadmap.
Template: [ARCHITECTURE_TEMPLATE](../code/code_sop/templates/ARCHITECTURE_TEMPLATE.md).

## 1. Version and evidence (required)

| Field | Value |
| --- | --- |
| Maintainer / most recent verification date | Xiaoyang / 2026-09-28 |
| Code version verified | ai4r_main_branch at dc9e6afdbacdc78a5d2eede3b4ab0dd1347e7483 |
| Current status | Partially verified by source inspection and prior bounded baseline checks; proposed runtime not implemented |
| Repository entry points | pyproject.toml; jiuwenswarm/start_services.py, channels/web/, gateway/, server/ |
| Relevant current design | [plan v0.1](../../specs/AI4R-001-codex-subscription/plan.md), Draft |
| Decision record | [ADR-0001 v0.1](../adr/0001-codex-subscription-runtime.md), Proposed |

## 2. System purpose and boundaries (required)

- Problem addressed: provide local projects, conversations, agents and teams with observable model/tool execution.
- External users/callers: one local user per installation; web/desktop/CLI/ACP entry points require coverage confirmation.
- Owned processing/output: app sessions/history, scheduling, coordination, UI transport and host tools.
- Outside boundary: external model account/service behavior and resource-provider availability.
- Execution modes: separate gateway, agent-server and web launch entries exist; current research inspected web chat and runtime consumers. Other launchers are inventory obligations.
- Existing design context: [big-picture.md](big-picture.md) explicitly describes an aspirational M4 system; [m1.md](m1.md) describes M1 planning. Their labels are not substituted for actual code ownership.

## 3. Module directories and responsibilities (required)

| Module | Actual directory / status | Primary responsibility | Outside scope | Owner / backup owner | Entry points and evidence | Module AGENTS |
| --- | --- | --- | --- | --- | --- | --- |
| Web client | jiuwenswarm/channels/web/frontend/src; existing | Settings, session UI and app events | Account token ownership | Unassigned / unassigned; Xiaoyang coordinates | useWebSocket, webClient, session stores | web and frontend AGENTS |
| Gateway | jiuwenswarm/gateway; existing | Transport, dispatch and scheduled callbacks | Model protocol implementation | Unassigned / unassigned | web_connect, app_web_handlers, cron/scheduler | Root AGENTS; inspect descendants before edits |
| Agent runtime | jiuwenswarm/server/runtime/agent_adapter; existing | Main/code execution adapters | User-visible auth setup | Unassigned / unassigned | create_adapter, interface_deep, interface_code | Root AGENTS |
| Teams | jiuwenswarm/agents/swarm; existing | Group assembly and coordination | Implicit subscription coverage | Unassigned / unassigned | assembly; installed MemberRuntime seam | Root AGENTS |
| Symphony/auxiliary services | jiuwenswarm/symphony and agents/harness/common; existing | Additional model/retrieval/evaluation paths | Assumed single-chat coverage | Unassigned / unassigned | research C06–C18 | Root; applicable descendants before edits |
| Subscription runtime | jiuwenswarm/server/runtime/codex_subscription; proposed | Account policy, lifecycle, bindings, tools/text ports | Silent provider fallback | Proposed coordinator Xiaoyang; module assignment pending | plan §4 | Root; local instructions to be added if needed |

No authoritative ownership register has been adopted; do not infer owners from branch names or roadmap module labels.

## 4. Dependency directions and data flows (required)

| Caller | Callee | Purpose | Contract path | Synchronous / asynchronous / batch | Failure handling owner |
| --- | --- | --- | --- | --- | --- |
| Frontend | Gateway | Account requests and existing chat/control | Draft feature contracts/runtime.md | Asynchronous app RPC/events | UI reports; gateway validates |
| Gateway | Agent-server lifecycle owner | Managed auth/catalog and run control | Same draft | Existing internal control transport | Backend service |
| AgentAdapter / team/scheduler | Codex session runtime | Native agent execution | Same draft; existing app adapter contract retained | Async streams | Session runtime and host coordinator |
| Runtime | Host MCP bridge | Scoped tool execution | Same draft | Async request/response | Host tool authorization owner |
| Auxiliary callers | Text/JSON port | Bounded model work | Same draft | Async completion | Caller plus typed runtime errors |

Proposed flow: frontend -> gateway -> Jiuwen session/coordinator -> Codex adapter -> App Server; tool requests return through scoped host tools; provider events map back to existing app session events. Account control is centralized even when harness clients launch separate workers.

Allowed directions: UI uses app interfaces; backend owns runtime/account; host tools retain scoped authority. Prohibited: browser reading auth files, model-supplied session authority, independent key-provider fallbacks, ambiguous duplicate tool execution.

## 5. State, data, and resources (required when applicable)

| Data / state / resource | Owner | Source and storage location | Lifecycle | Consistency / concurrency requirements | Recovery after failure |
| --- | --- | --- | --- | --- | --- |
| New application profile/history | App persistence | Dedicated JIUWENSWARM_DATA_DIR | Initialize once, persist across launches | No force overwrite or old-root import | Preserve files; reconcile execution state |
| Codex auth/thread state | Codex under app lifecycle control | Dedicated profile CODEX_HOME | Managed login through logout | Account-generation fencing across workers | Explicit sign-in/reconciliation |
| Session/thread/turn mapping | Runtime binding owner | Existing app persistence with proposed binding fields | Per session/agent and account generation | One active turn per binding | Resume matching thread or show interruption |
| MCP/server processes | Backend lifecycle owner | Local children/endpoints | Start after policy checks, close on logout/shutdown | Scoped requests and cleanup acknowledgments | Stop orphan work before readmission |

Legacy migration N/A under CR-01; newly created data durability remains required.

## 6. Environment and execution (required)

- Installed versions/commands: [ENVIRONMENT](../governance/ENVIRONMENT.md).
- Launcher: pyproject.toml maps jiuwenswarm-start to jiuwenswarm.start_services:main; proposed fresh-profile behavior is not yet implemented or launched.
- External dependencies: personal subscription, compatible Codex SDK/binary, scoped resource services; embeddings/media equivalents unresolved.
- Configuration precedence proposed: selected data root before cached path resolution; explicit binary and sanitized child config/env; no ambient model keys/provider overrides.
- Verification entry points: [TEST_REPORT](../tasks/AI4R-001/TEST_REPORT.md) baseline and [quickstart](../../specs/AI4R-001-codex-subscription/quickstart.md) proposed acceptance; no standalone TESTING record yet.

## 7. Quality attributes and architectural constraints (required; select applicable items)

| Attribute | Requirement and source | Architectural support | Verification location |
| --- | --- | --- | --- |
| Authentication and credential boundaries | AC-01/06 | Managed account service, isolated home, sanitized launch/logs | Plan/quickstart Q1/Q4 |
| Session/interaction correctness | AC-02/03/07 | Identity binding, generation fence, scoped tool receipts | Q2/Q3/Q5 |
| Coverage and honest failure | AC-04/08 | Typed errors and per-capability gates | research inventory, Q4/Q6 |
| UI compatibility | Frontend AGENTS | Shared controls, both locales, Chrome107 | Build/browser verification |

## 8. Current facts, proposed changes, and technical debt (required)

| Item | Type | Evidence of current state | Target / treatment | Owner | Task or ADR | Blocks current work? |
| --- | --- | --- | --- | --- | --- | --- |
| Existing account path is direct auth/client | Verified source fact | app_web_handlers and modelAdapters | Replace operational path | Xiaoyang | AI4R-001 / ADR-0001 | Does not block drafting |
| Native harness skips native rails | Known limit | installed setup_agent/member runtime | G1 parity proof | Xiaoyang | T001 | Blocks dependent implementation |
| Embedding/media/specialist parity | Pending verification | research C12–C18 | G3 evidence or explicit scope change | Xiaoyang | T003 | Blocks whole-project claim |
| SDK permissive approval/env defaults | Known limit | research R4 | G4 fail-closed launch/control | Xiaoyang | T005–T007 | Blocks safe runtime activation |

## 9. Architecture change log (required when changes occur)

| Date | Change | Design / ADR | Code Lead approval evidence | Effective code SHA |
| --- | --- | --- | --- | --- |
| 2026-09-28 | Baseline boundary inventory and proposed subscription runtime | plan v0.1 / ADR-0001 | Pending design approval | Not effective; no application changes |

Architecture documentation does not establish runtime acceptance or final review.
