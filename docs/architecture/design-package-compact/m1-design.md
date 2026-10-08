# System architecture

**Reading level: human immediate.** This page connects the whole M1 system. [Research design](research-design.md) expands each responsibility; [reference](reference/README.md) defines the information crossing boundaries.

## From meaning to a governed research program

Intake captures the original request and qualifies permitted local documents/assets. It rejects unreadable required inputs rather than silently losing them. Intent compilation identifies the user's problem, desired change and requested result. Requirements turns accepted meaning into the Research Brief contract. Neither compiler chooses the scientific solution.

```mermaid
flowchart TB
    I[Qualified original request] --> C[Intent compiler CC: candidate Intent IR]
    C --> D1{Deterministic Intent checks}
    D1 -->|valid| V1[Intent verifier CC: fidelity and usability verdict]
    D1 -->|invalid| G1[Protected Intent gate]
    V1 --> G1
    G1 -->|durably accepted| R[Requirements CC: Research Brief contract]
    G1 -->|blocked| H[Visible halt: reason and retained artifact]
    R --> D2{Deterministic Brief checks}
    D2 -->|valid| V2[Requirements verifier CC: completeness and consistency]
    D2 -->|invalid| G2[Protected Requirements gate]
    V2 --> G2
    G2 -->|durably accepted| P[Static binder or bounded Phase 3 planner]
    G2 -->|blocked| H
    P --> F[Protected plan check and freeze]
    F --> S[Search and ideation]
    S --> O[Screen one opportunity]
    O --> B[Register hypothesis and protocol]
    B --> K[Build bounded POC]
    K --> M[Measure baseline then treatment]
    M --> E[Scientific evaluation]
    E --> T[Deliver report and evidence]
```

Search → Screening → Hypothesis → Builder → Benchmark → Scientific Evaluation → Delivery is one governed research sequence. Every stage uses the shared capture/check/verifier/protected-commit boundary; the diagram abbreviates those repeated boundaries. Scientific FAIL may be a valid accepted result, not infrastructure failure.

## Execution and model routing

Each M1 execution node has one work CC. Additional work CCs use separate gated nodes; verifier invocations remain separately governed checking assignments. Composite/merged CCs and internal member graphs remain later work.

```mermaid
flowchart LR
    S[Protected scheduler] --> R[Governed CC runner]
    R --> C[Work or verifier CC]
    C -->|permitted model request through runner context| Route[Protected role/profile routing]
    Route --> Bridge[Audited model bridge]
    Bridge --> Model[Configured endpoint; static Codex baseline]
    Bridge --> Evidence[Observed calls, effective identity and telemetry]
    R --> X[Restricted scientific executor]
    X --> Evidence
    Evidence --> Check[Checking and durable run state]
```

## Where RSI connects

```mermaid
flowchart LR
    L[(Eligible immutable library parent)] --> Profile[Protected target profile and frozen contract]
    Profile --> P[Bounded proposer using audited model boundary]
    P --> Guard[Mutation guard and isolated child runner]
    Guard --> Referee[Independent referee and fixture custodian]
    Referee -->|approved aggregate loop feedback only| P
    Referee --> Export[Paired evidence and inactive candidate]
    Export --> Admission[Protected admission]
    Admission --> Human[Explicit human activation or rollback]
    Human -->|future selection only| L
```

## Placement, state and human inspection

The application image contains the frontend, same-origin web/control API and workflow runtime. Its entrypoint starts the product. The browser reaches container port 5173 through host-loopback publication, normally `127.0.0.1:5173:5173`. No external UI script or separate frontend container is required. A separate sidecar/benchmarker uses configured private-network service DNS and the container port, ordinary scoped authentication and a compatibility handshake; its own localhost is not the application.

SQLite owns durable lifecycle/release state; immutable files retain artifacts and observations. Account/profile state survives run/workspace deletion. Readable views are derived from the same records; restart pauses without replay, and saved inspection never executes work.

## Full M1 and the next build

| Delivery phase | Required architecture and exit meaning |
|---|---|
| Phase 1: baseline, Stages 0–7 | Governed foundation; qualified request → accepted Brief → static bound research graph; search/screen/hypothesis; POC and matched measurements; scientific verdict/report; persistence, evidence and native workstation clients. Demonstrate real connected work and failure handling |
| Phase 2: Stage 8 RSI | Independent bounded Target 1 mutation/evaluation/evidence with frozen referee and security; sandbox candidate stays outside production. Target 2 depends on available bounded model execution |
| Phase 3: integration | Attempt every applicable advanced compiler, Team/Cluster planning, dynamic discovery/binding, heterogeneous routing, alternate verifier and Code Mode effort. Preserve baseline; distinguish validated, blocked and incomplete outcomes |
