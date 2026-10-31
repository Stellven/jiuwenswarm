# SIMLAB: architecture

**Architecture Design Main Body · r0.4.1 · Milestone PAS-M1 (local workstation only) · October 30, 2026.** Start here. [Context](../Architecture_context/Architecture_context.md) holds the interfaces, flows, failure behavior, worked example, required reading and open inputs. Private classes, algorithms and file layouts belong to implementers; shared fields and authority do not.

## Completion boundary

**Request → builder constructs the experiment and its feasibility record → AI4R checks and gate accept it → runner executes every arm and trial with checks → data and records return → AI4R sends the next question → builder constructs a changed follow-up with the same tools.**

Milestone PAS-M1 completes at the phase 5 exit, on the local workstation, with `PAS-M1_Final_Test_Report.md`. A mocked model, a number without a run record, a follow-up that needed a special core change, a missing dependency reported as if it ran, or a research campaign where every candidate was blocked is not completion.

## Responsibilities

| Component | Required work and output | Authority / boundary |
|---|---|---|
| Builder (`simlab.experiment_build`) | Construct experiments through the authoring tools; write the protocol with origins; feasibility record; typed halts | A reasoning agent; no scientific choices; never runs the trials that count or edits a submitted experiment |
| Runner and experiment core | Validate; execute arms and trials; run checks; save state; keep records, attempts and traces | Plain code; never judges; reaches models only through the model interface |
| Executors | MuJoCo first, numerical engine, a source's simulator when admitted | Pinned versions; admitted by conformance |
| Libraries | Actuators, extra forces, flexible parts, solvers, frozen policies, world models | Built against the library interface; wrap MuJoCo's own models where they exist (`dcmotor`, `pid`, cable and flex rods); admitted after known-answer checks |
| Model interface and memory | Calls to models under test, timing, budgets, fallbacks, memory state | Records every call; no training |
| Checks | Validation, sanity watchdogs, reruns, recomputation, conformance | Owned separately from the code they check |
| Capability registry | What is supported, excluded and missing | Admission only by conformance results |
| Tool interface | MCP server, Python client, CLI, including the authoring tools | Same operations for every agent |
| Run capsule (`simlab.benchmark`) | Submit, wait, return the AI4R benchmark payload with references | No interpretation; no reruns to improve results |

The scientific requester (AI4R in the integrated journey, or whoever uses SIMLAB directly) owns objectives, experiment design, thresholds, interpretation and the next question.

## Placement

The integrated `ai4r` container carries SIMLAB's two capsules and is the only service on `127.0.0.1:5175`. The `simlab-runner` has no credentials and sits on the lab's private network. Each component declares its execution mode: in-process extension, separate process or separate service. Agent-authored code is always confined (no network, no credentials, declared limits). Calls to models under test go from the runner through the model interface to the lab's model route; executors never hold credentials.

In M1 everything, including SYSTEM evidence, runs on the owner's laptop (x86-64, WSL2 capped at 6 GB, a 6 GB GPU). Run data lives in a declared data directory outside the repository; curated evidence is committed. Models under test are API models or local ones admitted as fitting the laptop.

Following the labs brief (a lab is an AI4R fork, its capsules and installed application code), everything for the lab lives in `labs/physicalai_sim/`, self-contained like `jiuwenbox/`: code, tests, images, `benchmarks/`, and `missions/PAS-M1/` for the spec, task records, evidence and reports. Only the two capsules sit in AI4R's code (`jiuwenswarm/research/capsule_extensions/simlab_*/`), where AI4R loads capsules. Work happens on the `PhysicalAI-Sim` branch, forked from `AI4Research-Main`.

## Build order

| Phase | Build |
|---|---|
| **1. Base simulator** | A first check that the real local setup fits (AI4R, model route and simulator together); experiment core, MuJoCo, authoring tools, records, checks, world-state save and branch, traces, tool interface, doctor |
| **2. Builder and first demonstration** | Builder and construction tools, feasibility records, the first demonstration (Fit2Form unless decided otherwise), a changed follow-up, and a thin AI4R connection |
| **3. Libraries** | Numerical engine, actuators, forces, flexible parts, solvers, frozen policies, world models, model interface and memory |
| **4. AI4R journey and scale** | Full AI4R journey with follow-ups, whole-state checkpoints, concurrency, recovery, live view |
| **5. First research runs** | Hypothesis-register candidates end to end; final report |

During development, a general core improvement is fine if it is reviewed and the affected evidence is rerun. During phase 5, a request that needs a bespoke core change is recorded as a capability gap.

## Required proof

| Exit | Required observable result | Level |
|---|---|---|
| X1.1 | AI4R, one real model-route request and a simulator process run together on the laptop; resource use and failures are recorded | BOUNDARY |
| X1.2 | Phase 1 test benches pass to their frozen specifications | BOUNDARY |
| X1.3 | A malformed experiment returns all findings at once with typed errors, and clean controls pass | BLOCK, BOUNDARY |
| X1.4 | A coding agent with no other access builds, runs and inspects an experiment only through the tools | BOUNDARY |
| X1.5 | Replay is identical on the same machine and build; save, restore and branch reproduce the continuation; a fresh checkout reproduces a result | BOUNDARY |
| X2.1 | First demonstration: the source reference, the MuJoCo rebuild's agreement with it (declared unit and tolerance) and any discrepancy diagnosis are reported separately; an explained discrepancy is not a PASS | BOUNDARY |
| X2.2 | The builder rebuilds the first demonstration from AI4R-style inputs | BOUNDARY |
| X2.3 | Planted defects are caught, paired clean controls pass, and false alarms are reported | BOUNDARY |
| X2.4 | A missing dependency is BLOCKED with its reason, never proxied | BOUNDARY |
| X2.5 | A scripted next question produces a materially changed follow-up (a new procedure, apparatus or measurement, not just a parameter change) with no core change | BOUNDARY |
| X2.6 | One real AI4R request reaches SIMLAB through the capsules and gets its data back | SYSTEM |
| X3.1 | Each library passes its known-answer case and, where it adapts released code, an adapter conformance check | BOUNDARY |
| X3.2 | Two components whose behavior depends on each other pass the runtime contract; one scene uses at least three libraries | BOUNDARY |
| X3.3 | A real model drives a simulated robot in two timing modes; replay reproduces its decisions; a fresh replication is recorded as new | BOUNDARY |
| X3.4 | World-model scoring is verified, and a real world model's error against physics is reported for a declared domain | BOUNDARY |
| X4.1 | An AI4R question reaches a report, every number traced to a run | SYSTEM |
| X4.2 | The overall test inside AI4R: it inspects the data, asks a next question, and SIMLAB builds the follow-up with no core change | SYSTEM |
| X4.3 | [confirm: 1,000] runs are characterized (workload, concurrency, throughput, latency, peak memory, failures); a killed worker loses nothing completed and duplicates nothing | SYSTEM |
| X4.4 | A whole-state checkpoint at a quiescent point restores, and a follow-up branches from it | SYSTEM |
| X4.5 | Live view pauses and cancels without changing the experiment (Conditional) | SYSTEM |
| X5.1 | At least [confirm: 3] of [confirm: 5] register candidates complete end to end with valid checks, on held-out cases not used during development; blocked candidates are reported separately | SYSTEM |
| X5.2 | The final test report covers every exit with evidence | SYSTEM |

**M2 (later):** the DGX Spark and native arm64; models too large for the laptop; scale beyond the laptop; then use as an RL environment, full input lineage and further engines.

Mocks do not count at BOUNDARY or SYSTEM level. Fixture checks cannot prove a real model's behavior. BLOCKED and NOT_RUN are not PASS.

## AI4R connection and prompt use

SIMLAB consumes AI4R's capsule format, Planner, gates and process rules without modifying them. The AI4R baseline is pinned; merging a newer `AI4Research-Main` is a recorded update followed by rerunning the affected checks. Nothing in `labs/physicalai_sim/` imports AI4R code; an import check enforces this. Any agent reaches the lab through its MCP server; AI4R's journeys reach it through the two capsules. The owner's coding prompt points the coding agent at these four documents and [Verification](../Verification/README.md). Phase 3 libraries can be built in parallel once the library interface has passed its first interacting-components check (X3.2).
