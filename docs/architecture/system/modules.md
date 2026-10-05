---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-02.txt, integration.md, ../capsule/toolchain.md, ../capsule/runner.md]
provides: [system.module_map, system.process_topology]
consumes: [system.adapters, cc.gate_host, cc.run_plan]
depends_on: [integration.md, ../capsule/runner.md, ../capsule/toolchain.md]
tags: [system, m1, responsibility]
---

# M1 modules, code placement and processes

This is the current owning map for proposed M1 code locations and process placement. These paths are design destinations, not claims that code already exists. The old 27-module design is historical. Product semantics stay with the named workstream; Muk owns shared CC interfaces. Each module publishes the seven contracts in [PROCESS](../PROCESS.md): placement, interface, control, persistence, security, environment and verification.

## Module map

All paths below are relative to the jiuwenswarm repository. Cross-module calls use the linked public API. Store and events are shared state interfaces; they do not prohibit direct calls to another module's public API.

| Module / design owner | Proposed code location | Process | Reuse or new boundary | Public authority / dependencies |
|---|---|---|---|---|
| Configuration, startup, doctor / Muk with Xiaoyang | `cc/config.py`, `cc/bootstrap.py`, `cc/doctor.py` | trusted supervisor | new CC profile wrapper; reuse upstream startup through adapter | [environment](environment.md); runs before launch |
| Entry and local session / workstation owner, Muk for API | `cc/adapters/entry.py`, `cc/adapters/local_session.py` | trusted supervisor | wrap native CLI, `chat.send`, local Web/TUI | [workstation](workstation.md), [integration](integration.md#entry-how-a-run-starts) |
| Launcher, restart, halt / Muk | `cc/launcher/`, `cc/launcher/plans/m1.json` | trusted supervisor | new lifecycle API around Swarmflow | [lifecycle](lifecycle.md), [toolchain](../capsule/toolchain.md#m01-launcher) |
| Freeze / Muk | `cc/freeze.py` | trusted supervisor | new; resolves admitted library versions | [toolchain](../capsule/toolchain.md#m03-freeze-the-binding-writer), [storage](storage.md) |
| Swarmflow adapter and generic script / Muk | `cc/adapters/swarmflow.py`, `cc/adapters/plan_script.py` | trusted supervisor | `run_workflow`, `AgentBackend`, journal adapter | [integration](integration.md#swarmflow-run-a-plan-be-the-backend), [lifecycle](lifecycle.md) |
| Runner service and client / Muk | `cc/runner/service.py`, `cc/runner/client.py`, `cc/runner/pipeline.py` | managed runner subprocess; client in supervisor | pipeline is new; core engine backend reused | [runner](../capsule/runner.md), [lifecycle](lifecycle.md) |
| Kind handlers, broker, SDK / Muk | `cc/runner/handlers/`, `cc/runner/broker.py`, `cc_sdk/` | runner; untrusted code in restricted child | new protocol; text-only model turns through broker | [runner](../capsule/runner.md#kind-handlers) |
| Model bridge / Muk; routing behavior: Model Routing | `cc/adapters/codex.py`, `cc/model.py`, `cc/adapters/model_bridge.py` | trusted model bridge | wrap existing subscription service; protected local IPC is new | [environment](environment.md#model-bridge), [runner M05](../capsule/runner.md#the-model-client-contract-m05) |
| Check runner / Muk with Ramika for criteria | `cc/checks/runner.py`, `cc/checks/registry/` | trusted gate host; restricted check subprocess | fixed registry and check ABI | [toolchain M10a](../capsule/toolchain.md#m10a-check-runner-and-the-check-library) |
| Gate host / Muk; acceptance profiles: Ramika | `cc/gate.py` | trusted supervisor | new fold and durable decision writer | [gate host](../capsule/gate-host.md), [Verification](../schemas/verification-record.md) |
| Store, hashes, vocabulary, policy / Muk | `cc/store.py`, `cc/hashing.py`, `cc/vocab.py`, `cc/policy/` | trusted supervisor, sole persistent writer | new durable file publication; native KV may index committed records | [storage](storage.md), [toolchain](../capsule/toolchain.md) |
| Author kit and admission / Muk | `cc/kit.py`, `cc/admission.py` | trusted CLI; test calls through runner | tested or Puppet admission behind one provider; mandatory integrity first | [admission](../capsule/admission.md), [toolchain M13/M14](../capsule/toolchain.md#m13-author-kit) |
| Eight research work capsules and shared verifier / stage owner, Muk for schema | `capsules/research.<capability>/` | runner skill handler or restricted tool child | one semantic verifier with pinned stage criteria; deterministic checks remain host code | [pipeline](../m1/pipeline.md) |
| Three search capabilities / Muk | `capsules/op.<search>/`, `cc/adapters/deepsearch.py`, `cc/adapters/codesearch.py` | nested restricted tool child | local/scholarly/code search; bounded retrieval permissions | [M1 operators](../m1/order.md) |
| Mechanical research helpers / Muk | `cc/research/` | supervisor, restricted child only where permission boundary requires | ordinary functions for source extraction, IntentIR, rank/arithmetic, snapshot/compiler/publication | [pipeline](../m1/pipeline.md); expose canonical payloads without separate capsule identity |
| Generated POC service / Muk, Xiaoyang | `cc/security/poc_service.py`, `cc/security/linux_launcher.py` | separate restricted process tree | new confinement and offline installer | [process boundary](../capsule/process-boundary.md) |
| Data Foundation / Suraj, Muk for shared evidence API | `cc/evidence.py`, `cc/data/collector.py`, `cc/data/assembler.py`, `cc/data/export.py` | mandatory capture in trusted supervisor; assembler offline | native memory/trace adapters plus new lossless capture | [storage](storage.md#required-evidence-and-derived-views), [seam](../seams.md#data-foundation) |
| Progress and UI / workstation owner | `cc/events.py`, `cc/adapters/runview.py` | supervisor; native browser/TUI clients | reuse native views; new CC state mapping | [workstation](workstation.md) |
| Offline RSI / Saurav, Muk for Candidate/evidence interfaces | `cc/rsi/session.py`, `cc/rsi/attempts.py`, `cc/rsi/submit.py` | isolated offline controller; no live DAG mutation | existing RSI sources are reuse candidates, not yet verified | [RSI engine](../capsule/rsi-engine.md) |
| Fixture oracle / Saurav, Muk/Xiaoyang for security | `cc/security/oracle.py` | independent private daemon; isolated child per case | new aggregate-only authenticated API | [oracle](../capsule/fixture-oracle.md) |
| Isolated planner and validator / Muk | `cc/planning/service.py`, `cc/planning/validate.py`, `cc/adapters/leader.py` | trusted experimental controller; model proposal through bridge | native Leader identity; new typed plan validator; planner is not capsule | [planner](planner.md) |
| Experimental compiler/router/Code Mode adapters / workstream owner | `cc/experiments/entry.py`, `cc/adapters/` | separate experimental worker/profile | whitelist-only adapters; native permissions for Code Mode | [experiments](experiments.md) |
| External benchmark entry/export / Muk interface, Saurav harness | `cc/benchmark_api.py`, `cc/data/export.py` | trusted headless entry/export | new versioned evidence boundary; harness internals external | [benchmark export](benchmark-export.md) |

## Deployment placement

[Deployment](deployment.md) owns one Docker image/container. The process labels below are internal monolith trust boundaries, not independent services or deployment units. Host CLI/browser and the external benchmark harness use loopback-published APIs; all runtime Python, TUI/tmux, Codex app-server and restricted children run inside the same Linux image. Benchmark traffic enters the authenticated versioned endpoint on host 127.0.0.1:8787. No per-task container creation or runtime Docker socket is available.

## Process topology

Additional canonical components: `cc/records.py` owns [system-record variants and reservations](records.md); `cc/measurements/registry.py` and `protocol.py` own method registration, parsing and arithmetic; `cc/security/measurement_service.py` owns [trusted per-arm evidence](../m1/measurement-protocol.md#trusted-measurement-authority) in a trusted process with isolated workload children. Snapshot/compiler/comparison helpers live under `cc/research/`; requiring a restricted subprocess does not itself require a capsule. These are new modules, not reuse claims.

```mermaid
flowchart LR
    CLI["host API client / in-container CLI and TUI"] --> SUP["trusted supervisor: launcher, engine, gate, store"]
    WEB["loopback-published Web UI"] --> SUP
    SUP <-->|"authenticated runner frames"| RUN["managed CC runner subprocess"]
    RUN --> TOOL["restricted tool and check children"]
    RUN <-->|"authorized model request"| MODEL["trusted model bridge"]
    MODEL <-->|"existing inherited stdio"| CODEX["Codex app-server"]
    RUN --> POC["separate confined POC service"]
    RSI["offline RSI controller"] <-->|"aggregate only"| ORA["private oracle daemon"]
    ORA --> CHILD["restricted child per fixture"]
    RSI -->|"Candidate to admission"| SUP
    EXP["isolated experiment entry"] -->|"validated run_plan"| SUP
    EXP --> LEAD["native Leader adapter / model bridge"]
    HAR["external benchmark harness"] -->|"authenticated HTTP v1: task/config/seed"| SUP
    SUP -->|"sealed export references"| HAR
```

The runner is a managed subprocess for PRD 4.6.3. `CcBackend` remains the engine's client in the supervisor; the R2 pipeline and R6/R7 handlers execute in the runner process. Only the trusted supervisor writes the store. Runner record requests and required evidence return through its authenticated channel; the supervisor validates their writer/identity before committing. The model bridge holds login credentials and supplies text results only. No untrusted child inherits the supervisor environment, home directory, store directory or model login files.

## Reuse evidence

Upstream adapters are owned by [integration](integration.md); cite the existing symbol there rather than copy it. The inspected integration source pin is `6cc05c36b`, with agent-core pin `9e339019`; it is distinct from the current architecture revision. Newly verified destinations include `pyproject.toml:9` (Python), `:134` (CLI scripts), `:141` (startup), `jiuwenswarm/start_services.py:525` (process commands), `:687` (readiness), and `server/runtime/codex_subscription/transport.py:97` under `jiuwenswarm/` (inherited stdio). These establish reuse entrypoints, not that upstream already satisfies the security or persistence contracts.

## Design status

This map retains draft status pending Muk's approval. Connected AI review and dispositions are recorded in [final review](../reviews/2026-10-03-final-fresh-review.md). [Handoff](handoff.md) and [coder requirements](coder-requirements.md) provide the full seven-question matrix; [verification](verification.md) supplies failure hooks. Twelve capsules is the current minimal proposal, justified by capability boundaries rather than a target count. Platform validation obligations block execution on affected platforms while their system contracts remain defined.
