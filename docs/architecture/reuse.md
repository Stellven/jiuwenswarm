---
id: arch.reuse
type: design
level: present
status: draft
version: 1
provides: [arch.reuse]
consumes: [arch.placement, arch.isolation]
depends_on: [placement.md, isolation.md, k8s-lens.md, system/integration.md, system/reuse-audit.md, system/modules.md, build-order.md]
tags: [reuse, jiuwenswarm, agent-core, start-here]
prd: [3.0.1, 4.1.4, 4.6.1, 4.6.2]
---

# What we reuse from jiuwenswarm and what we build

PRD: 3.0.1, 4.1.4, 4.6.1, 4.6.2

> Answers: What do we reuse from jiuwenswarm and agent-core, and what do we build?

Rule: **use a native feature when it does the job and does not break an invariant.** Build only where the native feature cannot keep one of our rules: single writer, [Gate](verification.md#term-gate) before release, zero retries, no ambient workspace, hash-pinned [capsules](capsule/capsule.md#term-capability-capsule).

- **REUSE** = call it as is.
- **WRAP** = call it through a thin adapter that fixes its defaults.
- **BUILD** = ours, with the reason.

Native code was read at the agent-core pin `9e339019` where possible. Symbols that exist only in the pin are flagged in [reuse audit](system/reuse-audit.md). Re-check line references at the pin before coding.

## Matrix

| Area | Native feature | Decision | What we do with it | Why |
|---|---|---|---|---|
| Workflow engine | `run_workflow`, `agent()`, `parallel`, `cap`, `BudgetLedger`, `abort_event`, `AgentBackend` | **REUSE** | `CcBackend` is our backend. Use `cap`, `budget` and `abort_event` for concurrency, budget and [halts](system/lifecycle.md#term-halt) | the engine already schedules, journals and aborts |
| Engine journal and WAL | `Journal` | **WRAP** | scheduling cache only. Never authority | flush without fsync, cache can replay |
| Sandbox | **[jiuwenbox](isolation.md#term-jiuwenbox)** HTTP API: create, exec, upload, download, delete | **REUSE** | one sandbox per attempt, [execution profile](schemas/profiles.md#term-executionprofile) set by us. The image holds the HTTP server, its token and policy; the doctor [probes](system/environment.md#term-probe) it | Bubblewrap, [Landlock](isolation.md#term-landlock), [seccomp](isolation.md#term-seccomp) and netns already built |
| Doctor | `run_doctor` | **WRAP** | Step zero, then our probes. Map `ok/failed` to `pass/fail/unsupported` | existing diagnostics |
| Human halt | `human_session`, pause/resume/stop controls | **WRAP** | `local_session` reads the reply. Use native control names on the web and TUI | native vocabulary and surface |
| Run view | `WorkflowRunState.apply`, progress events | **WRAP** | UI projection from engine events | already built |
| Spans | agent-core semconv, `open_agent_run_span` | **WRAP** | optional views. Records stay authority | spans can be dropped |
| Codex transport | `codex_subscription` service and transport | **WRAP** | dedicated profile, text-only, one stream. The existing `codex_start` profile is the precedent | already text-only and read-only |
| Permissions | permission engine, file guard, net guard, tool policy | **WRAP, later** | on only in a Mode 2 DeepAgent track as extra defense. Not counted as isolation | off by default, ignores per-agent rules, shell bypasses it |
| CLI, TUI, web, ws server | native channels, console scripts | **WRAP** | add the CC entry as one more branch | users already know them |
| Store, records, commit | native KV, checkpointer | **BUILD** | `cc/store.py` with atomic publish and fsync | single writer and durable authority needed |
| Skill runner | `SkillTool`, `SkillUseRail`, `SkillManager` | **BUILD** | single-turn runner over a hash-pinned `SKILL.md` | native skills give the model file and shell tools, and have no content hash |
| Tool runner | `ToolCard`, `LocalFunction` | **BUILD** | child process plus confinement | native tools have no process boundary |
| Workspace | `Workspace`, worktrees, `restrict_to_sandbox` | **BUILD** | attempt directories | native shell check misses `$var` paths and falls back to the cwd |
| Config | `get_config`, `resolve_env_vars` | **BUILD** | `load_config` with project layer, provenance, hash, freeze | native is one user file, no freeze |
| Planner | Leader, `TaskGraph`, Symphony `plan()` | **BUILD** | planner service (fixed template, no model call in M1) plus [validator](system/planner.md#term-plan-validator). Symphony only as a Phase 2 comparison | our plan must be validated, bound and [frozen](system/lifecycle.md#term-freeze) |
| Gate and verify | `verify()` votes | **BUILD** | [Gate host](capsule/gate-host.md#term-gate-host) and verifier CC | votes cannot express our three outcomes |
| [Model routing](model-routing/README.md#term-model-routing) | native router, failover | **BUILD** (static) | one frozen model, zero retries | native failover and retries break zero-retry |
| Memory | Task and Coding memory | **BUILD** | not used on the CC path. Summaries only | raw evidence stays in run bundles |
| Search | deepsearch, CodeSearch | **WRAP** | `op.*` capsules over vendored closure | [code_sha256](capsule/fields.md#term-code-sha256) pins and process boundary |
| Scheduling, cron | cron runtime, queues | **BUILD** | supervisor dispatch | different problem |

## Rules that follow

1. **Halts must not be swallowed.** `CcHalt` derives from `BaseException` and also sets `abort_event`. Native `parallel()` turns ordinary exceptions into `None`, which would let the script continue after a failed Gate.
2. **Pass the right things to the engine.** Always pass `CcBackend` (the engine silently uses a mock backend if none is given, which returns fake results) and always pass `run_id` (a missing id lets the cache match on signature alone). Pass only references as `args`, never secrets.
3. **Neutralize hidden retries.** The engine retries backend errors twice and offers no switch. Our backend never raises: it returns a valid envelope with the typed failure, so there is nothing to retry. A test injects an exception to prove it.
4. **One writer.** `parallel()` can call the backend concurrently. Every store write still goes through the supervisor's single writer. The runner returns its records and the supervisor commits them on its behalf (`commit_request`).
5. **No native tools on the CC path.** Native tools are ambient unless the working directory is set per task. Capsules reach files only through brokers.
6. **Do not use the process-global jiuwenbox runner singleton** that auto-starts a server. Call the HTTP API through our adapter.
7. **Do not use the trajectory store as evidence.** It deletes old rows.
8. **Own the wire and the exit.** Local channels use length-prefixed frames, not the native newline-delimited form. A run ends with exit code 0, 2, 3 or 4 (success, rejected, halted, environment unavailable).

## Contingencies

- A direct ChatGPT-account model client exists in agent-core (no app-server child process). It is a fallback if the Codex app-server path [blocks](system/modules.md#term-block) us. It must be set to zero retries. Not chosen in M1.
- Native Symphony planning may be compared with our planner in Phase 2.

Detail: [integration](system/integration.md), [reuse audit](system/reuse-audit.md), [modules](system/modules.md), [k8s lens](k8s-lens.md).
