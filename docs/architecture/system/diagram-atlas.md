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

Start with [today's whole-system capsule views](overall-draft.md) to see all twelve CCs and conditional track participation together. Use the [complete information-flow variants](information-flow.md) for all required bindings, filtered observability/RSI and failure recovery. Return here for deeper questions.

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

This is an authority map, not a filesystem permission grant. Workload processes cannot open the store. [Deployment](deployment.md) owns process identities, [environment](environment.md) owns IPC, [records](records.md) owns reservations, and [Gate host](../capsule/gate-host.md) owns the fold. The [full typed map](diagram.md) expands implementation modules and payload names without changing these boundaries.

## 3. Production data spine

This generated view shows the primary successive output at each stage. Brief/intake/evidence fan-in and exact complete input sets are owned by the [pipeline table and plan fixture](../m1/pipeline.md); the [deep typed map](diagram.md) shows all those edges. Each research transition also includes its Gate/commit/release sequence below. This view is regenerated from the owning plan/table, never edited independently.

<!-- generated:production-flow -->
```mermaid
flowchart TB
    IN["Launcher: committed intake and source_text"]
    P0["requirement: research.compile_brief"]
    IN -->|"intake and source_text"| P0
    P1["search: research.search_ideas"]
    P0 -->|"research_brief"| P1
    P2["screening: research.select_opportunity"]
    P1 -->|"idea_set"| P2
    P3["hypothesis: research.form_hypothesis"]
    P2 -->|"opportunity_card"| P3
    P4["poc: research.build_poc"]
    P3 -->|"hypothesis_blueprint"| P4
    P5["benchmark: research.run_benchmark"]
    P4 -->|"poc_bundle"| P5
    P6["evaluation: research.evaluate_results"]
    P5 -->|"benchmark_payload"| P6
    P7["report: research.write_report"]
    P6 -->|"evaluation_verdict"| P7
    PUB["Publisher: committed report manifest"]
    P7 -->|"research_report"| PUB
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
    P -->|"validated fixed plan"| S
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
    else Committed PASS
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
