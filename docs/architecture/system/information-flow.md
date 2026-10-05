---
type: design
status: draft
version: 2
owner: muk
sources: [../m1/control-flow.md, lifecycle.md, storage.md]
provides: [system.information_flow_views]
consumes: [m1.control_flow, system.record_api]
depends_on: [../m1/control-flow.md, lifecycle.md, storage.md]
tags: [diagram, data, m1]
---

# Information flow: fixed preparation and planned execution

The [M1 control-flow owner](../m1/control-flow.md) defines the main path: intake -> intent capsules/Gates -> requirement capsules/Gates -> planner -> validation/binding/freeze -> local DAG execution -> ordinary Delivery processing and user retrieval.

SwarmFlow supplies required fixed outer positions. Requirements determine the task DAG, which becomes fixed before execution. Every work capsule enters its Gate boundary before its output can unlock consumers. A failed Gate halts further capsule dispatch for the whole run. Gate call sites reuse one `research.verifier` identity through criteria profiles, with zero RSI-mutable components.

## Reading these views

- Arrows show logical data and authority dependencies, not unrestricted process access. Inputs/evidence resolve through authorized references.
- All four views preserve the fixed preparation path, planner boundary, bound local execution, Gates, durable authority and ordinary Delivery/output path.
- Observability filtering hides derived display branches only. Required capture and records remain. RSI filtering hides the separate offline session only; it does not remove its M1 scope.
- The previous 23-binding research example is preserved in the [archived fixed-chain map](../archive/information-flow-fixed-research-2026-10-05.md). It does not define this overall flow. Concrete intent/requirement/planner wire contracts remain in connected revision; diagram labels are logical data roles, not newly released schemas.
- [Storage](storage.md), [Gate host](../capsule/gate-host.md), [shared verifier](../capsule/gate-capsules.md), [Codex bridge](model-auth.md) and [benchmark export](benchmark-export.md) own enforcement and persistence details.

## 1. Full system with derived views and offline RSI

<!-- generated:information-full -->
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
  HAR["Benchmark client: authenticated local API"] -->|"task, config and request identity"| IN
  STORE["Canonical store: required capture and durable records"]
  MODEL["Protected Codex bridge: private credential owner"]
  EXPORT["Sealed export and authorized manifest retrieval"]
  POLICY["Pinned configuration, budgets and policy"]
  POLICY -->|"permitted planning limits"| PLAN
  POLICY -->|"frozen enforcement inputs"| BIND
  PLAN -->|"authorized bounded proposal request"| MODEL
  RUN -->|"authorized work and verifier requests"| MODEL
  MODEL -->|"captured proposal or typed failure"| PLAN
  MODEL -->|"captured result or typed failure"| RUN
  IC1 -->|"output and required capture via trusted writer"| STORE
  RC -->|"requirements and required capture"| STORE
  IG1 -->|"frontend Verification and release via supervisor"| STORE
  RG -->|"requirement Verification and release"| STORE
  SAVE -->|"immutable output and required raw capture"| STORE
  COMMIT -->|"Verification then release: one trusted writer"| STORE
  STORE -->|"only committed authority is replayed"| REC
  PUB -->|"processed outputs and committed manifest"| STORE
  STORE -->|"authorized sealed public evidence"| EXPORT
  EXPORT -->|"manifest-scoped data"| VIEW
  EXPORT -->|"correlated benchmark evidence"| HAR
  VIEWS["Derived telemetry, UI progress and Data Foundation views"]
  STORE -.->|"derive views without changing authority"| VIEWS
  VIEWS -.->|"optional displays"| VIEW
  RSI["Offline RSI: eligible work capsules only"]
  ORACLE["Private fixture oracle"]
  ADMIT["Admission: integrity plus tested or Puppet policy"]
  ACT["Explicit human activation"]
  USER -.->|"separate offline session"| RSI
  LIB -->|"frozen parent and zero Gate mutation permission"| RSI
  RSI -->|"reserved private evaluation"| ORACLE
  ORACLE -->|"aggregate results, no hidden answers"| RSI
  RSI -->|"public Candidate without hidden fixtures"| ADMIT
  ADMIT -->|"admitted inactive candidate"| ACT
  USER -->|"explicit activation command"| ACT
  ACT -->|"future snapshots only"| LIB
```
<!-- /generated:information-full -->

## 2. Without derived observability

<!-- generated:information-no-observability -->
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
  HAR["Benchmark client: authenticated local API"] -->|"task, config and request identity"| IN
  STORE["Canonical store: required capture and durable records"]
  MODEL["Protected Codex bridge: private credential owner"]
  EXPORT["Sealed export and authorized manifest retrieval"]
  POLICY["Pinned configuration, budgets and policy"]
  POLICY -->|"permitted planning limits"| PLAN
  POLICY -->|"frozen enforcement inputs"| BIND
  PLAN -->|"authorized bounded proposal request"| MODEL
  RUN -->|"authorized work and verifier requests"| MODEL
  MODEL -->|"captured proposal or typed failure"| PLAN
  MODEL -->|"captured result or typed failure"| RUN
  IC1 -->|"output and required capture via trusted writer"| STORE
  RC -->|"requirements and required capture"| STORE
  IG1 -->|"frontend Verification and release via supervisor"| STORE
  RG -->|"requirement Verification and release"| STORE
  SAVE -->|"immutable output and required raw capture"| STORE
  COMMIT -->|"Verification then release: one trusted writer"| STORE
  STORE -->|"only committed authority is replayed"| REC
  PUB -->|"processed outputs and committed manifest"| STORE
  STORE -->|"authorized sealed public evidence"| EXPORT
  EXPORT -->|"manifest-scoped data"| VIEW
  EXPORT -->|"correlated benchmark evidence"| HAR
  RSI["Offline RSI: eligible work capsules only"]
  ORACLE["Private fixture oracle"]
  ADMIT["Admission: integrity plus tested or Puppet policy"]
  ACT["Explicit human activation"]
  USER -.->|"separate offline session"| RSI
  LIB -->|"frozen parent and zero Gate mutation permission"| RSI
  RSI -->|"reserved private evaluation"| ORACLE
  ORACLE -->|"aggregate results, no hidden answers"| RSI
  RSI -->|"public Candidate without hidden fixtures"| ADMIT
  ADMIT -->|"admitted inactive candidate"| ACT
  USER -->|"explicit activation command"| ACT
  ACT -->|"future snapshots only"| LIB
```
<!-- /generated:information-no-observability -->

## 3. Without the offline RSI branch

<!-- generated:information-no-rsi -->
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
  HAR["Benchmark client: authenticated local API"] -->|"task, config and request identity"| IN
  STORE["Canonical store: required capture and durable records"]
  MODEL["Protected Codex bridge: private credential owner"]
  EXPORT["Sealed export and authorized manifest retrieval"]
  POLICY["Pinned configuration, budgets and policy"]
  POLICY -->|"permitted planning limits"| PLAN
  POLICY -->|"frozen enforcement inputs"| BIND
  PLAN -->|"authorized bounded proposal request"| MODEL
  RUN -->|"authorized work and verifier requests"| MODEL
  MODEL -->|"captured proposal or typed failure"| PLAN
  MODEL -->|"captured result or typed failure"| RUN
  IC1 -->|"output and required capture via trusted writer"| STORE
  RC -->|"requirements and required capture"| STORE
  IG1 -->|"frontend Verification and release via supervisor"| STORE
  RG -->|"requirement Verification and release"| STORE
  SAVE -->|"immutable output and required raw capture"| STORE
  COMMIT -->|"Verification then release: one trusted writer"| STORE
  STORE -->|"only committed authority is replayed"| REC
  PUB -->|"processed outputs and committed manifest"| STORE
  STORE -->|"authorized sealed public evidence"| EXPORT
  EXPORT -->|"manifest-scoped data"| VIEW
  EXPORT -->|"correlated benchmark evidence"| HAR
  VIEWS["Derived telemetry, UI progress and Data Foundation views"]
  STORE -.->|"derive views without changing authority"| VIEWS
  VIEWS -.->|"optional displays"| VIEW
```
<!-- /generated:information-no-rsi -->

## 4. Core request-to-DAG flow

<!-- generated:information-core -->
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
  HAR["Benchmark client: authenticated local API"] -->|"task, config and request identity"| IN
  STORE["Canonical store: required capture and durable records"]
  MODEL["Protected Codex bridge: private credential owner"]
  EXPORT["Sealed export and authorized manifest retrieval"]
  POLICY["Pinned configuration, budgets and policy"]
  POLICY -->|"permitted planning limits"| PLAN
  POLICY -->|"frozen enforcement inputs"| BIND
  PLAN -->|"authorized bounded proposal request"| MODEL
  RUN -->|"authorized work and verifier requests"| MODEL
  MODEL -->|"captured proposal or typed failure"| PLAN
  MODEL -->|"captured result or typed failure"| RUN
  IC1 -->|"output and required capture via trusted writer"| STORE
  RC -->|"requirements and required capture"| STORE
  IG1 -->|"frontend Verification and release via supervisor"| STORE
  RG -->|"requirement Verification and release"| STORE
  SAVE -->|"immutable output and required raw capture"| STORE
  COMMIT -->|"Verification then release: one trusted writer"| STORE
  STORE -->|"only committed authority is replayed"| REC
  PUB -->|"processed outputs and committed manifest"| STORE
  STORE -->|"authorized sealed public evidence"| EXPORT
  EXPORT -->|"manifest-scoped data"| VIEW
  EXPORT -->|"correlated benchmark evidence"| HAR
```
<!-- /generated:information-core -->

## 5. Gate persistence, halt and recovery

This per-call temporal view applies to intent, requirements and DAG work. It does not authorize bypassing frontend Gates or replanning a live DAG.

```mermaid
flowchart TB
    START["Validate intake, profiles, references and isolation"]
    CALL["Reserve dispatch and invoke pinned CC"]
    SAVE["Persist output, Observation and required capture"]
    GATE["Evaluate deterministic checks and applicable verifier criteria"]
    VSAVE["Persist Verification"]
    PASS{"Committed routing_action ADVANCE?<br/>PASS or PASS_WITH_KNOWN_LIMITATIONS"}
    RELEASE["Persist release for exact run, step and attempt"]
    NEXT["Dispatch successor from committed authority"]
    HALT["Halt: preserve partial evidence and missing-record reason"]
    HUMAN["Explicit human recovery or new run"]
    REC["Reconcile committed records before any re-execution"]
    START -->|"valid and supported"| CALL
    CALL -->|"work complete"| SAVE
    SAVE -->|"publication committed"| GATE
    GATE -->|"computed decision only"| VSAVE
    VSAVE -->|"committed decision"| PASS
    PASS -->|"yes"| RELEASE
    RELEASE -->|"committed"| NEXT
    START -->|"missing input, bad config or unsupported isolation"| HALT
    CALL -->|"timeout, cancellation, duplicate conflict or uncertain effect"| HALT
    SAVE -->|"store or mandatory capture failure"| HALT
    GATE -->|"predecision invocation unavailable"| HALT
    VSAVE -->|"save fails, even after computed PASS"| HALT
    PASS -->|"no"| HALT
    RELEASE -->|"save fails"| HALT
    HALT --> HUMAN
    HUMAN --> REC
    REC -->|"committed result and decision reused"| PASS
    REC -->|"Observation committed but Verification absent"| GATE
    REC -->|"valid committed release reused"| NEXT
    REC -->|"human-approved environment or reviewed partial-effect retry, unchanged pins"| CALL
    REC -->|"changed task, input, policy or config"| START
```
