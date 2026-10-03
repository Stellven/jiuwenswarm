---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-02.txt, lifecycle.md, ../m1/pipeline.md]
provides: [system.temporal_flow]
consumes: [m1.run_plan, system.record_api]
depends_on: [lifecycle.md, records.md, ../capsule/gate-host.md, ../capsule/rsi-engine.md, planner.md, benchmark-export.md]
tags: [diagram, control, temporal]
---

# Temporal flows and durable authority

[Spatial diagram](diagram.md) maps modules and typed connections. These diagrams map order and persistence; arrows do not grant authority. [Lifecycle](lifecycle.md) owns recovery, [pipeline](../m1/pipeline.md) owns stage order, and [records](records.md) owns durable identities.

## One governed step

The deployment order is image/volume validation → identity bootstrap → store recovery → model bridge → security/fixture doctor → runner → HTTP readiness. This is one container's internal startup, owned by [deployment](deployment.md). The benchmark harness obtains an approved profile, submits a request, polls the durable handle, requests an export after completion/halt/abort, and retrieves its manifest-listed artifacts via the [HTTP API](benchmark-export.md#docker-http-transport). A transport disconnect never repeats accepted research work.

```mermaid
sequenceDiagram
    participant U as Local user
    participant S as Supervisor
    participant D as Durable store
    participant R as CC runner
    participant G as Gate host
    participant V as Shared verifier
    U->>S: launch intake/config/request
    S->>S: doctor, validate plan, resolve active snapshot
    S->>D: freeze bindings + run-start manifest
    loop Eight production research steps
        S->>D: reserve dispatch identity before effects
        S->>R: call pinned capability and inputs
        R->>D: supervisor commits outputs, capture, Observation
        R-->>S: committed Observation reference
        S->>G: gate(exact Observation)
        G->>G: deterministic checks from pinned profile
        opt Applicable semantic criteria
            G->>V: evidence bundle + independent criteria
            V-->>G: verifier_assessment
        end
        G->>D: commit Verification
        alt Passing and durable
            G-->>S: passing Verification reference
            S->>D: commit release for same dispatch
            S->>S: authorize successor from committed release
        else Failure, unknown or write error
            S->>D: preserve evidence and halt if store available
            S-->>U: review requirement or headless terminal halt
        end
    end
    S->>D: publish report/artifact manifest after report release
    S-->>U: retrievable immutable references
```

The runner's store arrows are requests to the sole trusted writer, not direct child filesystem access. A passing in-memory decision cannot release work. A scientific negative/inconclusive result continues when its infrastructure Gate passes; integrity failure stops advancement.

## Restart after interruption

```mermaid
sequenceDiagram
    participant U as Local user
    participant S as Supervisor
    participant D as Durable store
    S->>D: read dispatch, output, Verification, release and capture
    alt Release already committed
        S->>S: advance without repeating work/model calls
    else Output committed but decision/release incomplete
        S->>S: repair missing Gate persistence/control record
        S->>D: commit matching decision/release if checks complete
    else Effects uncertain or genuine failure
        S-->>U: preserved evidence + explicit review
        U->>S: attributable restart/abort decision
        S->>D: new attempt reservation under same run/step
    end
```

No crash proves that an effect did not happen. Raw model response and gate-call reservations determine whether missing persistence can be repaired without another call. If evidence is insufficient, recovery requires explicit action and a new attempt. All store failure paths return truthful diagnostics without claiming a durable halt was written.

## Offline RSI and activation

```mermaid
sequenceDiagram
    participant C as Offline controller
    participant O as Private oracle
    participant K as Human custodian
    participant A as Admission
    participant L as Library writer
    participant U as Developer
    C->>C: pin target, parent, mutation scope and model
    C->>O: open protected session
    loop Bounded running-phase proposal requests
        C->>O: private TrialRef + request identity
        O->>O: durably reserve session/lifetime quota
        O->>O: confined candidate against private fixtures
        O-->>C: aggregate-only result
        C->>C: persist attempt and lineage
    end
    C->>O: close_session pins incumbent and ablation schedule
    C->>O: bounded closing ablations then finish_close
    O-->>K: committed closed_session_ref
    K->>O: evaluate_final once using closed reference
    O-->>C: promotable or no_candidate aggregate evidence
    C->>A: publish and submit Candidate only if promotable
    A->>A: mandatory integrity + chosen admission provider
    A-->>L: admitted inactive version and honest assurance
    U->>L: explicit compare-and-set activation
    L->>L: durable activation record / future snapshot
```

Puppet admission may grant exempt standing after mandatory integrity; it cannot produce a runtime Gate PASS or activate a candidate. Existing run pins survive later activation. Query details and separate final budget live in [oracle](../capsule/fixture-oracle.md).

The isolated planner and benchmark export have their own ordered sequences in [planner](planner.md) and [benchmark export](benchmark-export.md). Their manifests expose track and deviations; they cannot silently become production acceptance.
