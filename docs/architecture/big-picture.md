---
type: design
tags: [goal, post-m1]
---

# The big picture: where we are heading

> **A potential near-term goal, open to change.** This page gives context: it shows where the project is heading, so that someone working on M1 can see why M1 builds what it builds. Anyone may propose changes to it. It is not a design and not granular enough to build from: the smallest thing drawn is a capability capsule or a gate. The design to build from is [B1](b1-design.md) for the earliest pipeline, then [M1 architecture](m1-architecture.md) for the full build; the earlier [M1 design](m1-design.md) is past and no longer current.

**What the goal adds to M1:**

- **Dispatch becomes truly dynamic.** A planner builds the plan for each request, and a selector picks capsules from the library. The fixed pipeline stays as a fallback.
- **A library sits in the middle.** It holds every admitted capsule, its Verdicts, its Standing, its lineage and its test suites. The hot path takes capsules out of it, and the cold paths put capsules into it.
- **RSI is attached to the library.** It reads what the library has learned, builds better or new capsules, and sends them back through admission. No person has to copy them in.
- **A librarian keeps the library honest.** It watches how capsules behave in real runs and moves their Standing.
- **Capabilities come from anywhere.** An importer turns an outside tool, skill or MCP server into a capsule, after verifying it in isolation.

## Three loops, meeting at the library

```mermaid
flowchart LR
    subgraph HOT["hot path: one request, intake to delivery"]
        RQ>"request"]:::ext --> PIPE["the pipeline: fixed stages around a dynamic dispatch"]:::ctrl --> ANS>"answer"]:::ext
    end
    subgraph LIBR["the library"]
        ADM{{"admission gate"}}:::gate --> LIB[("admitted capsules: Verdicts, Standing, lineage, test suites")]:::rec
        LBR["librarian: moves Standing"]:::ctrl --> LIB
    end
    subgraph COLD["cold path: RSI"]
        RSI["RSI: builds new and better capsules"]:::agent --> CAND[("Candidates")]:::rec
    end
    subgraph OUT["outside"]
        SRC>"tools, skills, MCP servers from anywhere"]:::ext --> IMP["importer and isolated verification"]:::ctrl
    end
    LIB -->|"selector and binder pick capsules"| PIPE
    PIPE -->|"Observations, Verifications"| LBR
    PIPE -->|"Observations, gaps"| RSI
    LIB -->|"lineage, test suites, Findings"| RSI
    CAND --> ADM
    IMP -->|"Candidates"| ADM

    classDef gate fill:#C9A8E0,stroke:#5B1F86,stroke-width:2.5px,stroke-dasharray:6 3,color:#1a1208,font-weight:bold
    classDef ctrl fill:#ffffff,stroke:#5B1F86,stroke-width:2.5px,color:#1a1208,font-weight:bold
    classDef rec fill:#E6CFB6,stroke:#6E3F12,stroke-width:2px,color:#1a1208,font-weight:bold
    classDef ext fill:#ffffff,stroke:#3b3b3b,stroke-width:2px,color:#111111,font-weight:bold
    classDef agent fill:#CFE3F7,stroke:#1F5A96,stroke-width:2px,color:#1a1208,font-weight:bold
```

- **The hot path runs fast, once per request.** It takes admitted capsules out of the library and records every call.
- **The cold paths run slowly, away from any request.** RSI and the importer put capsules in, and the librarian keeps their Standing current.
- **Admission is the only way in.** A capsule from RSI, from the importer or from a person passes the same gate.

## The hot path after M1

```mermaid
flowchart TB
    H>"researcher: request and documents"]:::ext --> IN["intake"]:::ctrl
    IN -->|"RawIntent"| C1(["compile_intent"]):::cc
    C1 --> G1{{"intent gate"}}:::gate
    G1 -->|"IntentIR"| C2(["compile_requirement"]):::cc
    C2 --> G2{{"requirement gate"}}:::gate
    G2 -->|"semantic contract"| PL["planner: builds the plan for this request"]:::ctrl
    LIB[("library")]:::rec -->|"capsules that fit, by port type and Standing"| SEL["selector"]:::ctrl
    SEL --> PL
    PL -->|"plan"| BD["binder and freeze: pin each node"]:::ctrl
    BD ==>|"Bindings"| DISPATCH
    subgraph DISPATCH["dispatch: set at runtime by the plan"]
        D1(["capsule"]):::cc --> DG1{{"gate"}}:::gate
        DG1 --> D2(["capsule"]):::cc
        DG1 --> D3(["capsule, in parallel"]):::cc
        D2 --> DG2{{"gate"}}:::gate
        D3 --> DG3{{"gate"}}:::gate
        DG2 --> D4(["composite capsule"]):::cc
        DG3 --> D4
        D4 --> DG4{{"gate"}}:::gate
    end
    DG4 -->|"checked outputs"| DL["delivery"]:::ctrl
    DL --> OUT>"researcher reads the answer"]:::ext
    DISPATCH -.->|"a gate halts or asks for a replan"| PL
    DISPATCH -.->|"a gate halts"| HS>"a person decides"]:::ext

    classDef cc fill:#F2A007,stroke:#8A4B00,stroke-width:3px,color:#1a1208,font-weight:bold
    classDef gate fill:#C9A8E0,stroke:#5B1F86,stroke-width:2.5px,stroke-dasharray:6 3,color:#1a1208,font-weight:bold
    classDef ctrl fill:#ffffff,stroke:#5B1F86,stroke-width:2.5px,color:#1a1208,font-weight:bold
    classDef rec fill:#E6CFB6,stroke:#6E3F12,stroke-width:2px,color:#1a1208,font-weight:bold
    classDef ext fill:#ffffff,stroke:#3b3b3b,stroke-width:2px,color:#111111,font-weight:bold
    style DISPATCH fill:#FFF4DC,stroke:#B86E00,stroke-width:3px
```

Key as in [B1](b1-design.md#the-pipeline).

- **The stages around dispatch stay the same as in B1 and M1:** intake, intent compilation, requirement compilation, then delivery. What changes is how dispatch is filled.
- **The planner and selector fill dispatch at runtime.** The selector offers the admitted capsules that fit the contract. The planner orders them, possibly in parallel, and the binder pins each node by hash.
- **Every capsule is still followed by its gate.** A gate can halt the run, or send it back to the planner for a new plan.
- **A composite capsule** is a capsule made of other capsules. It is pinned and gated like any other.
- **Selection picks capsules, never models** (see [needs](capsule/fields.md#needs-what-must-hold-and-what-it-uses)).

## The cold paths after M1

```mermaid
flowchart TB
    subgraph RSIP["RSI"]
        GAP[("gaps and weak capsules, from Findings and Observations")]:::rec --> DEC[("a new or changed Declaration")]:::rec
        DEC --> IMPL["implementer agent"]:::agent
        DEC --> TW["test-writer agent"]:::agent
        IMPL --> LOOP["run the tests until good enough"]:::ctrl
        TW --> LOOP
        LOOP --> CAND[("Candidate with lineage")]:::rec
    end
    subgraph IMPP["import"]
        SRC>"a tool, skill or MCP server from anywhere"]:::ext --> DRAFT["draft a Declaration and tests"]:::ctrl
        DRAFT --> SBX["verify in an isolated sandbox"]:::ctrl
        SBX --> CAND2[("Candidate with its source")]:::rec
    end
    CAND --> ADM{{"admission gate: hashes, rules, visible and sealed tests"}}:::gate
    CAND2 --> ADM
    ADM -->|"Verdict"| LIB[("library")]:::rec
    LIB --> LBR["librarian: measures real runs, moves Standing"]:::ctrl
    LBR --> LIB
    LIB -.->|"share admitted capsules"| STORE[("stores and repositories")]:::rec

    classDef gate fill:#C9A8E0,stroke:#5B1F86,stroke-width:2.5px,stroke-dasharray:6 3,color:#1a1208,font-weight:bold
    classDef ctrl fill:#ffffff,stroke:#5B1F86,stroke-width:2.5px,color:#1a1208,font-weight:bold
    classDef rec fill:#E6CFB6,stroke:#6E3F12,stroke-width:2px,color:#1a1208,font-weight:bold
    classDef ext fill:#ffffff,stroke:#3b3b3b,stroke-width:2px,color:#111111,font-weight:bold
    classDef agent fill:#CFE3F7,stroke:#1F5A96,stroke-width:2px,color:#1a1208,font-weight:bold
```

- **RSI grows the system in two ways:** new capsules let it do more, and better capsules let it do the same things well. Capsules are isolated and testable one at a time, so each change is tested on its own capsule.
- **Import brings in outside capabilities.** A tool, skill or MCP server is drafted into a Declaration with tests, verified in isolation, and then admitted like any other capsule.
- **The library also screens capsules that are bad together.** Two capsules can each pass admission and still fail as a set. The library searches for such sets from their Declarations, confirms them in a sandbox, and records a Finding, so the selector avoids them. See [When good capsules are bad together](capsule/library.md#when-good-capsules-are-bad-together).
- **The librarian closes the loop.** It measures how capsules behave in real runs, lowers the Standing of those that drift, and its Findings tell RSI where to work next.
- **Stores and repositories** are the end point: admitted capsules shared with other systems, each carrying its Declaration, checks and Verdict.

## How the workstreams fit together

Each workstream builds one part of the pictures above, and meets the others only at a named interface.

| Workstream | Where it sits in the pictures | In M1 | Its interface to the rest |
|---|---|---|---|
| Capability Capsule | the capsules, the CC runner, admission and the library at the middle of the three loops | the six core capsules in the `make_capsule.md` contract, with rubrics ported from sciencediscovery and strict JSON payloads; the CC runner; admission | the Declaration; admission; the Binding |
| Verifier | every gate after a capsule, both tiers; and benchmarking, which measures the whole platform against native openJiuwen | the Evaluator gate: the two tiers and the PRD's five gate outcomes; a three-phase benchmark against native openJiuwen | the Verification record and its outcomes; reads the records of runs |
| RSI | the RSI cold path, attached to the library | mutation in an offline sandbox, against static contracts and hidden fixtures | reads Findings, Observations, lineage and test suites; sends Candidates to admission |
| RSI data foundation | feeds the RSI cold path | the data and fixtures RSI works on | sample runs and fixtures |
| Verifier fine-tuning | the model behind the tier 2 judge | tuning the model behind the tier 2 judge | a new version of the verifier capsule, through admission |
| Model routing | inside capsules whose authors want a routed model; not in the capsule layer (see [needs](capsule/fields.md#needs-what-must-hold-and-what-it-uses)) | on the main branch, the Codex CLI adapter over one subscription. On an isolated branch, a multi-model router against simulated endpoints until enterprise keys arrive | none with the capsule layer |
| Planner | fills the dispatch box at runtime | the Cluster Mode planner, tested against offline scenarios; the Leader Agent for intent compilation. It may replace the fixed DAG after M1. Muk has reviewed a similar bounded, effect- and trust-aware graph search elsewhere. It informs the shape of this problem; the design here still needs to be built fresh, not carried over | reads the contract and the selector's offer; writes the plan |

Because the parts meet only at these interfaces, each workstream can build and test its part on its own.

## Where each part comes from

| Part | First appears | Where to read more |
|---|---|---|
| fixed pipeline, CC runner, gates | B1 | [B1](b1-design.md) |
| two-tier gate, admission, operators | M1 | [M1 architecture](m1-architecture.md) |
| RSI in an offline sandbox, dynamic planner and router on their own tracks | M1, as parallel tracks | [M1 architecture, Seams with other workstreams](m1-architecture.md#seams-with-other-workstreams) |
| library, selector, planner and binder on the main path, librarian | after M1 | this page |
| importer, isolated verification, composites, stores | after M1 | [Tools](capsule/tools.md), [Composition](capsule/composition.md) |
