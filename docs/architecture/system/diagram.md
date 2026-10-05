---
type: design
status: draft
version: 2
owner: muk
sources: [../m1/control-flow.md]
provides: [system.diagram]
consumes: [m1.control_flow]
depends_on: [../m1/control-flow.md, information-flow.md]
tags: [diagram, m1]
---

# System data and control connections

The [control-flow owner](../m1/control-flow.md) defines this sequence. The fixed SwarmFlow outer workflow gates intent and requirements before planning. The planner supplies a task DAG; validator/binder freeze exact work and Gate versions before local execution.

## Main path

<!-- generated:current-main -->
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
<!-- /generated:current-main -->

## Bound-node data and Gate ordering

<!-- generated:current-dag -->
```mermaid
flowchart TB
  INPUT["Validated task data"] --> N1["Node 1: task-specific bound CC use"]
  N1 --> S1["Commit output and evidence"]
  S1 --> G1["Gate: host checks then shared verifier<br/>RSI mutable components: 0"]
  G1 -->|"advancing result only"| R1["Commit advancing Verification and release"]
  R1 -->|"accepted typed output"| N2["Node 2: task-specific bound CC use"]
  R1 -->|"accepted typed output when required"| N3["Node 3: task-specific bound CC use"]
  N2 --> S2["Commit output and evidence"] --> G2["Gate: host checks then shared verifier<br/>RSI mutable components: 0"] -->|"advancing result only"| R2["Commit advancing Verification and release"]
  N3 --> S3["Commit output and evidence"] --> G3["Gate: host checks then shared verifier<br/>RSI mutable components: 0"] -->|"advancing result only"| R3["Commit advancing Verification and release"]
  R2 --> JOIN["Dependent join: required inputs accepted"]
  R3 --> JOIN
  JOIN --> END["Next governed node or ordinary delivery"]
  G1 -->|"failure"| STOP["Halt entire run<br/>no next or sibling capsule starts"]
  G2 -->|"failure"| STOP
  G3 -->|"failure"| STOP
```
<!-- /generated:current-dag -->

## Deeper contracts

- [Information-flow variants](information-flow.md): required evidence, output/export and offline RSI.
- [Temporal sequence](temporal.md): fixed frontend, proposal/freeze and per-node advancement.
- [Module map](modules.md), [integration](integration.md), [deployment](deployment.md): placement, SwarmFlow adapter and local process boundaries.
- [Runner](../capsule/runner.md), [Gate host](../capsule/gate-host.md), [shared verifier](../capsule/gate-capsules.md), [storage](storage.md): invocation, acceptance and persistence.
- [Research capabilities](../m1/capability-designs.md) remain capability design references; they are not a universal fixed overall chain. Intent/requirement/planner contract reconciliation remains explicit in the control-flow owner.
