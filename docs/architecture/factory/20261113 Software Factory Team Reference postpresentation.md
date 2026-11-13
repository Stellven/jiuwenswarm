# 20261113 Software Factory Team Reference postpresentation

For this branch, use the [Jetson branch record](20261113%20Jetson%20Software%20Factory%20Branch%20Record%20postpresentation.md) as the primary reference. The Spark companion package discussed below is external follow-up work, not code or performance established by this branch.

## Purpose

Our video-led demo worked well as a software-factory proof of concept. We applied reusable engineering knowledge through Capability Capsules (CCs), integrated an inference engine and inspected recorded execution and results. The next step is deeper research, stronger CCs and DGX Spark hardware, not another presentation.

## Code references

| Repository | Role | Revision |
|---|---|---|
| [Stellven/jiuwenswarm](https://github.com/Stellven/jiuwenswarm/tree/cc-siminfeng) | Factory controller, CC runtime, task graph and evidence store | Branch `cc-siminfeng`; inspected snapshot `fe88a20682550603a5d32193403c74cc6e68e8b7` |
| [Muxite/siminfeng](https://github.com/Muxite/siminfeng) | Hardware-facing lab: queue, builds, inference, experiments | Submodule `lab/siminfeng`, pinned at `45813e3d62650a6de06174a4523f8794b18ae8a3` in that snapshot |

GitHub advertised factory branch tip `532d56c7ee1aec91e636f26221244fd8ecfbd95e` and Siminfeng HEAD `9209e2507ab15e7076691fe2e6112d2f54723663` on November 13. The published factory tip was subsequently inspected: it is the direct parent of local `fe88a206`, whose addition is the RSI assignment package. The Siminfeng HEAD is still a separate reference, not the pinned submodule. Do not silently substitute them when reproducing the inspected snapshot.

```sh
git clone --branch cc-siminfeng https://github.com/Stellven/jiuwenswarm.git factory-reference
cd factory-reference
git fetch origin fe88a20682550603a5d32193403c74cc6e68e8b7
git switch --detach fe88a20682550603a5d32193403c74cc6e68e8b7
git submodule update --init --recursive
git rev-parse HEAD
git submodule status
```

These are proposed reproduction commands, not a fresh-clone test. The inspected local clone originated from Satay; availability of its exact commit through GitHub remains unverified. If fetching fails, request a reviewed source bundle from the owner. The submodule URL uses GitHub SSH and requires the teammate's own access. Do not use `submodule update --remote` for reproduction. The inspected local clone's submodule was registered but uninitialized.

## Architecture and semantics

```text
Operator task + frozen contract
           |
Coding agent selects actions and reads CC guidance
           |
JiuwenSwarm: authority, task revisions, evidence
           |
CC operations -> durable jobs -> Siminfeng shared queue
           |
Build -> correctness screen -> measurement -> decision
```

A CC packages declared capabilities and/or passive materials. It need not be a compiled functional module. Inspect its declaration to discover its actual ID, operations, inputs and outputs. The agent chooses actions; ontology references provide targeting and traceability, not automatic planning or proof of semantic correctness. The graph records dependencies, attempts and revisions. Replay reconstructs recorded state; it does not dispatch jobs.

The factory can use an external lab through `SIMINFENG_ROOT`. Record the actual lab revision and path: a submodule pin alone does not prove which lab executed a run.

## Reading map

All paths below are relative to the pinned factory repository. Read `AGENTS.md` first.

| Topic | Files |
|---|---|
| Repository boundary | `docs/architecture/factory/REPOS.md` |
| CC runtime and declarations | `jiuwenswarm/ccv2/`, `docs/architecture/ccv2/README.md` |
| Agent versus host responsibility | `docs/architecture/factory/CONTROLLER.md`, `AMENDMENT.md`, `MIGRATION.md` |
| Graph and replay | `jiuwenswarm/factory/taskgraph.py`, `docs/architecture/factory/TASK-GRAPH.md`, `NODE-EXAMPLE.md` |
| Actual factory CCs | `jiuwenswarm/factory/ccs/` |
| Original operating procedure | `docs/architecture/factory/RUNBOOK.md` |

CC directories include `engine_inspector`, `expert_streaming`, `engine_component`, `integration_skill`, `builder`, `lab_client`, `evidence` and `methodology_ab`. Folder names are not necessarily capability IDs. Catalog presence does not prove invocation: inspect each task's material reads and operation receipts.

Older START-HERE/demo notes retain historical directions and can blur the integration demo with J-OM13. Use the distinctions below. Older local-agent login directions are not Spark setup instructions: our current approach keeps subscription authentication and reasoning local and operates Spark over SSH.

## Evidence boundaries

| Evidence | What it establishes | Limits |
|---|---|---|
| Satay image `a15f04f0` | Working fill-only engine and genuine terminal request/response | Functional demo, not HTTP execution or measured speedup |
| Historical J-OM13 image `1274abb8` | Fill plus predictive reads: 841.4975 to 711.425 ms/token; 15.5% lower decode time / 18.3% higher throughput | Separate experiment; four repeats per headline arm, all 12 observations retained |
| Jifan recording | Real inspection and replay tools operated | Historical build/inference were not rerun there |
| Spark build prototype | Cold compilation 233.4 s; unchanged cycle 2.6 s; small-edit cycle 9.3 s | Single observations, three targets, no portable export per cycle; initial cold launch smoke failed, corrected later runs passed |
| Spark memory qualification | 8 GiB CPU inference, verified NVMe reads and output matching 16 GiB control | Model exceeds allocated budget, not physical RAM; full GPU accounting remains open |

The small source edit was a diagnostic marker, not an inference optimization. No isolated 80% cache penalty or screen-recording overhead was established. Historical model-hash provenance remains incomplete. Nsight mechanism summaries are not clean speed comparisons.

## Useful first contributions

1. Reconstruct a task from its contract, CC declarations, graph revisions and evidence. Explain cancellations and acceptance without launching new inference.
2. Compare supported inference engines on Spark with fixed workloads, exact identities and correctness checks. llama.cpp is a familiar baseline, not an established best performer.
3. Expand CCs from demonstrated procedures: explicit inputs, outputs, dependencies, authority, failure behavior and evidence requirements. Loader validation alone does not qualify runtime effectiveness.
4. Improve build turnaround with configuration-specific caches and separate configure, compile, package and export timings. Keep cold, unchanged and small-edit cases.
5. Qualify memory behavior: distinguish artificial caps from actual SSD-backed execution; next investigate GPU allocation accounting and genuinely oversized models.

Each contribution should state a bounded question, source/model/runtime identities, finite timeout and resource budget, correctness check, raw results and an accept/reject rationale. Preserve negative results. No factory redesign is required to add a benchmark.

## Companion package

The selected `tools/` files include the local SSH wrapper, current v3 runner, build prototype, inference probe versions and owned-container cleanup probe. `capsules/` contains two material-only v0.1.1 candidates: `factory.methods.spark_build_iteration` and `factory.methods.memory_budget_qualification`. They passed the existing declaration loader but are not centrally installed callable tools.

These are workspace-specific prototypes, not a portable installer. Review explicit host, workspace, queue, source, image and model paths before adapting them to a separate owned workspace. Do not run unchanged scripts against the owner's shared workspace. Use your own SSH access. Never copy account credentials, start a second shared worker, clear host page cache, globally prune Docker, change drivers or overwrite another project.

The included operating guide documents inspect, stage, submit, status, logs, fetch and cancel. Requests persist before dispatch; identical IDs recover the same job. After disconnect, reconcile before resubmitting. Cancellation targets owned IDs. The queue serializes participating heavy jobs, not unrelated workloads. Docker membership means this is ownership discipline, not a security sandbox.

The original handoff/evidence index use owner-machine paths; they describe qualification records, not files guaranteed to exist on a teammate's machine. Large sources, models, images and raw evidence are excluded from this small package. Obtain the specific evidence set needed for reproduction from the owner.

## Distribution status

Prepared locally; not committed, pushed or sent. GitHub references were queried and local code paths inspected. Fresh-machine installation and exact-snapshot GitHub access remain untested. Portable configuration and repository access are the main onboarding gaps. Treat newer branch tips and older demo instructions as separate references, not substitutes for this pinned handoff.
