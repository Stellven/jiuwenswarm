---
type: review
status: draft
version: 1
owner: muk
sources: [integration.md, modules.md, ../../product/SOURCE_FREEZE.md]
provides: [system.reuse_audit_2026_10_05]
consumes: []
depends_on: [integration.md, modules.md, environment.md, model-auth.md, ../capsule/runner.md]
tags: [reuse, audit, source, adapters]
---

# Pinned source reuse audit, October 5

This is inspection evidence, not another integration specification. [Integration](integration.md) owns adapter allocation; [modules](modules.md) owns proposed code placement. This audit reopened inspection because the new planner, Codex abstraction and authority-cleanup requirements affect those boundaries. No package imports, authenticated turns, workflow execution or security tests were performed.

## Method and source identities

Read source with `git show <pin>:<path>` and locate definitions with `git grep -n ... <pin> -- <paths>`. Inspected agent-core at the dependency pin **`9e3390195a9ea15235b2b5f7412cb2aa440622cc`**, jiuwenswarm at the existing integration pin **`6cc05c36b`**, and DeepSearch at **`ff243bca4ab409116476587dcb106cf526581804`**. The local agent-core HEAD is `e23806c1073275780dced2b71ddd592ffb0a21fd`; it was not substituted for the pin. Jiuwenswarm's inspected architecture starting checkpoint was `b9979ca38f982b757505300c02f4108724a07629`.

The reviewed source packages were local mirrors under `huawei/openjiuwen/agent-core`, `huawei/openjiuwen/deepsearch` and `huawei/jiuwenswarm`. DeepSearch has no root `pyproject.toml` at its pin; its relevant dependency declaration is `deepsearch/pyproject.toml`. A failed initial root lookup was corrected to that nested path. Received source documents were not modified.

## What actually exists and what the adapter must add

| Boundary | Exact pinned source evidence | Reusable behavior | Required M1 adaptation and limitation |
|---|---|---|---|
| Swarmflow execution | AC `openjiuwen/agent_teams/workflow/engine/runner.py:294` `run_workflow`; `:334` onward loads journal/WAL and creates Runtime | Script entry, backend injection, per-run args, progress, budget binding and normal-completion finalize | The CC supervisor remains release authority. Native journal return/replay is not proof of committed Verification/release. Interrupted calls without cache entries may be re-entered natively; the CC reservation boundary prevents another effect without explicit recovery |
| Backend contract | AC `.../engine/backends/base.py:22` AgentResult, `:39` AgentBackend, `:118` run; same file open/send/close/aclose | Single-shot structured result and optional human-session quartet | AgentResult.tokens defaults to zero, but absent provider usage remains explicitly unavailable in canonical CC telemetry; do not interpret the upstream default as measured zero |
| Hidden native retries | AC `.../engine/runtime.py:62` retries=2; `.../engine/primitives.py:692` `_attempt_calls` retries backend errors, timeouts and schema-coercion failures | Engine attempts are useful upstream behavior but not M1 execution policy | Existing CC design returns validated envelopes/skipped, omits engine timeout options and uses reservation reuse. Verify injected adapter/coercion failures cannot execute the capsule/model more than once. Native `run_workflow` has no public retries argument at this pin; do not document a nonexistent zero-retry switch |
| Native cache | AC `.../engine/primitives.py:563` reads cached result before backend; journal.py `call_signature` and `get_cached` | Same-script/run cache lookup and replay bookkeeping | Generic `cc_node` must reread exact supervisor authority even when backend was bypassed. A forged/stale native cache cannot authorize another node |
| Journal/WAL durability | AC `.../engine/journal.py:259` `_append_wal`, `:272` flush; `:292` flush before `os.replace` | Async append serialization, torn-tail tolerance and atomic snapshot rename | Source shows flush but no file/directory fsync in those methods. Do not borrow a power-loss durability guarantee from its docstring. Canonical CC store owns durable records and publication; journal is recoverable scheduling/cache data |
| Human review | AC `.../engine/primitives.py:1376` human_session; backend session methods above | Native session primitive and lifecycle hooks | Implement authenticated local terminal review with persisted review identity. Agent-kind sessions are not needed for runner-owned capsule skills. Headless halt must not await a terminal |
| Codex managed service | JS `jiuwenswarm/server/runtime/codex_subscription/service.py:14` SubscriptionService, `:131` stream, `:214` get_service | Managed account state, thread ownership/epoch binding, stream events, interrupted-thread invalidation | `get_service()` selects a singleton keyed by the native workspace's `subscription` directory, not an arbitrary CC profile. The CC bridge must construct its own service/transport at its dedicated root and own its lifetime; never close native user-chat transport during CC cancellation |
| Codex deadlines | JS same service `:125` interrupt wait=10, `:177` stream inactivity=180; transport.py `:128` request wait=30, close method has child wait=3 | Bounded native waits and unknown-delivery refusal | These source constants are not the CC configured turn deadline/cancel grace. The bridge adds its total deadline, tracks partial capture, and closes only its owned child after grace. No uncancellable unbounded drain and no automatic resubmission |
| Codex process and credentials | JS `.../transport.py:22` child_environment, `:44` profile claim, `:62` start | Dedicated CODEX_HOME, file-backed auth, exclusive profile lock, pinned packaged executable, text-only tools-off config | Native home/environment and configuration policy need mapping to the Docker volume/security owner. Native inherited HOME/PATH are not the generated-code environment contract. Separate login plus one writer is supported by this pattern; refresh behavior was not executed |
| Codex chat entry | JS `.../agent_adapter/interface_codex.py:33` process_message_stream_impl | Native ordinary text-chat streaming | It rejects team, skills, attachments and non-chat controls. Add the explicit authenticated CC entry branch; do not route CC orchestration through this plain-chat adapter or claim its restrictions provide capsule confinement |
| UI projection | JS `jiuwenswarm/agents/harness/team/handlers/workflow_state.py:345` apply; workflow_monitor_handler.py `:323` updated-event constructor | Progress-kind projection and `{event_type,session_id,workflow}` deltas | Unknown event kinds are ignored. Adapt CC durable-state events to known UI projection kinds; preserve run/session correlation. The rendering result is derived, not release authority; non-team subscription remains a required fixture |
| Optional KV cache | AC `openjiuwen/core/foundation/store/kv/shelve_store.py:69` exclusive_set, `:126` get_by_prefix | A local lookup implementation with db.sync | No CC transaction or directory-publication guarantee follows from this API. get unwraps exclusive-value wrappers; get_by_prefix returns stored wrappers. Normalize in the optional cache adapter and rebuild from authoritative committed records |
| Native Leader | AC `openjiuwen/agent_teams/schema/blueprint.py:159` LeaderSpec, `:198` TeamAgentSpec and its build; `runtime/team_plan.py:25` is_team_plan_enabled | Role identity, model/spec representation and plan-mode setting | is_team_plan_enabled is only a Boolean accessor. TeamAgentSpec.build materializes a full team/runtime and model-pool policy; it is not a read-only typed proposal generator. Reuse identity/config through a constrained adapter; proposal inference goes through the CC Codex abstraction, deterministic validator/freeze decide workability and dispatch |
| Scholarly connectors | DS `deepsearch/openjiuwen_deepsearch/framework/openjiuwen/tools/search_api/scholarly_search/arxiv.py:65` wrapper/`:100` async results; semantic_scholar.py `:43` wrapper/`:98` async results; common.py `:160` async_request_once | API request/response parsing with explicit full-text-off policy | Wrappers have upstream DNS, HTTP and shared control dependencies. Vendor the licensed minimum closure and isolate imports; deny custom remote/private endpoints, retain M1 budgets, and test exact parser fixtures. Source presence is not a clean-import result |
| CodeSearch | DS `codesearch/openjiuwen_codesearch/retropus/index.py:17` build_index, retrievers/bm25.py `:294` BM25Retriever/`:381` index/`:445` AST search | Model-free AST/text retrieval, reusable index and structured spans | Native build_index calls asyncio.run, so it cannot be invoked directly in a running event loop. Upstream tokenization may spawn ProcessPoolExecutor workers; do not adopt unbounded workers outside the confined resource profile. Result cap is MAX_RESULT=5 in retrievers/base.py. Existing M1 [CodeSearch](../m1/op-codesearch.md) uses a compatible local adapter rather than importing the full runtime |

AC paths abbreviated with `.../engine/` above are under `openjiuwen/agent_teams/workflow/engine/`. JS abbreviated `.../transport.py` and `.../agent_adapter/` paths are under `jiuwenswarm/server/runtime/`. Citations identify source at the stated pin; proposed `cc/` locations remain design destinations.

## Findings and disposition routing

| ID | Finding | Disposition and verification obligation |
|---|---|---|
| REUSE-01 | Integration's old Codex row promised an uncancellable drain and described get_service as per-profile, unlike the dedicated/configured CC bridge | Correct the integration summary to link [environment](environment.md#model-bridge) and [auth](model-auth.md); retain constructor ownership and bounded cancellation above. Downstream test two profiles, cancelled CC turn and surviving native chat |
| REUSE-02 | Native engine has two retries and bypasses backend on a cache hit | Preserve CC reservation/envelope/release adapter design; inject backend exception, schema failure and forged cache to prove zero duplicate effects and zero unauthorized releases. No fabricated public retries knob |
| REUSE-03 | Native WAL docstring uses crash-durable language beyond flush/rename implementation | Preserve [storage](storage.md) as authority. Separate process-interruption recovery from host power-loss guarantees in implementation evidence |
| REUSE-04 | Native KV prefix enumeration and individual get have different wrapper projection | Cache-only adapter normalizes both; corruption/missing cache never changes committed record authority |
| REUSE-05 | Leader identity/plan-mode support can be mistaken for a complete constrained planner | [Planner](planner.md) owns proposal/validator and Codex inference abstraction; do not enable unrestricted native team tools/delegation as a shortcut |
| REUSE-06 | CodeSearch upstream uses nested dependencies, synchronous event-loop entry and process-pool optimization | Retain snapshot-scoped local adapter; validate import closure, worker/process limits, source spans and deterministic ties. Reuse algorithm/interface precedent rather than its unrestricted process behavior |

The first finding is an architecture-summary correction. The remaining rows are source-supported adapter limits and concrete implementation probes, not claims that those behaviors have been tested. Subsequent review should mark a correction closed only after rereading the semantic owner and affected summary.

## Why this reuse boundary fits

[Microsoft's anti-corruption layer](https://learn.microsoft.com/en-us/azure/architecture/patterns/anti-corruption-layer) is the existing decision precedent: keep upstream types and behaviors inside adapters, publish stable project contracts, and validate translated semantics. Here the borrowed pattern prevents inherited cache/retry/team behavior from silently acquiring CC authority. It does not imply adopting a separate service deployment; adapters remain inside the Dockerized modular monolith.

Replace an adapter when its source pin changes, a specified behavior is disproved, or a new requirement affects the seam. Preserve its public contract or version it explicitly; recheck the dependent owners listed in the [authority index](../authority.md). No package version, licensed component, performance optimization or security guarantee is adopted merely because it is visible in this source audit.
