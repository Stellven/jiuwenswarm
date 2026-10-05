---
type: design
status: draft
version: 1
owner: muk
sources: [../m1/pipeline.md, deployment.md, planner.md, ../capsule/rsi-engine.md]
provides: [system.diagram_atlas]
consumes: [m1.run_plan, system.deployment, system.experimental_planner]
depends_on: [deployment.md, diagram.md, temporal.md, planner.md, ../m1/pipeline.md]
tags: [diagram, navigation, presentation]
---

# Diagram atlas: explain first, inspect next

These views summarize linked contracts. They do not define extra APIs or product scope. Each view shows one question; follow its owner links for field meanings and failures. This uses the context/container/component zoom pattern of the [C4 model](https://c4model.com/diagrams), with Mermaid flowcharts and sequence diagrams instead of a new diagram framework.

| Depth | Question | Read next |
|---|---|---|
| 1 Context | Who uses it, and what is deployed? | context below; [deployment](deployment.md) |
| 2 Components | Who may execute, judge, store or call Codex? | control view below; [modules](modules.md), [full typed map](diagram.md) |
| 3 Research data | What does each capability consume and produce? | [pipeline ports and plan fixture](../m1/pipeline.md), [capability design packets](../m1/capability-designs.md) |
| 4 Time and failure | What commits before the next step? | [temporal sequences](temporal.md), [failure stories](../stories/README.md) |

Start with [today's whole-system capsule views](overall-draft.md) for the fixed frontend and planned/frozen execution section. Use the [complete information-flow variants](information-flow.md) for current data/authority connections, filtered observability/RSI and failure recovery. Return here for deeper questions.

## 1. Context and deployment

```mermaid
flowchart TB
    U["Researcher: local CLI, Web or TUI"]
    H["Saurav's benchmark harness"]
    A["One Dockerized application"]
    C["Codex app-server: protected provider"]
    X["Scholarly services: brokered retrieval"]
    U <-->|"local run API"| A
    H <-->|"benchmark HTTP API"| A
    A -->|"authorized model turns"| C
    A -->|"bounded search requests"| X
```

The Codex app-server process belongs inside the application's trusted bridge boundary; the box above exposes its replaceable provider role. The benchmark harness is external. No capsule receives that harness's implementation or the bridge's credential volume.

## 2. Authority and trust components

```mermaid
flowchart LR
    E["Entry and supervisor"]
    L["Library: admitted versions"]
    R["Runner and broker"]
    W["Confined workload"]
    D["Canonical store"]
    G["Gate host"]
    E -->|"snapshot refs"| L
    E -->|"reserved dispatch"| R
    R -->|"pinned inputs"| W
    W -->|"output frames"| R
    R -->|"run evidence commit"| D
    E -->|"committed evidence refs"| G
    G -->|"Verification commit"| D
    D -->|"durable release authority"| E
```

Semantic assessment and inference expand the runner/Gate boundary separately so storage edges do not obscure model custody:

```mermaid
flowchart LR
    G["Gate host via runner"]
    V["Shared verifier"]
    R["Runner broker"]
    M["Protected Codex bridge"]
    G -->|"evidence and criteria"| V
    V -->|"assessment"| G
    V -->|"brokered turn"| M
    R -->|"scoped model request"| M
```

This is an authority map, not a filesystem permission grant. Workload processes cannot open the store. [Deployment](deployment.md) owns process identities, [environment](environment.md) owns IPC, [records](records.md) owns reservations, and [Gate host](../capsule/gate-host.md) owns the fold. The [current system map](diagram.md) expands the preparation/planning/execution boundaries without changing these boundaries.

## 3. Fixed preparation and planned execution spine

This generated view follows the [control-flow owner](../m1/control-flow.md): fixed intake/intent/requirements acceptance, planning, binding/freeze and governed DAG execution. [Information flow](information-flow.md) adds evidence, model, export and optional display branches. The [research contract baseline](research-contract-map.md) retains earlier detailed payload wiring for reconciliation, not current overall ordering.

<!-- generated:production-flow -->
```mermaid
flowchart TB
  USER["User or benchmark client"] -->|"request and declared resources"| IN["Intake: validate and snapshot"]
  IN -->|"normalized source inputs and context"| IC1["Intent compilation capsule"]
  IC1 -->|"output and captured evidence"| IG1["Intent Gate CC<br/>shared research.verifier"]
  IG1 -->|"accepted intent and source refs"| RC["Requirement compilation capsule calls"]
  RC -->|"each call immediately: output and evidence"| RG["Requirement Gate profiles<br/>shared research.verifier"]
  RG -->|"accepted task contract"| PLAN["Planner: propose a DAG of nodes and data bindings"]
  LIB["Reusable CC library snapshot"] -->|"capabilities, ports and exact versions"| PLAN
  PLAN -->|"candidate DAG"| VAL["Deterministic plan validator"]
  VAL -->|"valid plan"| BIND["Bind work CCs and declaration-derived Gate tests<br/>then freeze closure"]
  LIB -->|"pinned work and Gate implementations"| BIND
  BIND -->|"frozen bound DAG"| DIS["SwarmFlow dispatch and CC supervisor"]
  IN -->|"immutable resource refs"| DATA["Declared DAG input data"]
  RG -->|"accepted requirements"| DATA
  DATA -->|"validated input ports"| DIS
  DIS -->|"ready node and Binding"| RUN["Local CC runner inside Docker"]
  RUN -->|"execute bound capability"| CC["Bound CC executes task node locally<br/>restricted process"]
  CC -->|"output and evidence"| SAVE["Commit output and capture"]
  SAVE -->|"evidence and pinned criteria"| GATE["Node Gate: deterministic checks first<br/>then declaration-derived shared verifier test<br/>when deterministic checks pass"]
  GATE -->|"assessment"| COMMIT["Commit Verification and release"]
  COMMIT -->|"accepted output unlocks successors"| DIS
  COMMIT -->|"required terminal outputs accepted"| PUB["Delivery: ordinary processing and publication"]
  PUB -->|"processed report and artifact manifest"| VIEW["Result retrieval and user view"]
  VIEW -->|"authorized results"| USER
  GATE -->|"non-advancing result"| HALT["Halt entire run and preserve evidence<br/>no following or sibling capsule starts"]
  VAL -->|"invalid plan"| HALT
  COMMIT -->|"persistence failure"| HALT
  HALT -->|"explicit operator recovery"| REC["Reconcile committed state before any execution"]
  REC -->|"only recorded authority or approved unchanged-pin attempt"| DIS
  classDef cc fill:#FFF1D6,stroke:#B86E00,color:#172D45;
  classDef gate fill:#EEE4F6,stroke:#754A91,color:#172D45;
  class IC1,RC,CC cc;
  class IG1,RG,GATE gate;
```
<!-- /generated:production-flow -->

## 4. Three isolated execution tracks

```mermaid
flowchart TB
    E["Authenticated entry: freeze track and policy"]
    P["Production: fixed typed research plan"]
    R["Offline RSI: bounded candidate search"]
    X["Isolated experiment: allowlisted features"]
    O["Private fixture oracle"]
    A["Admission: integrity plus assurance provider"]
    L["Manual activation: future library snapshot"]
    V["Planner validator: structure and policy"]
    S["Supervisor: dispatch from committed authority"]
    E -->|"production config"| P
    E -->|"offline session request"| R
    E -->|"approved experiment profile"| X
    P -->|"validated requirements-planned frozen DAG"| S
    R -->|"private TrialRef and reserved quota"| O
    O -->|"aggregate results only"| R
    R -->|"promotable Candidate"| A
    A -->|"admitted inactive version"| L
    X -->|"complete proposal and exact pins"| V
    V -->|"persisted valid plan"| S
```

Activation is an explicit developer action; RSI cannot move the active alias. Experimental dispatch remains labelled and obeys the authority appropriate to its pinned study/profile. Approved Gate ablations never fabricate production PASS/release. [Experiments](experiments.md), [planner](planner.md) and [RSI engine](../capsule/rsi-engine.md) own those distinctions.

## 5. One step, including failed durable success

```mermaid
sequenceDiagram
    participant S as Supervisor
    participant R as Runner
    participant D as Canonical store
    participant G as Gate host
    S->>D: reserve dispatch and input refs
    S->>R: invoke exact frozen capability
    R->>S: output and required capture
    S->>D: commit Artifact and Observation
    S->>G: evaluate committed evidence
    G->>S: computed decision and evidence
    S->>D: commit Verification
    alt Verification commit fails
        S->>S: halt, no successor
    else Committed advancing PASS or PASS_WITH_KNOWN_LIMITATIONS
        S->>D: commit release
        alt Release commit fails
            S->>S: halt, no successor
        else Release committed
            S->>R: dispatch successor
        end
    else Nonpassing committed decision
        S->>S: halt for explicit review
    end
```

[Temporal flows](temporal.md) expands recovery, RSI and planner ordering. Diagram arrows to storage mean requests to an authorized writer; Gate host may publish through that writer. A computed success is never durable authorization.

## Diagram maintenance

Change the owning contract first. Update the affected view and deep diagram, then parse/render and inspect its labels, direction, trust placement and failure branches. Retain simple ASCII labels and standard shapes for renderer compatibility. A passing Mermaid parser proves syntax only; it cannot verify product semantics or isolation.
