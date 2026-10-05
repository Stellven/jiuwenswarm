---
id: arch.flow-variants
type: generated
level: detail
status: draft
version: 1
provides: [arch.flow.variants]
depends_on: [flow.md]
prd: []
prd_note: generated views of the flow graph; the PRD clauses are on flow.md
tags: [flow, diagram, generated]
---

# Flow variants: smaller views of the same graph

> Answers: What does the flow look like without observability, without RSI, and with core nodes only?

These three diagrams are **generated** from the graph source in [flow](flow.md#graph-source-edit-here-then-regenerate) by `python _tools/flow_views.py`. Never edit the generated block. The full view is on [flow](flow.md).

## Without observability

Observability branches are removed from the drawing only. Required capture and durable records still happen. Hiding a display never disables evidence.

<!-- generated:flow-no-observability -->
```mermaid
flowchart TB
  USER["User or benchmark client"] -->|"request and declared resources"| N_intake["N_intake: validate and snapshot resources"]
  N_intake -->|"normalized source text and context"| N_intent["N_intent: intent CC<br/>research.compile_intent"]
  N_intent -->|"output and captured evidence"| G_intent["G_intent: Gate<br/>research.verifier"]
  G_intent -->|"accepted intent"| N_req["N_req: requirement CC<br/>research.compile_brief"]
  N_req -->|"output and evidence"| G_req["G_req: Gate<br/>research.verifier"]
  G_req -->|"accepted requirements"| N_plan["N_plan: planner service, not a CC<br/>emits the fixed-template DAG and data bindings"]
  LIB["Library snapshot: admitted CC versions"] -->|"capabilities, ports, versions"| N_plan
  N_plan -->|"candidate DAG"| N_validate["N_validate: check whole graph"]
  N_validate -->|"valid plan"| N_bind["N_bind: bind CC and Gate per node, freeze"]
  LIB -->|"pinned implementations"| N_bind
  N_bind -->|"frozen bound DAG"| N_dispatch["N_dispatch: SwarmFlow and supervisor"]
  N_intake -->|"resource refs"| DATA["Declared DAG input data"]
  G_req -->|"accepted requirements"| DATA
  DATA -->|"validated input ports"| N_dispatch
  N_dispatch -->|"ready node and Binding"| N_run["N_run: runner, local, restricted process"]
  N_run -->|"execute pinned CC"| N_node["N_node: task node (planned, frozen)"]
  N_node -->|"output and evidence"| SAVE["Commit output and capture"]
  SAVE -->|"evidence and pinned criteria"| G_node["G_node: Gate right after the node<br/>deterministic checks, then verifier test"]
  G_node -->|"assessment"| COMMIT["Commit Verification and release"]
  COMMIT -->|"release unlocks successors"| N_dispatch
  COMMIT -->|"terminal outputs accepted"| N_deliver["N_deliver: delivery, ordinary code"]
  N_deliver -->|"processed report and manifest"| VIEW["Result retrieval and user view"]
  VIEW -->|"authorized results"| USER
  G_node -->|"not advancing"| HALT["HALT: no following or sibling capsule starts"]
  N_validate -->|"invalid plan"| HALT
  COMMIT -->|"persistence failure"| HALT
  HALT -->|"explicit human recovery"| REC["Reconcile committed state"]
  REC -->|"recorded authority only"| N_dispatch
  STORE["Store: required capture and durable records"]
  MODEL["Model bridge: wraps Codex, static route"]
  N_intent -->|"required capture"| STORE
  N_req -->|"required capture"| STORE
  SAVE -->|"immutable output and capture"| STORE
  COMMIT -->|"Verification then release, one writer"| STORE
  STORE -->|"only committed authority is replayed"| REC
  N_run -->|"scoped model requests"| MODEL
  MODEL -->|"captured reply or typed failure"| N_run
  RSI["Offline RSI: eligible work CCs only"]
  ORACLE["Private fixture oracle"]
  ADMIT["Admission: integrity, then tested or Puppet provider"]
  ACT["Explicit human activation"]
  USER -.->|"separate offline session"| RSI
  LIB -->|"frozen parent, Gate CCs excluded"| RSI
  RSI -->|"private evaluation"| ORACLE
  ORACLE -->|"aggregates only"| RSI
  RSI -->|"Candidate, no hidden fixtures"| ADMIT
  ADMIT -->|"admitted, inactive"| ACT
  USER -->|"activation command"| ACT
  ACT -->|"future snapshots only"| LIB
  classDef cc fill:#FFF1D6,stroke:#B86E00,color:#172D45;
  classDef gate fill:#EEE4F6,stroke:#754A91,color:#172D45;
  classDef halt fill:#FBE3E3,stroke:#B03030,color:#172D45;
  class N_intent,N_req,N_node cc;
  class G_intent,G_req,G_node gate;
  class HALT halt;
```
<!-- /generated:flow-no-observability -->

## Without RSI

Production flow alone. [RSI](rsi.md#term-rsi) never [runs](system/lifecycle.md#term-run) inside it. [RSI](rsi.md) is the separate area.

<!-- generated:flow-no-rsi -->
```mermaid
flowchart TB
  USER["User or benchmark client"] -->|"request and declared resources"| N_intake["N_intake: validate and snapshot resources"]
  N_intake -->|"normalized source text and context"| N_intent["N_intent: intent CC<br/>research.compile_intent"]
  N_intent -->|"output and captured evidence"| G_intent["G_intent: Gate<br/>research.verifier"]
  G_intent -->|"accepted intent"| N_req["N_req: requirement CC<br/>research.compile_brief"]
  N_req -->|"output and evidence"| G_req["G_req: Gate<br/>research.verifier"]
  G_req -->|"accepted requirements"| N_plan["N_plan: planner service, not a CC<br/>emits the fixed-template DAG and data bindings"]
  LIB["Library snapshot: admitted CC versions"] -->|"capabilities, ports, versions"| N_plan
  N_plan -->|"candidate DAG"| N_validate["N_validate: check whole graph"]
  N_validate -->|"valid plan"| N_bind["N_bind: bind CC and Gate per node, freeze"]
  LIB -->|"pinned implementations"| N_bind
  N_bind -->|"frozen bound DAG"| N_dispatch["N_dispatch: SwarmFlow and supervisor"]
  N_intake -->|"resource refs"| DATA["Declared DAG input data"]
  G_req -->|"accepted requirements"| DATA
  DATA -->|"validated input ports"| N_dispatch
  N_dispatch -->|"ready node and Binding"| N_run["N_run: runner, local, restricted process"]
  N_run -->|"execute pinned CC"| N_node["N_node: task node (planned, frozen)"]
  N_node -->|"output and evidence"| SAVE["Commit output and capture"]
  SAVE -->|"evidence and pinned criteria"| G_node["G_node: Gate right after the node<br/>deterministic checks, then verifier test"]
  G_node -->|"assessment"| COMMIT["Commit Verification and release"]
  COMMIT -->|"release unlocks successors"| N_dispatch
  COMMIT -->|"terminal outputs accepted"| N_deliver["N_deliver: delivery, ordinary code"]
  N_deliver -->|"processed report and manifest"| VIEW["Result retrieval and user view"]
  VIEW -->|"authorized results"| USER
  G_node -->|"not advancing"| HALT["HALT: no following or sibling capsule starts"]
  N_validate -->|"invalid plan"| HALT
  COMMIT -->|"persistence failure"| HALT
  HALT -->|"explicit human recovery"| REC["Reconcile committed state"]
  REC -->|"recorded authority only"| N_dispatch
  STORE["Store: required capture and durable records"]
  MODEL["Model bridge: wraps Codex, static route"]
  N_intent -->|"required capture"| STORE
  N_req -->|"required capture"| STORE
  SAVE -->|"immutable output and capture"| STORE
  COMMIT -->|"Verification then release, one writer"| STORE
  STORE -->|"only committed authority is replayed"| REC
  N_run -->|"scoped model requests"| MODEL
  MODEL -->|"captured reply or typed failure"| N_run
  VIEWS["Derived telemetry, UI progress, run exports"]
  STORE -.->|"derive views, no authority"| VIEWS
  VIEWS -.->|"optional displays"| VIEW
  classDef cc fill:#FFF1D6,stroke:#B86E00,color:#172D45;
  classDef gate fill:#EEE4F6,stroke:#754A91,color:#172D45;
  classDef halt fill:#FBE3E3,stroke:#B03030,color:#172D45;
  class N_intent,N_req,N_node cc;
  class G_intent,G_req,G_node gate;
  class HALT halt;
```
<!-- /generated:flow-no-rsi -->

## Core (neither)

The smallest picture: request in, governed DAG, answer out. Store, [halts](system/lifecycle.md#term-halt) and recovery are left out of the drawing only.

<!-- generated:flow-core -->
```mermaid
flowchart TB
  USER["User or benchmark client"] -->|"request and declared resources"| N_intake["N_intake: validate and snapshot resources"]
  N_intake -->|"normalized source text and context"| N_intent["N_intent: intent CC<br/>research.compile_intent"]
  N_intent -->|"output and captured evidence"| G_intent["G_intent: Gate<br/>research.verifier"]
  G_intent -->|"accepted intent"| N_req["N_req: requirement CC<br/>research.compile_brief"]
  N_req -->|"output and evidence"| G_req["G_req: Gate<br/>research.verifier"]
  G_req -->|"accepted requirements"| N_plan["N_plan: planner service, not a CC<br/>emits the fixed-template DAG and data bindings"]
  LIB["Library snapshot: admitted CC versions"] -->|"capabilities, ports, versions"| N_plan
  N_plan -->|"candidate DAG"| N_validate["N_validate: check whole graph"]
  N_validate -->|"valid plan"| N_bind["N_bind: bind CC and Gate per node, freeze"]
  LIB -->|"pinned implementations"| N_bind
  N_bind -->|"frozen bound DAG"| N_dispatch["N_dispatch: SwarmFlow and supervisor"]
  N_intake -->|"resource refs"| DATA["Declared DAG input data"]
  G_req -->|"accepted requirements"| DATA
  DATA -->|"validated input ports"| N_dispatch
  N_dispatch -->|"ready node and Binding"| N_run["N_run: runner, local, restricted process"]
  N_run -->|"execute pinned CC"| N_node["N_node: task node (planned, frozen)"]
  N_node -->|"output and evidence"| SAVE["Commit output and capture"]
  SAVE -->|"evidence and pinned criteria"| G_node["G_node: Gate right after the node<br/>deterministic checks, then verifier test"]
  G_node -->|"assessment"| COMMIT["Commit Verification and release"]
  COMMIT -->|"release unlocks successors"| N_dispatch
  COMMIT -->|"terminal outputs accepted"| N_deliver["N_deliver: delivery, ordinary code"]
  N_deliver -->|"processed report and manifest"| VIEW["Result retrieval and user view"]
  VIEW -->|"authorized results"| USER
  G_node -->|"not advancing"| HALT["HALT: no following or sibling capsule starts"]
  N_validate -->|"invalid plan"| HALT
  COMMIT -->|"persistence failure"| HALT
  classDef cc fill:#FFF1D6,stroke:#B86E00,color:#172D45;
  classDef gate fill:#EEE4F6,stroke:#754A91,color:#172D45;
  classDef halt fill:#FBE3E3,stroke:#B03030,color:#172D45;
  class N_intent,N_req,N_node cc;
  class G_intent,G_req,G_node gate;
  class HALT halt;
```
<!-- /generated:flow-core -->
