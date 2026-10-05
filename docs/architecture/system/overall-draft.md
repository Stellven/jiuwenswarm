---
type: design
status: draft
version: 1
owner: muk
sources: [../m1/pipeline.md, modules.md, deployment.md, planner.md, ../capsule/rsi-engine.md]
provides: [system.overall_draft_view]
consumes: [m1.run_plan, system.deployment, system.experimental_planner]
depends_on: [../m1/pipeline.md, deployment.md, planner.md, modules.md]
tags: [diagram, presentation, m1]
---

# Today's architecture: whole system at capsule level

**Snapshot: 5 October 2026. Draft, not executed acceptance.** These are reading views of the [production plan](../m1/pipeline.md), [module map](modules.md) and [three tracks](experiments.md). They add no contracts. Start here for the shape of the system; use the [atlas](diagram-atlas.md) for deeper spatial/temporal views and the [typed map](diagram.md) for complete ports.

## Legend and dynamic placement

- **Blue CC boxes:** the twelve capability identities in the current inventory. The eight work CCs are fixed production nodes, not choices a production planner may omit. A halted run simply has not reached later nodes.
- **Pale boxes:** ordinary services, resources and control modules, not capsules. A label names a responsibility, not a separately deployed service.
- **Dashed border marked CONDITIONAL:** present in a particular run/session only when its approved track or declared caller needs it. This does not mean the capability is absent from the shipped library.
- **Solid arrows:** the primary data/control path. **Dashed arrows:** nested calls, evidence assessment or optional track participation. They do not grant filesystem/network permissions.
- **Experimental placement:** a validated isolated plan may include different permitted CCs and bindings from the admitted library. The diagram shows no universal experimental sequence; it cannot imply that an arbitrary subset is valid. Required inputs, dependencies, Gates and objective coverage still constrain placement.
- **Not drawn repeatedly:** Brief/intake/resource fan-in, individual logging writes and every model-call edge. Exact inputs remain in the pipeline owner. Required evidence capture is a shared responsibility, never optional observability. Local and scholarly retrieval are mandatory nested dependencies of production Search; dynamic experimental placement does not change that production rule.

## 1. Every capsule and its place in the research path

```mermaid
flowchart TB
    IN["Intake and source projection<br/>ordinary launcher helpers"]
    subgraph A["Research formation: fixed production order"]
        direction LR
        BR["CC: research.compile_brief"] -->|"research_brief"| SE["CC: research.search_ideas"]
        SE -->|"idea_set"| SC["CC: research.select_opportunity"]
        SC -->|"opportunity_card"| HY["CC: research.form_hypothesis"]
    end
    subgraph B["Scientific execution and report: fixed production order"]
        direction LR
        PO["CC: research.build_poc"] -->|"poc_bundle"| BM["CC: research.run_benchmark"]
        BM -->|"benchmark_payload"| EV["CC: research.evaluate_results"]
        EV -->|"evaluation_verdict"| RE["CC: research.write_report"]
    end
    subgraph RET["Nested retrieval: declared callers only"]
        direction LR
        LS["CC: op.local_search<br/>Search call: both per query"]
        SS["CC: op.scholarly_search<br/>Search call: both per query"]
        CS["CC: op.codesearch<br/>Hypothesis and POC code-location dependency"]
    end
    subgraph ACCEPT["One acceptance boundary reused after each work CC"]
        direction LR
        GH["Gate host<br/>deterministic checks and pinned criteria"]
        VE["CC: research.verifier<br/>applicable semantic assessment"]
        GH -->|"evidence and criteria via runner"| VE
        VE -->|"assessment, not release"| GH
    end
    PUB["Publication<br/>ordinary module: committed manifest"]
    MEAS["Trusted measurement and confined POC<br/>ordinary processes: baseline and treatment"]
    IN -->|"intake and source_text to compile_brief"| A
    A -->|"hypothesis_blueprint to build_poc"| B
    B -->|"Benchmark executes frozen protocol"| MEAS
    B -->|"research_report from write_report"| PUB
    B ~~~ RET
    RET ~~~ ACCEPT
    classDef cc fill:#E4F2F5,stroke:#087E8B,color:#172D45;
    classDef service fill:#F6F8FA,stroke:#A5B2BE,color:#172D45;
    classDef conditional fill:#E4F2F5,stroke:#087E8B,stroke-dasharray:5 4,color:#172D45;
    class BR,SE,SC,HY,PO,BM,EV,RE,LS,SS,CS,VE cc;
    class IN,GH,PUB,MEAS service;
```

Group arrows name their actual caller/consumer to preserve a readable layout: they are not all-to-all connections. Retrieval and acceptance boxes are supporting insets, not downstream stages; invisible layout links only position those insets. Their invocation points are named in each box and below. Search calls both local and scholarly operators per query, including when inputs/results are empty; Hypothesis and POC both pin CodeSearch to locate repository mechanisms. Benchmark owns scientific execution coordination. Every work node has its pinned Gate profile, even though the reusable acceptance boundary is drawn once. Verifier invocation depends on applicable criteria and deterministic-check success; its admission identity is shared, its criteria are stage-specific. The supervisor alone releases successors after durable Verification and release publication.

**Why this shape:** [Kubeflow typed component specifications](https://www.kubeflow.org/docs/components/pipelines/reference/component-spec/) motivate ports and reuse; [OPA policy/data separation](https://www.openpolicyagent.org/docs) motivates one Gate interface with criteria profiles. These are precedents, not runtime dependencies or proof of safety.

## 2. Whole application, alternate tracks and authority

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

- **Placement:** all application boxes belong to one deployable. Separate protected processes and the CLI/TUI/tmux runtime remain inside it. The harness, host browser/API clients and terminal attachment are outside; attachment does not move the TUI process onto the host. No runtime Docker socket or per-task container creation is implied.
- **Dynamic authority:** optional isolated plans choose permitted capsule versions/placement before execution. Validator acceptance and frozen bindings are mandatory; nodes cannot add live successors or perform automatic repair. RSI is a required M1 feature but a separate explicitly started session, not a node present in every production run.
- **Admission is not a runtime Gate:** Puppet allowlisting changes honest assurance, not test truth. RSI cannot move aliases, change the referee or release production work.
- **Experimental adapter placement:** the compiler prepares input before proposal; routing is inside an authorized model call; Code Mode runs in an isolated worker with result validation/Gates. The dashed feature box is a profile annotation, not a universal upstream plan node.
- **Observability:** required raw capture belongs to the canonical evidence path; UI traces and Data Foundation views derive from it. Individual record/event edges are deliberately omitted.
- **Failure:** failed Verification/release persistence means no successor. Unsupported confinement or missing mandatory evidence blocks the selecting path. Scientific negative results may still produce a valid report.

**Why this shape:** [Docker deployment](https://docs.docker.com/engine/containers/run/) plus protected internal processes; [Temporal durable execution](https://docs.temporal.io/workflow-execution) as the record-before-release precedent; [MLflow version/alias separation](https://mlflow.org/docs/latest/ml/model-registry/workflow/) as the admission/activation precedent. Follow [deployment](deployment.md), [lifecycle](lifecycle.md), [planner](planner.md), [RSI](../capsule/rsi-engine.md), [model authentication](model-auth.md) and [benchmark export](benchmark-export.md) for exact contracts.

For all 23 required production bindings and versions with observability/RSI hidden, use the [information-flow views](information-flow.md). The overview above deliberately summarizes those secondary inputs.

## Questions these views answer

- What is one deployment versus a capsule versus a protected process?
- Which capabilities always belong to production, which are nested calls, and which paths are conditional?
- Who chooses versions/placement, judges evidence, owns credentials and releases the next node?
- Where do RSI candidates enter admission and human activation?
- Where do local users and benchmarking connect, and where does the final evidence leave?

For exact fields, all secondary fan-in and timeout/recovery conditions, follow the owning contracts rather than infer missing edges from this simplified view. Platform isolation and execution acceptance remain [implementation obligations](../open-issues.md).
