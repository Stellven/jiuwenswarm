# 20261113 Jetson Software Factory Branch Record postpresentation

## What this branch demonstrates

`cc-siminfeng` is a software-factory proof of concept developed and exercised on **Satay, an NVIDIA Jetson Orin Nano Super 8GB**. It packages existing engineering knowledge as Capability Capsules (CCs), lets a coding agent apply it to an owned llama.cpp source branch, builds identified engine images, evaluates them under explicit contracts, and records the decisions and evidence.

The November 13 video-led walkthrough was clear and well received as a software-factory proof of concept, according to the presenter. That is presentation feedback, not additional benchmark evidence. The engineering outcome is a working integration/build/evaluation workflow and a promising, separately measured historical engine result. It is not evidence that the factory invented the techniques, that every candidate improved performance, or that an arbitrary task can be solved autonomously.

This is the current branch-level reading guide. Historical records, source artifacts and experiment outcomes remain unchanged. Start here rather than treating an old demo script as the current state.

## Revision boundary and repositories

Inspection on November 13 fetched GitHub `Stellven/jiuwenswarm:cc-siminfeng` at **`532d56c7ee1aec91e636f26221244fd8ecfbd95e`**. The local branch is at **`fe88a20682550603a5d32193403c74cc6e68e8b7`**, whose recorded parent is that published commit. The local commit adds the RSI assignment and fixtures under `docs/rsi/2026-11-13/`; it does not replace the published factory implementation. This checkout is shallow, so use the commit object's parent and tree comparison rather than interpreting a shallow history boundary as an unrelated branch. No remote publication of the local addition is implied.

| Repository / source | Responsibility | Version boundary |
|---|---|---|
| JiuwenSwarm, branch `cc-siminfeng` | Agent/controller integration, CC host, factory tools, evidence store and task graph | Published and local commits above |
| Siminfeng, `lab/siminfeng` submodule | Hardware-facing queue, CUDA build, inference/AB harnesses, patches and research records | Parent snapshot pins `45813e3d62650a6de06174a4523f8794b18ae8a3` |
| Runtime lab checkout | Actual lab scripts used on Satay | Can be external through `SIMINFENG_ROOT`; must be recorded separately from the submodule pin |
| llama.cpp | Engine being modified, not the factory itself | Component base `cf34d311332e362198f0a410c466d1e940287d02`; candidate commits/images vary by task |

[REPOS.md](REPOS.md) documents the repository boundary. [The recovery handoff](../../demo/recovery/HANDOFF.md) records a later external Siminfeng checkout at `9209e25`; the [J-ASK1 record](../../demo/recovery/proof-ask-1/README.md) names lab commit `7cab011`. These references describe different artifacts; do not collapse them into one universal lab pin. The submodule is not initialized in this inspected local clone.

Spark is the intended next hardware target. Subsequent SSH adapters and Spark measurements are separate work; they are not proof of Jetson branch portability and are not included as results of this branch. Jetson CUDA SM87/runtime assumptions need explicit qualification on another device.

## Hardware and workload

The [historical status](STATUS-2026-11-12.md) records Jetson Orin Nano Super 8GB, approximately 7.4 GiB visible RAM, and L4T R36.5.2. The [runbook](RUNBOOK.md) records CUDA 12.6.68, JetPack 6.2.3+b81 and the intake software versions. These are historical observations, not assertions about a currently running host.

The recorded engine workload uses Qwen3.6-35B-A3B UD-Q4_K_XL, about 20.8 GiB / 22,360,456,160 bytes, exceeding Jetson's physical RAM. The status record describes 40 layers, 256 experts per layer and 8 routed experts plus shared computation. With the recorded `-cmoe` configuration, expert computation is on CPU. The work addresses mapped expert-weight availability and storage stalls, not moving experts onto the GPU.

llama.cpp was chosen as a well-documented, recognizable baseline. This branch does not establish that it is the best engine for the model or hardware. Model filenames and abbreviated hashes in summaries are not complete provenance; use the exact run's model manifest where available and disclose missing full hashes.

## Implemented architecture

```text
Operator task / constraints / budget + frozen lab contract
                         |
              CLI ask or task initialization
                         |
      JiuwenSwarm agent + Codex adapter chooses actions
                         |
              CC MCP host and factory interfaces
                         |
       inspect -> integrate -> build -> screen / compare
                         |                         |
       durable jobs -> Siminfeng queue        evidence / decision
                         |                         |
       identified image and lab outputs <--- revised work graph
```

| Area | What exists | Relevant implementation / documentation |
|---|---|---|
| CC runtime | Discovery, material reads, finite calls, services, artifacts and receipts; operator-defined authority | [CC v2 guide](../ccv2/README.md), `jiuwenswarm/ccv2/` |
| Factory controller | Agent-directed actions, budgets, decision revisions, resume/reconciliation and plain-language `ask` | [CONTROLLER.md](CONTROLLER.md), `controller.py`, `cli.py`, `api.py` |
| Source and image lifecycle | Inspect source, apply component material, submit builds, inspect completion and admit exact image identity | `inspector.py`, `components.py`, `builder.py`, `manager.py` |
| Lab evaluation | Single screens and AB comparisons under explicit contracts; component-specific acceptance | `contract.py`, `lab_runner.py`, `ab.py`, [RUNBOOK.md](RUNBOOK.md) |
| Durable execution | Persisted identities, job status/reconciliation, bounded queue execution | `jobs.py`, Siminfeng `bin/jobq` |
| Evidence and task graph | Shared evidence references, append-only revisions, dependencies, attempts, replay and readiness views | `store.py`, `taskgraph.py`, [TASK-GRAPH.md](TASK-GRAPH.md) |
| Inspection and presentation | Story, telemetry, export/replay, terminal captures and offline demo packages | [TELEMETRY.md](TELEMETRY.md), [recovery start page](../../demo/recovery/START%20HERE.md) |

Python basenames in this table are under `jiuwenswarm/factory/`. The [design-change record](DESIGN-CHANGE-2026-11-12.md) explains the revisable contract-driven loop and boundaries. This does not restore the removed M1 compiler/planner architecture.

The task graph records work; it is not an automatic dispatcher. The coding agent selects actions and may revise the plan. The existing job queue runs submitted jobs. Sources and outputs stay in workspace/store artifacts; nodes reference them rather than transporting the whole environment across graph edges. Native bindings and Docker access are trusted execution, not a hostile-code security sandbox.

## What the CCs contribute

The [complete CC catalog and lab integration guide](20261113%20CC%20Catalog%20and%20Lab%20Integration%20postpresentation.md) lists all 16 factory declarations plus 4 separate runtime examples, with full schemas and source material links.

CCs can package passive engineering materials, callable operations or both. A component material is not automatically an installed or enabled engine feature. The nested catalog entries expose reusable component knowledge; they do not mean each entry was used or measured in every task.

| CC / group | Role in the workflow |
|---|---|
| `engine.expert_streaming` | Guide, method, source map, ontology and component references for expert-weight readiness |
| `factory.components.expert_fill` | Specific source patches, prerequisites, runtime switches, engagement checks and rollback for demand fill |
| Other component entries | `mmap_advice`, `router_prefetch`, `expert_pregate`, `thread_names`, `expert_readiness`, `inflight_join`, `phase_stats`; statuses vary by task |
| `factory.engine_component` | Earlier thread-naming component bundle with patch and integration materials |
| `factory.engine_inspector` | Read-only source inspection and applicability information |
| `factory.integration_skill` | Guidance for applying and verifying changes; the agent performs integration |
| `factory.builder` | Durable build operations and identified build outputs |
| `factory.lab_client` | Submit/read lab and AB work |
| `factory.methodology_ab` | Experimental and interpretation guidance |
| `factory.evidence` | Evidence and decision/work-record interfaces |

Read the actual declarations in [the CC tree](../../../jiuwenswarm/factory/ccs/) for complete schemas, IDs, inputs and outputs. At this snapshot there are 16 `cc.yaml` declarations, including nested components; this inventory is not an invocation count. The parent `engine.expert_streaming` declaration is version 2.0.1; earlier frozen recordings used 2.0.0. [The handoff](../../demo/recovery/HANDOFF.md) explains the slice-link revision. Do not retroactively attribute new metadata to older experiments.

### How expert fill changes llama.cpp

Ordinary mapped weight access still needs the operating system to make missing pages resident. Our source integration adds a callback opportunity around CPU graph execution to prepare selected expert ranges. Demand fill uses buffered parallel reads before the demand computation consumes those bytes. It aims to control and overlap expensive I/O; it does not eliminate the need to read weights.

The [expert_fill material](../../../jiuwenswarm/factory/ccs/expert_streaming/components/expert_fill/component.yaml) declares `mmap_advice` and `router_prefetch` as source prerequisites. Integrating these patches does not imply their runtime features were enabled. The proof run enabled fill while leaving predictive prefetch switches off. The separate historical improvement included `expert_pregate` predictive reads. Extra speculative reads can be unused or duplicated; prediction accuracy alone is not readiness or a speed result.

`mmap` and memory-advice facilities are operating-system mechanisms, not inventions of this branch. Our component packages a specific engine integration and configuration of such mechanisms. See [NODE-EXAMPLE.md](NODE-EXAMPLE.md) and the component source map for engine regions and integration points.

## Contract, ontology and task revisions

The engineering task specifies the objective, allowed work, source, resources and budget. The frozen lab contract fixes the workload and correctness/comparison conditions. A small task file references these larger existing definitions rather than restating every schema.

Full task inputs live in [tasks](../../../jiuwenswarm/factory/tasks/); frozen contracts in [contracts](../../../jiuwenswarm/factory/contracts/); interface schemas in [schemas](../../../jiuwenswarm/factory/schemas/). The proof task used `qwen36-quick-v1`, not the same workload as historical J-OM13.

The system ontology describes engine regions and quantities. `expert_weight_readiness` connects selected-expert computation, weight ranges, read requests, page cache and readiness. Work-node kinds describe engineering actions such as inspect/integrate/build/measure/decide. Named references and validation provide targeting and traceability; they neither derive the workflow automatically nor prove that edits fulfill the ontology. Generic evidence requirements also have enforcement gaps described in [RSI-HANDOFF.md](RSI-HANDOFF.md).

For the proof task, the broad initial graph included baseline rebuilding and AB work prohibited by the operator. The agent cancelled those nodes and used one correctness screen. Revision 3 represented integration complete with candidate build ready; later revisions recorded build/screen completion and the final decision. Viewing or replaying a revision reconstructs that recorded state; it does not redo those operations. This adaptation is real, while the initial template remains broader than necessary.

## Results and attribution

| Record | What happened | Interpretation and limits |
|---|---|---|
| Run 4, task `bd173c08...` | Agent integrated components and built candidates; endpoint runs 903.95 to 785.22 ms/token; incremental fill/pregate comparisons recorded | A real campaign, but endpoint numbers are single runs, not the later direct headline ABBA; do not multiply incremental ratios |
| J-OM13, image `1274abb8...` | Separate historical fill plus predictive-read experiment: 841.4975 to 711.425 ms/token | 15.5% lower decode time / 18.3% higher throughput; four repeats per headline arm, all 12 observations retained; warm-cache experiment with starting residency not recorded |
| Run 5, task `53db4945...` | Stopped by operator; regressions and null trials retained; no component kept | Not the headline improvement; do not confuse excluded factory Run 5 with J-OM13 observation `005-factory` |
| Recorded task `e5b8d4b7...` | Fill-only task, two null comparisons, operator interventions recorded | The old approximately 6:46 video shows an inconclusive task, not the J-OM13 experiment |
| Proof task `cc5e8585445c484ba4d5b5b0dd96c31c` | Operator-prescribed integrate/build/screen sequence accepted in 3 turns, 13 min 10 s; image `a15f04f0...` | Demonstrates functioning capsule application and a completed build/screen, not measured acceleration |
| J-ASK1 | One-round 32-token ABBA for the proof image; 7.6% lower mean time, below the 23.4% gate | Null result, not a confirmed speed improvement |

The [November 12 status](STATUS-2026-11-12.md) links Run 4/5 receipts. The [recovery handoff](../../demo/recovery/HANDOFF.md) distinguishes J-OM13 from the recorded task. The [proof-run record](../../demo/recovery/proof-ask-1/README.md) contains the complete operator instruction, component commits, build and screen references and J-ASK1 results.

The proof run applied three separate commits: `133bdac08` mmap advice, `679bd0e1e` router prefetch prerequisite and `885eec824` expert fill. Build `3445e556` records 165 seconds, CUDA 12.6 SM87 and image `a15f04f0...`. Screen `bbc85611` matched the frozen stdout `cad62aa9...`. Component evidence recorded active fill and nonzero calls/reads. The contract-level instrumentation checks were **0/2**, because the fill-only source lacked reporting/thread-name patches 08/09. Component engagement does not make these missing checks pass.

Genuine terminal request/response captures demonstrate functionality, not HTTP API execution and not an apparent-speed comparison. Later Jifan inspection/replay and edited presentation footage are demonstrations of evidence tools, not fresh Jetson builds or inference. Heavy operations share CPU, memory and storage; separated captures preserve the evidence story, but this does not establish measured recording overhead or an isolated 80% cache penalty.

## Known limitations and unfinished work

- **Scope and agency:** techniques and the proof-run scope were supplied by people. The agent applied declared knowledge and chose actions within it; there is no claim of independent technique discovery or an advanced autonomous planner.
- **Correctness:** identical greedy output on fixed workloads is a narrow regression check, not broad model quality or numerical equivalence across workloads.
- **Measurement:** null and invalid experiments remain null/invalid. Cache state, contention, settings and instrumentation affect comparability. Nsight traces incur profiling overhead and support mechanism analysis, not clean speed comparisons.
- **Provenance and distribution:** slim exports omit large artifacts; some full logs/models/images live outside Git. Summaries use abbreviated hashes. A source clone alone is not a reproducible full lab environment.
- **Export integrity:** later review found that credential redaction damaged metric names and made two exported graph JSON files invalid. The staged presentation used recovered revisions checked against the source store. Do not replay malformed exports or assume this documentation fixes the exporter; validate schema and replay against authoritative records.
- **Ontology/enforcement:** references and graph validation are useful but not semantic proof. Read the existing headroom notes before claiming every evidence requirement or dispatch race is enforced.
- **Hardware transfer:** this branch's CUDA build and empirical results are Jetson-specific. Spark, other GPUs, other engines, new model sizes and broader workloads need independent qualification.
- **Future components:** catalog entries and CPU-tested development work do not establish Jetson speedups. Adaptive streaming policies, broader placement sweeps and several follow-up measurements remain open.

## How a teammate can use the branch

1. Clone `Stellven/jiuwenswarm`, select `cc-siminfeng` and record the actual commit. Initialize the pinned submodule with `git submodule update --init --recursive`; this requires access to `Muxite/siminfeng`. Do not substitute its latest HEAD when reproducing a pinned run.
2. Read this record, [REPOS.md](REPOS.md), [RUNBOOK.md](RUNBOOK.md), [TASK-GRAPH.md](TASK-GRAPH.md) and the actual CC/task/contract files. Existing runbook commands target Satay paths and versions; adapt them deliberately in an owned environment. Do not assume Satay remains available.
3. Begin with read-only inspection of the proof instruction and evidence. Verify completed builds, immutable image IDs and lab outcomes rather than treating submission or a graph state alone as success. Missing package artifacts must be obtained separately; never fabricate them.
4. For new execution, inventory the host and queue, resolve model/image/source identities, set a finite budget and keep builds separate from measurements. Use personal credentials and preserve other users' work. Check actual queue state; old handoff service-status text is historical.
5. Change one bounded thing and retain the evidence for rejection as well as success. A useful next step is a reusable CC improvement, not a new control platform.

The local-only [RSI assignment](../../rsi/2026-11-13/README.md) proposes builder reuse as the primary task and power-aware AB decisions as a fallback. Its fixture observations are opportunities, not implemented speedups. The distinction matters: applying an existing capsule improves a candidate engine; RSI changes the reusable capsule for later applications.

## Review receipt

This documentation update inspected the fetched published tip, the local commit's raw parent/tree difference, declarations, component material, task/ontology docs, runbook, status and proof/recovery records. It changes documentation only. No build, inference, historical measurement, credential migration, commit or push was performed as part of this update. Runtime behavior and fresh-machine installation were not requalified. See the Git diff for the exact documentation changes.
