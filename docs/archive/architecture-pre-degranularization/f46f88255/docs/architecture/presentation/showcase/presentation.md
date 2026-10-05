# System

[Start here](README.md) · Specified design · Runtime validation pending

## Deployment and component roles

- **Dockerized modular monolith:** one Linux application image, shared configuration and versioned internal interfaces. Separate subprocesses enforce trust boundaries; a component box does not imply a separately deployed service. See [deployment](../../system/deployment.md) and [module map](../../system/modules.md).
- **Capability capsule (CC):** admitted, versioned capability with a Declaration, typed ports, dependencies, effects and checks. It performs work; it does not release the next workflow node. See [Declaration](../../capsule/fields.md).
- **Workflow node:** a plan position binding one pinned capability to input references, budgets and a Gate profile. Multiple nodes can use one capability. See [run plan](../../types/run-plan.md).
- **Ordinary module:** control or deterministic helper without independent capsule admission. Examples: supervisor, extraction, resource freezing, numeric arithmetic, plan validator and publisher. See [pipeline](../../m1/pipeline.md).
- **Host boundary:** browser and benchmark client use the application API. CLI/TUI/tmux execute inside the workstation environment; host terminal attachment is an access path. See [workstation](../../system/workstation.md).

## Three tracks

- **Production:** fixed research plan, static Codex route, real Gates, durable records, local report publication. This is the first integration target.
- **Offline RSI:** isolated candidate changes and private evaluation; no live production changes or automatic activation.
- **Isolated experiments:** only whitelisted planning, routing, intention-compilation, Code Mode, alternate semantic verifier and approved component/Gate ablation paths. The planner is an orchestration service, not a CC. Conditional participation does not make required production stages optional.
- Scope and promotion boundaries are owned by [experimental tracks](../../system/experiments.md). Fusion, composite capsules, live replanning and unrestricted delegation are outside current acceptance.

## Spatial view

Generated from [overall draft](../../system/overall-draft.md). Arrows summarize placement and interfaces, not filesystem permissions. Required capture is present even where its edges are omitted. Host terminal attachment reaches the in-container CLI/TUI/tmux environment.

<!-- generated:showcase-system -->
```mermaid
flowchart TB
    USER["Researcher<br/>host browser/API or terminal attachment"]
    HAR["External benchmark harness<br/>authenticated local HTTP"]
    subgraph APP["One Dockerized modular monolith"]
        direction TB
        ENTRY["Shared entry and configuration<br/>container CLI/TUI, pin task and track"]
        PLAN["CONDITIONAL: isolated planner<br/>ordinary controller, not a CC"]
        EXP["CONDITIONAL: allowed experimental adapters<br/>compiler, routing or confined Code Mode"]
        VALID["Deterministic plan validation and freeze<br/>production template or permitted proposal"]
        SUP["Supervisor<br/>reserve, dispatch, halt and explicit recovery"]
        RUN["CC runner and broker<br/>executes the capsule view above"]
        LIB["Admitted library snapshot<br/>versions, profiles and exact pins"]
        MODEL["Protected model bridge and Codex<br/>private persistent login"]
        GATE["Gate host and shared verifier<br/>decision evidence, not dispatch authority"]
        STORE["Canonical store and required capture<br/>Artifacts, Observations, Verifications, releases"]
        RSI["CONDITIONAL session: required offline RSI<br/>bounded mutations, never live replanning"]
        ORACLE["Private fixture oracle<br/>aggregate results, protected answers"]
        ADMIT["Admission<br/>tested evidence or Puppet exempt assurance"]
        ACT["Explicit human activation<br/>future snapshots only"]
        OUT["Sealed report and benchmark export<br/>authorized manifest-based retrieval"]
        ENTRY -.->|"isolated profile only"| PLAN
        ENTRY -.->|"whitelisted feature profile"| EXP
        ENTRY -->|"production fixed template"| VALID
        PLAN -->|"complete typed proposal"| VALID
        LIB -->|"admitted versions and profiles"| VALID
        VALID -->|"committed valid plan and Bindings"| SUP
        SUP -->|"reserved calls"| RUN
        RUN -->|"authorized turns"| MODEL
        PLAN -.->|"reserved proposal turn"| MODEL
        SUP -->|"committed work evidence"| GATE
        GATE -->|"Verification through supervisor writer"| STORE
        SUP -->|"required capture and durable release"| STORE
        STORE -->|"sealed public evidence"| OUT
        ENTRY -.->|"offline session request"| RSI
        RSI -->|"private trials"| ORACLE
        ORACLE -->|"aggregate comparison"| RSI
        RSI -->|"eligible Candidate"| ADMIT
        ADMIT -->|"admitted inactive RSI child"| ACT
        ACT -->|"human-selected version"| LIB
    end
    USER --> ENTRY
    HAR --> ENTRY
    classDef ordinary fill:#F6F8FA,stroke:#A5B2BE,color:#172D45;
    classDef conditional fill:#FFF4DC,stroke:#A87B24,stroke-dasharray:5 4,color:#172D45;
    classDef protected fill:#E4F2F5,stroke:#087E8B,color:#172D45;
    class ENTRY,VALID,SUP,RUN,LIB,GATE,STORE,ADMIT,ACT,OUT ordinary;
    class PLAN,EXP,RSI conditional;
    class MODEL,ORACLE protected;
```
<!-- /generated:showcase-system -->

## Why these boundaries

- One deployment keeps M1 operation small; restricted subprocesses retain distinct credential and code identities. The borrowed container/process patterns and replacement points are recorded in [deployment](../../system/deployment.md) and [confinement](../../capsule/process-boundary.md).
- Typed capabilities separate reusable behavior from scheduling. Component-specification precedent and the minimum-boundary rationale are recorded in [pipeline](../../m1/pipeline.md).
- Existing OpenJiuwen integration stays behind adapters. [Reuse audit](../../system/reuse-audit-2026-10-05.md) records source pins and actual symbols; [integration](../../system/integration.md) separates reused behavior from new work.

[Next: capsules](capsules.md)
