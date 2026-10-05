---
id: system.integration
type: design
status: draft
version: 1
sources: [../capsule/runner.md, ../capsule/toolchain.md, ../capsule/future-state.md, ../capsule/permissions.md]
provides: [system.adapters]
consumes: [system.events]
depends_on: [../terms.md, nodes.md]
tags: [system, m1, integration]
level: detail
prd: [3.0.1, 4.6.3]
---
# Integration: where CC code meets existing code

PRD: 3.0.1, 4.6.3

> Answers: Where does CC code meet existing jiuwenswarm and agent-core code?

> Every place CC code meets existing code. Each row fixes an adapter boundary; runtime verification remains downstream.

**Citations.** AC is agent-core at `9e339019`, jiuwenswarm's dependency pin; paths start `openjiuwen/`. JS is jiuwenswarm at `6cc05c36b`; paths start `jiuwenswarm/`. Rows distinguish verified source entrypoints from new adapter behavior. Runtime integration [probes](environment.md#term-probe) remain validation obligations, not undefined architecture. Line references for `agent_teams/workflow/engine/` and `agent_teams/workflow/runner.py` were re-read at the pin (`git show 9e339019:<path>`, 2026-10-05). The local agent-core HEAD `e23806c1` is older than the pin and its lines differ by about 47 after line 640. References marked `(pin, re-check)` were not verified at the pin; re-check them before coding. What to reuse and what to build is decided on [reuse](../reuse.md).

The [pinned-source audit](reuse-audit.md) records native retries, cache bypass, flush/rename limitations, shared Codex service custody, Leader limits and CodeSearch execution controls. These source mechanisms require the described adapters and probes; native behavior is not automatically CC authority.

## Centralised communication

Additional rows: the native [human_session](lifecycle.md#term-human-session) and backend session quartet at AC openjiuwen/agent_teams/workflow/engine/primitives.py and engine/backends/base.py map through cc.adapters.local_session, as specified by [lifecycle](lifecycle.md#failure-human-review-and-recovery). OpenJiuwen CodeSearch's model-free BM25Retriever/build_index/search_ast_nodes at deepsearch ff243bca4ab409116476587dcb106cf526581804 map through cc.adapters.codesearch, as specified by [CodeSearch](../capabilities/op-codesearch.md). These rows establish adapter scope; terminal execution and package import acceptance are still unrun.

Three rules keep every author on the same wires:

1. **Only `cc/adapters/` imports agent-core or jiuwenswarm.** There is one adapter per existing system, each with the small API below. No other CC module imports `openjiuwen` or `jiuwenswarm`. This is checked once code exists (proposed lint `adapters_only`).
2. **Inside CC, modules use published public APIs, the record store and the event bus.** No CC module calls another module's internals. The [module/process map](modules.md) names allowed calls; [lifecycle](lifecycle.md) is the home of service IPC.
3. **A new connection to existing code is a new row on this page first, then code.** An author who needs something not listed adds the row (with its citation) through the normal documentation update, never a private import.

```mermaid
flowchart LR
    subgraph CCM["CC modules"]
        LN["launcher"]
        FZ["freeze"]
        RU["runner"]
        GH["gate host"]
        ST["store"]
        PSK["progress sink"]
    end
    subgraph ADP["cc/adapters"]
        A1["swarmflow"]
        A2["codex"]
        A3["kv"]
        A4["runview"]
        A5["symphony"]
        A6["tracing"]
        A7["entry"]
    end
    subgraph EX["agent-core and jiuwenswarm"]
        E1["Swarmflow engine"]
        E2["Codex SubscriptionService"]
        E3["BaseKVStore, ShelveStore"]
        E4["WorkflowRunState, workflow.updated"]
        E5["Symphony"]
        E6["observability semconv, spans"]
        E7["CLI and agent server"]
    end
    LN --> A1 --> E1
    RU --> A1
    RU --> A2 --> E2
    ST --> A3 --> E3
    PSK --> A4 --> E4
    FZ -.->|"Phase 2"| A5 --> E5
    PSK -.->|"optional"| A6 --> E6
    A7 --> LN
    E7 --> A7
```

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-swarmflow"></a>**SwarmFlow** (also: Swarmflow) | The agent-core workflow engine we reuse. It runs the fixed outer flow and the frozen task DAG, with `CcBackend` as its backend and its journal used as a cache only. |
| <a id="term-codex-adapter"></a>**Codex adapter** | The CC adapter (`cc/adapters/codex.py`) that wraps the existing Codex subscription service for the model bridge. It builds a dedicated instance instead of using the shared chat transport. |
| <a id="term-adapter"></a>**Adapter** (also: adapters) | The one module per existing system under `cc/adapters/`, the only place CC code imports agent-core or jiuwenswarm. A new connection is added as a row on the integration page first. |

## The adapters

### `swarmflow`: run a plan, be the backend

**Adapter API:** `start_run(run_id, args, *, journal_path) -> dict` (calls `run_workflow` with the generic script, `CcBackend`, the progress forwarder, `run_id` and an `abort_event`; re-raises `CcHalt`); `CcBackend` (the `AgentBackend`); `cc_node(args, step_id, **refs) -> envelope`; `ENVELOPE_SCHEMA`; the generic script `plan_script.py`.

**Launcher rules for `run_workflow`** (source: `engine/runner.py` and `engine/primitives.py` at the pin):

1. **`CcHalt` derives from `BaseException` and also sets the engine's `abort_event`.** The native `parallel()`, `pipeline()` and `map_parallel()` wrap each branch in `except Exception: return None` (`primitives.py:1463` and `:1514` at the pin; `map_parallel` starts at `:1535`, its wrapper line `(pin, re-check)`). An `Exception`-based halt raised in a branch would become `None` and the script would continue after a failed step. A `BaseException` passes through those wrappers. Setting `abort_event` also stops sibling branches at the engine's next abort checkpoint. Because `CcHalt` is not an `Exception`, the engine's `except Exception` block in `run_workflow` (which emits `WORKFLOW_FAILED`) does not run, so the launcher emits `cc.run.halted` itself.
2. **Always pass `backend=CcBackend(...)`.** If `backend` is `None`, `run_workflow` builds a `MockBackend` (`runner.py:358`) that returns fake results. The launcher asserts `isinstance(backend, CcBackend)` before the call, and the adapter test [checks](../capsule/fields.md#term-check) it.
3. **Always pass `run_id`.** With `run_id=None` the journal cache (`get_cached(ks, sig, run_id)`, `journal.py:191`) can match on the call signature alone, so a different run could replay an earlier result.
4. **`args` are references only, never secrets, never `None`.** The engine stores `args` in the journal as a run record (`runner.py:342-349`), and with `args=None` it reloads the stored args for that `run_id`. Pass a dict of Refs and ids.
5. **Hidden retries.** `Runtime.retries` is 2 (`runtime.py:62`). `_attempt_calls` (`primitives.py:692`) retries backend exceptions, timeouts and schema-coercion failures, and `run_workflow` has no switch for it. This is compatible with M1's zero retries only because `CcBackend.run` never raises and always returns a valid envelope carrying the typed failure, and the script never sets `options={"timeout": ...}`. A required test injects a backend exception and proves the dispatch and model run at most once.
6. **The journal is not durable authority.** WAL append and [snapshot](../capsule/library.md#term-library-snapshot) write call `flush`, not `fsync` (`journal.py:272`, `:292`). An abort leaves the in-flight call unjournaled (`primitives.py:629` checks abort before the journal write), so a native resume would run that call again. [Idempotency](../contracts/principles.md#term-idempotency) reuse in the supervisor is therefore mandatory, not optional ([runner](../capsule/runner-broker.md#swarmflow-backend-talking-to-the-engine)).

| Existing symbol | Where | What CC does with it | M1 |
|---|---|---|---|
| `run_workflow(path, *, args, backend, resume, journal_path, progress_sink, abort_event, run_id, ...)` | AC `agent_teams/workflow/engine/runner.py:294` (`args` :297, `backend` :298, `resume` :299, `journal_path` :300, `progress_sink` :305, `abort_event` :310, `run_id` :311) | the launcher calls it directly with the [generic script](nodes.md#generic-workflow-adapter), `CcBackend`, the run's journal, the progress sink, an `abort_event` and an explicit `run_id` (rules above) | used |
| `AgentBackend.run(prompt, opts, schema_json, *, call_key) -> AgentResult` | AC `agent_teams/workflow/engine/backends/base.py:118` (class :39; `AgentResult` :22) | `CcBackend` implements it ([runner](../capsule/runner-broker.md#swarmflow-backend-talking-to-the-engine)) | used |
| `agent(prompt, *, label, phase, schema, options)` | AC `agent_teams/workflow/engine/primitives.py:540` | `cc_node` calls it once per step | used |
| `_attempt_calls` (retry loop) | AC `agent_teams/workflow/engine/primitives.py:692`; `Runtime.retries=2` at `engine/runtime.py:62` | not called by CC; it is why `CcBackend` must never raise | constraint |
| `parallel`, `pipeline`, `map_parallel` | AC `agent_teams/workflow/engine/primitives.py:1446`, `:1495`, `:1535` (branch wrappers `except Exception: return None` at `:1463`, `:1514`) | the generic script may use them only because `CcHalt` is a `BaseException`; `cap` bounds concurrency | used |
| script entry `async def run(args)` | AC `agent_teams/workflow/engine/primitives.py:1668-1680` | the generic script defines `run(args)` | used |
| `load_workflow_source`, `META` | AC `agent_teams/workflow/engine/loader.py:97-110` `(pin, re-check)` | the generic script defines a top-level literal `META` and `async def run(args)`, or the loader refuses it | used |
| `call_signature` | AC `agent_teams/workflow/engine/journal.py:61` | the resume key the call descriptor is designed around | used |
| `ProgressSink`, `WorkflowProgressEvent`, `ProgressKind` | AC `agent_teams/workflow/engine/progress.py:137`, `:59`, `:37` | the engine's own events (agent started, completed, failed, workflow completed, and more) reach the progress sink beside CC's events | used |
| `run_swarmflow`, `SwarmflowTool` | AC `agent_teams/workflow/runner.py:228`; `agent_teams/workflow/tool_swarmflow.py:70` | **not used.** They are the native team-mode path: `run_swarmflow` calls `run_workflow` (`workflow/runner.py:340` and `:369` at the pin), and the jiuwenswarm ws server has the controls `swarmflow.pause`, `swarmflow.resume` and `swarmflow.stop` (`_handle_swarmflow_pause`, `_resume`, `_stop`, JS `jiuwenswarm/server/agent_ws_server.py` around `:6609-6619`, local head). The CC launcher is the first **direct** caller of `run_workflow` outside the team path. The web and TUI surfaces reuse the native control names pause, resume and stop for a CC run; they map to the supervisor's halt, resume and abort ([lifecycle](lifecycle.md#failure-human-review-and-recovery)) | names reused; calls not |

### `codex`: the model, for M05

**Adapter authority:** the [model bridge](model-bridge.md) is the home of dispatch/cancel/status, deadlines, required capture and dedicated process custody. Reuse the pinned service/transport primitives through a CC-owned instance; the native shared singleton and its inactivity/interrupt defaults are not the CC lifecycle. Map provider failures through M05 without silently repeating a [turn](model-bridge.md#term-model-turn).

| Existing symbol | Where | What CC does with it | M1 |
|---|---|---|---|
| `get_service()` | JS `jiuwenswarm/server/runtime/codex_subscription/service.py:214` | Native shared root accessor, inspected for reuse only; CC constructs a dedicated instance/profile through its adapter | used |
| `SubscriptionService.stream(session_id, request_id, text, model=None)` | JS same file `:131` | M05 sends one turn and drains it to completion ([model client](../capsule/runner-broker.md#the-model-client-contract-m05)) | used |
| `CodexSubscriptionAdapter.process_message_stream_impl` | JS `jiuwenswarm/server/runtime/agent_adapter/interface_codex.py:33` | **not used by M05.** It refuses everything but plain chat (`MILESTONE_TEXT_ONLY`). A web entry into a CC run is a new branch beside it ([entry](#entry-how-a-run-starts)) | entry only |

### `kv`: the record store's backing

**Adapter API:** data_dir resolves the local user root. The previous open_kv/Shelve proposal becomes an optional committed-record lookup cache; [storage](storage.md) is the home of durable immutable publication and atomic batches. Only M12 accesses backing storage; a cache cannot authorize a [Gate](../verification.md#term-gate) transition.

| Existing symbol | Where | What CC does with it | M1 |
|---|---|---|---|
| `BaseKVStore.exclusive_set`, `.get`, `.get_by_prefix` | AC `core/foundation/store/base_kv_store.py:42`, `:57`, `:93` | M12 writes once with `exclusive_set` and lists by prefix | used |
| `ShelveStore(db_path)` | AC `core/foundation/store/kv/shelve_store.py:30` | optional rebuilt index; no assumed transaction/fsync guarantee | cache only |
| `get_user_workspace_dir()` | JS `jiuwenswarm/common/utils.py:416` (reads `JIUWENSWARM_DATA_DIR` at :427) | the data dir for records, content and the code cache | used |
| `BaseObjectStorageClient` | AC `core/foundation/store/object/base_storage_client.py:7` | content bytes, when they move off the local disk | later |

### `runview`: what the user sees

**Adapter API:** `forward(event)`, which takes engine progress events and CC events and sends `workflow.updated` deltas for the run's chat session.

| Existing symbol | Where | What CC does with it | M1 |
|---|---|---|---|
| `WorkflowRunState.apply(progress)` | JS `jiuwenswarm/agents/harness/team/handlers/workflow_state.py:200`, `:345` (input `WorkflowProgress` :41) | the progress sink turns engine events and `cc.gate.decided` and `cc.run.halted` into run-view deltas | used |
| `workflow.updated` event shape | JS `jiuwenswarm/agents/harness/team/handlers/workflow_monitor_handler.py:323-328` | CC sink constructs the same `{event_type, session_id, workflow}` projection and installs subscription for the CC session; this adapter does not require team dispatch | used; non-team rendering is an explicit downstream fixture |

### `entry`: how a run starts

**Adapter API:** the CLI command `jiuwenswarm cc run --topic <text> [--workspace <dir>]`, which calls `launch(prompt, "cli", workspace)`; and the web branch, which calls `launch(prompt, "web", workspace)`.

| Existing symbol | Where | What CC does with it | M1 |
|---|---|---|---|
| the `jiuwenswarm` CLI | JS `pyproject.toml` script `jiuwenswarm.channels.cli.main:main` | a `--topic` command calls the launcher (PRD 3.1.1) | used |
| `dispatch_parsed_request` (`chat.send`) | JS `jiuwenswarm/server/agent_ws_server.py:2383` | authenticated CC entry routes to `cc.adapters.entry` before ordinary text-chat runtime dispatch; the adapter calls the same launcher as CLI | used; explicit new branch, no dependency on ordinary AgentRuntime adapter hop |

### `deepsearch`: scholarly search

**Adapter API:** `async scholarly(query: str, top_k: int) -> list[dict]`, called only by [`op.scholarly_search`](../capabilities/op-scholarly-search.md). Each row is `{source, source_id, title, authors, published, url, content}`. Exactly what it does:

1. **Construction.** It builds both wrappers with `fetch_full_text=False`, `max_web_search_results=top_k` and `full_text_timeout_seconds=20`. So each call makes exactly one API request per service, and never scrapes or downloads a paper (PRD 3.3.2 excludes navigating unstructured sites).
2. **Calls.** It calls arXiv, then Semantic Scholar, each under `asyncio.wait_for(..., 50)`. Before each arXiv request it waits until 3 s have passed since the last one: the wrapper's own spacing is per process, and every tool host is a new process. The last-request time is kept in `<workspace>/.cc/state/deepsearch.json`.
3. **Errors.** Every `httpx.HTTPError`, `requests.RequestException`, `ScholarlySearchResponseError` and timeout from one service marks that service unavailable. One unavailable service is reported to the [operator](../capabilities/README.md#term-operator), which records an `EXTERNAL_UNAVAILABLE` issue. Both unavailable raises `cc.ExternalUnavailable`.
4. **Rows.**
   - A Semantic Scholar row whose `content` is the wrapper's no-abstract fallback (title, authors, journal and date joined, DS `semantic_scholar.py:179`) is dropped. Only abstracts become passages.
   - An arXiv id has its trailing `v<n>` stripped before it becomes `arxiv:<id>`, and before rows are compared.
   - The two lists are merged alternating (arXiv first), duplicates (the same arXiv id, or the same DOI) dropped, and the result cut to `top_k`.
5. **Replay.** When `cc.replaying()` is true, no request is sent. Each service request reads `<workspace>/.cc/replay/deepsearch/<sha256 of RFC 8785 JSON {service, query, max_results}>.json`, the raw response body (arXiv Atom XML, Semantic Scholar JSON), and parses it with the wrapper's own parser. A missing file means that service is unavailable.

Schema: the capsule-facing call to this adapter (`service: scholarly`) is is `tools-v1.schema.json#broker_search_request` and the reply `tools-v1.schema.json#broker_search_result`.

DS is the deepsearch repository at `ff243bc`; paths start `deepsearch/openjiuwen_deepsearch/framework/openjiuwen/tools/search_api/scholarly_search/`.

| Existing symbol | Where | What CC does with it | M1 |
|---|---|---|---|
| `ArxivSearchAPIWrapper.aresults(query) -> list[dict]` | DS `arxiv.py:65` (class), `:100` (`aresults`); `fetch_full_text` default `True` (`:46`, `:71`); spacing `ARXIV_REQUESTS_PER_SECOND = 1/3` (`:50`) | external search, with full text off | used |
| `SemanticScholarSearchAPIWrapper.aresults(query) -> list[dict]` | DS `semantic_scholar.py:43` (class), `:98` (`aresults`); `max_web_search_results` 1 to 10 (`:48`); no-abstract fallback (`:179`) | external search, with full text off; its API key is optional | used |
| row fields `title`, `url`, `content`, `source`, `source_id`, `published`, `authors` | DS `arxiv.py:223-232`; `semantic_scholar.py:183-188` | mapped onto [`search_hits`](../types/search-hits.md) | used |
| `ScholarlySearchResponseError` | DS `common.py:37` | caught, with the HTTP errors arXiv does not wrap | used |
| `DeepSearchAgent`, `AgentFactory` | DS package root | **not used.** It needs its own LLM API key, and would hide model behaviour inside an operator | not used |
| local search (Milvus index, embedding model) | DS `LocalSearchConfig` | **not used.** Local search is [`op.local_search`](../capabilities/op-local-search.md), plain keyword code | not used |

**Dependency resolution.** `openjiuwen-deepsearch` pins `openjiuwen[observability]==0.1.17` while this project pins agent-core `9e339019`. Do not install its conflicting dependency tree into M1. Vendor the minimum licensed scholarly connector/parser sources under `cc/adapters/deepsearch/`, with source commit/licence notices and replacement imports isolated there. CodeSearch likewise implements the verified model-free BM25 interface behind `cc/adapters/codesearch.py`; no DeepSearch agent/model runtime is imported. Validate clean imports, parser [fixtures](test-surfaces.md#term-fixture) and wire compatibility downstream. Replace the vendored adapter when upstream dependencies converge without changing [search_hits](../types/search-hits.md#term-search-hits) or operator [ports](../capsule/fields.md#term-port).

### `sandbox`: one jiuwenbox sandbox per attempt

**Adapter API:** `cc/adapters/sandbox.py` calls the [jiuwenbox](../isolation.md#term-jiuwenbox) HTTP API through our own client: create, exec, upload, download and delete, once per attempt (`jiuwenbox/src/jiuwenbox/server/routes/sandbox.py`). It sets [Landlock](../isolation.md#term-landlock) compatibility to `hard_requirement` (the jiuwenbox default is `best_effort`), network `isolated` and the server token. It does **not** use the process-global `JiuwenBoxRunner` singleton (JS `jiuwenswarm/server/sandbox/jiuwenbox_runner.py`), which auto-starts a server. See [isolation](../isolation.md) and [environment](environment.md#linux-confinement-inside-the-monolith). Route and policy field names are `(pin, re-check)`.

### `symphony`: task nodes (Phase 2)

| Existing symbol | Where | What CC does with it | M1 |
|---|---|---|---|
| `CapabilityProvider` (`capabilities()`, `source_snapshot()`) | AC `symphony/interfaces/capability.py:13` | `CapsuleProvider` publishes admitted [capsules](../capsule/capsule.md#term-capability-capsule) only, ports as `CapabilityIO` (AC `symphony/models/capability.py:15`, descriptor `:61`) | Phase 2 |
| `SymphonyGraphEngine.plan(query, candidate_ids, ...)` | AC `symphony/graph_engine.py:113` | source precedent only; the M1 planner service (not a CC) emits the fixed template through [planner](planner.md), followed by deterministic validation. No planner capsule layer and no model call | not active |
| `ScanResultCapabilityProvider`, `SwarmSymphonyService.plan` | JS `jiuwenswarm/symphony/adapter.py:27`; `jiuwenswarm/symphony/service.py:390` | templates for the provider and the planning call | Phase 2 |
| `symphony.enabled` | JS `jiuwenswarm/resources/config.yaml:33-34`; `jiuwenswarm/symphony/config.py:142` | off unless a Phase 2 run turns it on | Phase 2 |

### `leader`: native Leader identity for the experimental planner

At agent-core `9e339019`, `openjiuwen/agent_teams/schema/blueprint.py` exports `LeaderSpec` and `TeamAgentSpec.build`; `runtime/team_plan.py` exports `is_team_plan_enabled`. Reuse their identity/model/plan-mode configuration through `cc/adapters/leader.py`. Source was verified with `git show 9e339019:<path>` on 2026-10-02; the local mirror HEAD differs and is not the dependency pin. [Planner](planner.md) is the home of propose/validate interfaces; the Leader adapter belongs to block B27 and the isolated experiment track only. Native unrestricted delegation, plan approval and task mutation do not substitute for validate/bind/freeze or Gate release. The adapter exposes the read-only library snapshot and returns a typed proposal; only the supervisor dispatches admitted [nodes](nodes.md#term-node).

### Inspection and replacement policy

This is the recorded integration map, inspected at the dependency pin. Reinspect a symbol only when its pin changes, a described behavior is disproved, or a new requirement affects it. Adapters are the migration boundary. The pattern follows [Microsoft's anti-corruption layer](https://learn.microsoft.com/en-us/azure/architecture/patterns/anti-corruption-layer): translate upstream behavior into stable CC contracts without leaking upstream types into every module.

### `tracing`: optional spans

| Existing symbol | Where | What CC does with it | M1 |
|---|---|---|---|
| `OJ_RUN_ID = "openjiuwen.run.id"` | AC `extensions/observability/semconv.py:50` | every CC span carries the run id | optional |
| `open_agent_run_span(..., run_id=...)` | AC `harness/observability/run_span.py:69` | one root span per run | optional |
| `get_current_tool_span()` | AC `extensions/observability/span_context.py:982` | `cc.*` attributes on the current span | optional |
| `TrajectoryStore`; `trajectory_ui.enabled: false` | JS `jiuwenswarm/observability/store.py:388`; `jiuwenswarm/resources/config.yaml:569-570` | where spans land when tracing is turned on | optional; off in Codex mode |

## Existing code CC deliberately does not use

| Existing | Where | Why not |
|---|---|---|
| jiuwenswarm `SkillManager` install, agent-core `SkillManager.register` | JS `jiuwenswarm/server/runtime/skill/skill_manager.py:735`; AC `core/single_agent/skills/skill_manager.py:159` | a skill's files can change under the same version in that store, so CC [runs](lifecycle.md#term-run) skills only from its own content store, by hash ([tools](../capsule/tools.md#what-the-existing-pieces-give)). An importer may use `install_symphony_skill_artifact` (JS same file `:5348`) later |
| `PermissionEngine.check_permission` | AC `harness/security/permission_engine/core.py:272` | native permission rails are off by default (shipped config has `permissions.enabled: false` with defaults `allow`), compose only the Global, User and Session layers and ignore per-agent permissions (JS `permission_compose.py` around `:246`), and are not isolation; the Codex runtime skips the rail. At M1 the runner decides permission itself ([runner](../capsule/runner-broker.md#permissions-and-human-interaction-at-m1)) and confinement comes from the [restricted child](../capsule/process-boundary.md#term-restricted-child) profile. Agents never run capsules natively |
| `JiuwenBoxRunner`, `SysOperation` sandbox mode | JS `jiuwenswarm/server/sandbox/jiuwenbox_runner.py:73`; AC `core/sys_operation/sys_operation.py:167-184` | these two native entry points are not used (the runner is a process-global singleton that auto-starts a server). jiuwenbox itself already implements Bubblewrap, Landlock, [seccomp](../isolation.md#term-seccomp) and network namespaces and is the reuse base for restricted children: the CC [`sandbox`](#sandbox-one-jiuwenbox-sandbox-per-attempt) adapter calls its HTTP API with Landlock `hard_requirement`, network `isolated` and the server token, never its default policy ([process boundary](../capsule/process-boundary.md#confinement-engine), [environment](environment.md#linux-confinement-inside-the-monolith)). Its general orchestration (dependency install, secrets, resource limits) is deferred |
| [RSI](../rsi.md#term-rsi) service (`RsiTaskService.create`, `.start`) | JS `jiuwenswarm/agents/harness/common/rsi/services.py:124`, `:474` | RSI connects to CC through [Candidates](../schemas/candidate.md#term-candidate) and [Data Foundation](storage.md#term-data-foundation) exports, not at run time ([seams](seams.md)) |
| local `restrict_to_sandbox` | JS native shell-tool path check `(pin, re-check)` | it checks absolute paths written literally in the shell command string; `$var` paths are not detected and `get_cwd` falls back to `os.getcwd()`. It is not a boundary, so CC uses attempt directories and the sandbox |
| engine `verify()` | AC `agent_teams/workflow/engine/primitives.py:929` | it returns votes, not per-check results; CC's gates need three outcomes and records |
