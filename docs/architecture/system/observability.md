---
type: design
status: draft
version: 1
owner: muk
sources: [../capsule/observability.md, ../capsule/runner.md, ../b1-design.md, ../../product/prd-m1-data-foundation.md]
provides: [system.events]
consumes: [cc.observation, cc.verification, cc.artifact]
depends_on: [ledgers.md, integration.md]
tags: [system, m1]
---

> **Draft: reopened 2026-10-02 for the join key and the build order below.** Previously checked. How M1 is observed, for now. The concept is on [observability and quality](../capsule/observability.md); this page is the M1 wiring.

# Observability at M1

**Records are the truth; events are the live feed.** Every capsule call, value, pin and gate decision is a record in the store ([ledgers](ledgers.md)). While a run is going, the CC hosts also announce what they do on **one event bus**. Every live consumer subscribes to that bus, and none of them reaches into a host.

```mermaid
flowchart LR
    LN["launcher"] --> BUS["cc event bus"]
    FZ["freeze"] --> BUS
    RU["runner"] --> BUS
    GH["gate host"] --> BUS
    HH["halt host"] --> BUS
    BUS --> PS["progress sink M18: workflow.updated"]
    BUS --> DFH["Data Foundation capture hooks"]
    BUS -.->|"when tracing is on"| TRC["tracer: one span per call"]
```

## The events

The one definition of every CC event. Each carries `run_id` (or `candidate_id` at admission) and `at`. An event that describes a record is emitted **after** that record is written, so a subscriber can always read it. `cc.call.started`, `cc.call.resolved` and `cc.call.nested` describe no record yet; they only announce.

| Event | Emitted by | When | Also carries |
|---|---|---|---|
| `cc.run.started` | launcher | after the `run_plan` and `intake` are recorded | `run_plan` ref |
| `cc.run.frozen` | freeze | after all Bindings are written | `{step_id: binding ref}` |
| `cc.call.started` | runner | pipeline step 0 | `obs_id`, `caller`, `step_id` |
| `cc.call.resolved` | runner | after code is verified | `obs_id`, `decl_hash`, `code_sha256` |
| `cc.call.refused` | runner | a refusal in steps 1 to 6 | `obs_id`, reason |
| `cc.call.nested` | runner (broker) | a nested call starts | parent and child `obs_id` |
| `cc.model.turn` | runner (broker) | each finished model turn (announce only) | `obs_id`, turn, elapsed, `model_hint`, `model_id`, `route_record_id` |
| `cc.call.finished` | runner | after the Observation is written | Observation ref, outcome, reason |
| `cc.gate.decided` | gate host | after the Verification is written | `step_id`, `obs_id`, Verification ref, decision, verdict |
| `cc.run.halted` | halt host | a halting verdict ended the run | `step_id`, verdict, Verification ref |
| `cc.run.finished` | launcher | the script returned | every step's envelope |

**The bus.** It is in-process: cc.events.subscribe(callback) and cc.events.emit(name, payload). Optional display/debug subscribers may fail without changing a run. Required lossless capture is a synchronous acknowledged [evidence API](storage.md#required-evidence-and-derived-views), not an ignored subscriber; missing capture blocks completion. Managed-runner events are relayed through authenticated supervisor IPC before publication. Cross-module control uses public APIs, never observer events.

## Who reads what

| Consumer | Reads | For |
|---|---|---|
| Progress sink (M18) | events | the browser's run view (`workflow.updated`), with each gate's verdict and the halt reason |
| Data Foundation | events live; records and content after the run | run records, bundles, scorecards, exports ([seams](../seams.md#data-foundation)) |
| Tracer (optional) | events | one span per capsule call, with the `cc.*` attributes on the [Observation](../schemas/observation.md#reuse) page |
| RSI | Data Foundation's exports | learning from real runs |
| Librarian (later) | records | Standing moves and Findings |
| A person debugging | records first, then spans if any | what ran, on which code, and why it stopped |

## One join key, one answer per question

*Reopened 2026-10-02. Muk confirmed `obs_id` as the key and the build order. A blind canary drew this system from the first version of this section and found the gaps listed below; they are now stated, not hidden. Not yet through the area loop.*

**Two authorities, one key.** The record store is the authority for decisions and lineage: what was called, with what, what came out, what the gate said. The sealed raw capture is the authority for evidence that cannot be recreated: prompts, replies, process frames ([storage](storage.md#required-evidence-and-derived-views)). Both carry `obs_id`, and the Observation names its capture manifest, so one key reaches both. Events, spans, Data Foundation exports and every reader's view are derived. A derived view never holds a fact the two authorities lack.

**`obs_id` is the one join key** for everything inside a capsule call. It is the Observation's own `id`. Every other id is stored where the table below says, and joins through `obs_id`.

```mermaid
flowchart TB
    subgraph SUPP["supervisor process: owns the bus"]
        SUP["supervisor and launcher<br/>reserves obs_id and attempt"]
        FRZ["freeze"]
        GH["gate host"]
        HH["halt host"]
        BUS(("cc event bus<br/>in-process, derived"))
    end
    subgraph RUNP["managed runner process"]
        RUN["runner: one call, one obs_id<br/>nested, judge and admission calls reserve their own"]
    end
    BODY["capsule body<br/>no write access to records"]
    CONF["confined process<br/>POC and benchmark"]
    BR["model bridge<br/>protected socket"]
    EP["model endpoint<br/>prompt only"]
    subgraph AUTH["authorities"]
        REC[("record store<br/>Observation id is the obs_id<br/>Artifact, Binding, Verification, system records")]
        CAP[("sealed raw capture<br/>prompts, replies, frames by sha256<br/>manifest carries obs_id")]
    end
    DF["Data Foundation<br/>exports, derived"]
    TRC["tracer, optional<br/>spans carry cc.obs_id"]
    PS["progress sink, optional"]
    PX["benchmark proxy<br/>development only"]
    RDR["RSI, librarian, a person"]

    SUP -->|"RunnerRequest: dispatch_id, obs_id, attempt"| RUN
    RUN -->|"RunnerResponse: observation_ref"| SUP
    RUN -->|"call frame, GAP 2"| BODY
    BODY -->|"model and nested frames"| RUN
    RUN -->|"PocExecutionRequest, GAP 2"| CONF
    RUN -->|"ModelBridgeRequest: request_id, run_id, obs_id"| BR
    BR -->|"ModelBridgeResult: request_id, reply hash"| RUN
    BR -->|"prompt only: no stage, role or capsule"| EP
    EP -->|"reply"| BR
    BR -->|"prompt and reply bytes before success"| CAP
    RUN -->|"process and tool frames, seal_execution"| CAP
    CONF -->|"process evidence, GAP 3"| CAP
    RUN ==>|"Artifacts, then the Observation: turns, outcome, manifest ref"| REC
    SUP ==>|"plan, intake, Bindings, reservation, release"| REC
    FRZ ==> REC
    SUP -->|"gate obs_ref"| GH
    GH -->|"judge call, own obs_id"| RUN
    GH ==>|"Verification"| REC
    GH -->|"committed Verification ref"| SUP
    SUP -->|"halt"| HH
    HH ==>|"halt record and review requirement"| REC
    HH -->|"headless: exit code 3. else human_session"| SUP

    RUN -.->|"events after the record, relayed by supervisor IPC, GAP 1"| BUS
    SUP -.-> BUS
    FRZ -.-> BUS
    GH -.-> BUS
    HH -.-> BUS
    BUS -.-> PS
    BUS -.-> TRC
    REC --> DF
    CAP --> DF
    REC --> RDR
    DF --> RDR
    BR -.->|"development-only trace event keyed by request_id, never upstream"| PX
    PX -->|"join request_id to obs_id"| REC
    TRC -->|"cc.obs_id to Observation"| REC

    F1["capture or seal fails: EVIDENCE_UNAVAILABLE<br/>no completion, supervisor halts"]
    F2["bridge unavailable or timed out<br/>Observation error, never resubmitted"]
    F3["message with no obs_id<br/>refused and recorded, see rule below"]
    F4["optional subscriber raises<br/>the call continues"]
    F5["gate save fails<br/>no success, halt, incident if storage permits"]
    CAP -.-> F1
    BR -.-> F2
    RUN -.-> F3
    BUS -.-> F4
    GH -.-> F5
    F1 --> SUP
    F2 --> SUP
    F5 --> SUP
```

Solid lines are data flow, double lines are record writes, dotted lines are events or derived views. `GAP n` points to the table of gaps below.

**Where each id is stored, and what exists today.** The first version of this table claimed fields the schemas do not have. This is the corrected one.

| Id | Stored in | Exists today? | Change required |
|---|---|---|---|
| `obs_id` | the Observation's `id` | yes | none |
| `run_id` | the Observation's `scope` | yes | none |
| `attempt`, `decl_hash`, `caller`, `binding_ref` | Observation fields | yes | none |
| `step_id`, `capsule_name`, `role` | not on the Observation. Reached through `binding_ref`, which for a nested call is the caller's Binding, and is null for an admission call | no | add `step_id`, `capsule_name` and `role` as Observation fields set by the runner for every call kind, null where none applies ([observation](../schemas/observation.md)). Without them, per-capsule attribution is wrong for nested calls |
| model bridge `request_id` | the turn entry in `ext.runner.turns` | no: the entry has `session_id` but no `request_id` | add `request_id` to the turn entry, and promote `turns` from `ext.runner` (declared not part of the record's meaning) to a checked Observation field ([runner](../capsule/runner.md)) |
| `route_id` | the turn entry, as `route_record_id` | partly: one field holds either the capsule's `route_id` or the gateway's id | split it into `route_id` and `gateway_route_id` |
| process or tool frame id | the capture manifest, under `obs_id`. Not on the Observation | the manifest exists, with no frame ids | frames are indexed in the manifest; the Observation does not carry them ([storage](storage.md)) |
| trace and span id | the Observation's `trace`. Spans carry `cc.obs_id` | yes | none |

**Which source answers which question.**

| Question | Source | Never |
|---|---|---|
| what happened, and was it right | records | an event or a span |
| the exact prompts, replies and process output | sealed capture, found through the Observation's manifest | |
| what is happening now | bus events | |
| why was a call slow or costly | spans. CC writes its own from records. The native tool span the runner stamps is a debugging extra, not a source of facts | a span as the only copy of a fact |
| attribution of a model call (the benchmark proxy) | a reader-side join on `obs_id` through the Observation | a field on the model request |
| Data Foundation exports | read from records and capture after the fact. A live bus feed is optional | |

**Nothing about the pipeline goes to the model endpoint.** The [bridge request](environment.md#model-bridge) names only `request_id`, `run_id` and `obs_id`, and the bridge forwards the prompt only. The runner's `ModelCallContext` (capsule name, step, role) goes to the trusted side of the bridge, for records and for an endpoint that routes itself. Whether the native service forwards the session id `cc:<run>:<obs_id>:<n>` upstream is unverified (open). Gateway mode is a separate decision with its own threat note.

**The `obs_id` rule has a scope.** Every CC message made on behalf of a capsule call carries `obs_id`, and one that cannot is refused. The refusal is written as a system record, or as an incident when storage cannot be written. Startup probes, `doctor`, bridge `status` and other messages made before any call exists carry no `obs_id`, are exempt, and use their own system-record id. An admission call has `candidate_id` and no `run_id`, so the bridge request takes `scope` (a `run_id` or a `candidate_id`).

### Gaps the canary found, and the resolution proposed for each

| # | Gap | Proposed resolution | Owner to change |
|---|---|---|---|
| 1 | which process hosts the bus. Runner events cross a process boundary, and the runner protocol has no event frame | the supervisor hosts the bus. Add a `RunnerEvent` frame to the runner protocol, sent after its record is written | [lifecycle](lifecycle.md), [runner](../capsule/runner.md) |
| 2 | `obs_id` on runner-to-tool-host and runner-to-confined-process frames (the tool-host frames carry an integer `id`) | add `obs_id` to both frame families | [runner](../capsule/runner.md), [process boundary](../capsule/process-boundary.md) |
| 3 | who writes the confined process's evidence into capture | the supervisor's process service, under the `obs_id` of the call that launched it | [storage](storage.md), [process boundary](../capsule/process-boundary.md) |
| 4 | halts with no gate verdict (gate-save failure, capture failure) emit no event, so the progress sink cannot show a reason | `cc.run.halted` covers every halt, with its reason owner. `cc.run.finished` follows a halt | this page |
| 5 | `cc.model.turn` and `cc.call.refused` fire before the Observation exists | they describe no record yet, so they join the announce-only list with `cc.call.started` | this page |
| 6 | the development trace flag does not exist | add `cc.telemetry.bridge_trace` (default false, development only). The proxy reads the trace sink, never the protected socket | [environment](environment.md) |
| 7 | `freeze` is named as an event emitter, but lifecycle gives freeze to the supervisor | the supervisor emits `cc.run.frozen` | this page |
| 8 | the Observation's own page says the call's details are on agent-core's span, which contradicts "records are authority" | reword it: spans are sampled and may expire, and hold nothing the records and capture lack | [observation](../schemas/observation.md) |

## Build order for observability

Observability is built in the same thin slices as the capsules, because every check in the [build order](build-order.md) reads it. Step numbers are the build order's. Each row says what it needs from earlier steps, which fixes the dependency the canary found.

| Build step | Add | Needs | Check |
|---|---|---|---|
| 1 | the Observation and the content store, written only by the runner, keyed by `obs_id` | a **stub reservation**: a single-process counter hands out `obs_id` and `attempt`. The supervisor's durable reservation replaces it at step 4 | a second call produces a second Observation. The same input gives the same output hash. A changed body is refused and the refusal recorded |
| 2 | the model bridge with sealed capture, and the turn entries with `request_id` | step 1, and the Observation changes in the table above | the turn replays with no network. `request_id` resolves to exactly one `obs_id`. The prompt bytes in capture match the bridge request |
| 3 | the Verification record, and an event bus **skeleton** (emit and subscribe only, with no sink) so `cc.gate.decided` can be emitted | steps 1 and 2 | a failing check is readable from the Verification alone. A test subscriber receives `cc.gate.decided` after the Verification is readable |
| 4 | the supervisor's durable reservation, halt records, the `RunnerEvent` frame and the remaining events | step 3 | kill the process between steps and resume from records alone. Every halt, including a gate-save failure, emits `cc.run.halted` |
| 5 | spans written from records, with `cc.obs_id` | step 4 | each span's `cc.obs_id` resolves to exactly one Observation |
| 6 | the progress sink and the tracer as subscribers | step 5 | removing a subscriber changes no record and no run result |
| 7 | the Data Foundation export, read from records and capture | step 6 | the export's row count equals the records, and a missing capture blocks completion |

Required capture is decided already: a missing capture blocks completion (`EVIDENCE_UNAVAILABLE`, [storage](storage.md#required-evidence-and-derived-views)). It is built at step 2 with the bridge, not deferred.

## M1 limits, stated plainly

- **Required raw capture is enabled for M1**, including Codex model turns and tool/process frames. Optional native sampled spans may be unavailable in Codex mode; that does not excuse absent mandatory execution evidence.
- **No token counts.** The Codex service reports none, so `cost.tokens` stays empty until a router or provider reports them.
- **Broker/process operations are captured and compared to declarations.** Denied undeclared calls fail the capsule. Any operation class without verifiable enforcement/capture remains explicitly unsupported, as the [environment profile](environment.md) and issue 54 state; absence of a span is not evidence of absence of effects.
