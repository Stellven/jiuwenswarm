# SIMLAB: product context

**PRD Context · r0.4.2.** Read [PRD Main](../PRD_main_body/PRD_main_body.md) first. This page gives sources, user stories, scope and terms.

## Sources

| Source | Role |
|---|---|
| `received/ai4r-labs-and-capsules-brief-2026-10-23.txt` (5013 bytes, SHA-256 `aa4e9724…6c50c68`) | The colleague's lab and capsule direction. SIMLAB is the lab's installed application plus two capsules; findings, continuation and improvement stay in AI4R |
| AI4R PRD (`docs/product/received-prds/`, current reviewed version on the base branch) | Journey stages, capsule rules, scope labels and report requirements SIMLAB follows |
| Fit2Form, arXiv:2011.06498v1 (SHA-256 `d303487f…a273a7`) | First demonstration candidate |
| [`hypothesis-register.json`](hypothesis-register.json) (122 entries from 86 papers, desk dry runs, October 2026; nothing in it was simulated) | Phase 5 research candidates and benchmark hypothesis cases |

## User stories

| ID | Story |
|---|---|
| US-SL01 | As a researcher, I ask AI4R a question about a physical system and get a report whose numbers trace to runs. |
| US-SL02 | As a researcher, I ask a follow-up and SIMLAB builds the changed experiment without anyone editing its core. |
| US-SL03 | As a researcher, I see each result's checks and what actually ran versus what was missing. |
| US-SL04 | As a researcher, I study a model or memory module as the thing under test, and tell replays from fresh repeats. |
| US-SL05 | As a researcher, I preview many designs with a world model, then confirm the promising ones in physics. |
| US-SL06 | As a researcher, I save an experiment's whole state and branch a what-if from it. |
| US-SL07 | As a developer of another agent, I drive SIMLAB through its tools, without AI4R. |
| US-SL08 | As a reviewer, I read phase test reports and benchmark results showing what passed, failed and is blocked. |

## Scope and deployment

| In scope now | Not now |
|---|---|
| Rigid contact and articulated bodies; equation-only models; actuators, extra forces, flexible parts; model-based controllers; frozen policies; world models; models and memory under test | Training and RL post-training (SIMLAB can become an RL environment later); real hardware; photoreal perception; fluids, granular media, large FEM; a research loop inside SIMLAB; cloud deployment |

Hardware: milestone M1 runs only on the local workstation (Ryzen 7 8845HS, 16 threads; RTX 3050 laptop GPU with 6 GB; WSL2 currently capped at 6 GB of memory). The DGX Spark (arm64, 128 GB) comes in M2. Runtime model access goes only through the lab's model route; models in the loop in M1 are API models or small models that fit the laptop.

## Terms

| Term | Meaning |
|---|---|
| Request | What an agent asks for: a research objective, or a follow-up to an earlier run |
| Protocol | The scientific plan: objective, arms, variables, measurements, predicates, thresholds. AI4R owns it |
| Experiment package | The runnable form of one protocol; fixed once submitted |
| Library | A built-in part of the simulator: actuators, forces, flexible parts, solvers, frozen policies, world models |
| Checkpoint | A saved copy of the whole experiment state |
| Replay / fresh replication | Rerunning with a model's recorded decisions / with new model calls |
| Feasibility record | Per dependency: inspected, missing, unverified, needs calibration, or ran |
| The overall test | Construct an experiment, return data AI4R can inspect, receive the next question, construct a materially changed follow-up with no core change |
