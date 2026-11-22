# Software factory

The software factory (`jiuwenswarm/factory/`) lets one JiuwenSwarm agent improve a piece of software, here an inference engine, through Capability Capsules (CC v2). The agent reads evidence, records a decision, calls capsules, and decides again. The host enforces authority, durable identity and job lifecycle; it never picks actions. It runs next to the M1 research runtime and does not replace it ([migration](MIGRATION.md), [amendment](AMENDMENT.md)).

## Parts

| Part | Where | Doc |
|---|---|---|
| Controller and store: tasks, revisions, decisions, runs, evidence | `controller.py`, `manager.py`, `store.py` | [CONTROLLER.md](CONTROLLER.md) |
| Revisable task graph | `taskgraph.py` | [TASK-GRAPH.md](TASK-GRAPH.md) |
| Construction loop: source, build and execution identities | `builder.py`, `build_job.py`, `loop.py` | [CONSTRUCTION-LOOP.md](CONSTRUCTION-LOOP.md) |
| Telemetry, live monitor and story view | `telemetry.py`, `monitor.py`, `story.py` | [TELEMETRY.md](TELEMETRY.md) |
| Job packages | `job_packages.py` | [CC-JOB-PACKAGES.md](CC-JOB-PACKAGES.md) |
| Lab kit: job queue, image builder, guarded engine run, A/B runner | `labkit/` (bundled; `FACTORY_LAB_ROOT` switches it), wrapped by `jobs.py` | [REPOS.md](REPOS.md) |
| Outside sources (engine checkouts, packs, models) | `config.py` (`SOURCE_DEFAULTS`, `${FACTORY_...}` in task files) | [REPOS.md](REPOS.md) |
| Factory runs web page and API | `gateway/channel_manager/web/factory_http.py`, `channels/web/frontend/src/features/factoryRuns/` | [FACTORY-RUNS-HTTP.md](FACTORY-RUNS-HTTP.md) |
| Task contracts, format 2 | `contract_v2.py`, `schemas/contract-2.schema.json`, `contracts/` (for example [star-deepseek-v2](../../../jiuwenswarm/factory/contracts/star-deepseek-v2.json)) | [CONTRACT.md](CONTRACT.md), [NODE-EXAMPLE.md](NODE-EXAMPLE.md) |
| Lab manager, lab mailbox (directory or HTTP), shipped engine images or source, and stand-in lab agents | `lab_manager.py`, `lab_mailbox.py`, `lab_http.py`, `lab_payload.py`, `lab_build.py` (source bundles built in the lab), `lab_agent.py`, `ccs/lab_manager/` | [LAB-MANAGER.md](LAB-MANAGER.md) |
| CC v2 protocol changes | `jiuwenswarm/ccv2/` | [CCV2-REVISION.md](CCV2-REVISION.md), [../../ccv2/README.md](../../ccv2/README.md) |

CLI: `jiuwenswarm-factory` (also `jiuwenswarm factory`), with `init`, `run`, `ask`, `story`, `plan`, `export`, `telemetry`, `monitor`, `lab-agent` and `lab-server`.

## Capsules

`jiuwenswarm/factory/ccs/` holds 52 capsules. With the 8 expert-streaming components, the catalog lists 60 entries. `ccs/atlas-names.json` gives each one a display name and kind:

- **Builders (16):** write the source for one engine component. A builder is the method that builds the code, not the component. The five used on the DGX Spark are `expert_weight_cache`, `weight_placement_planner`, `expert_demand_predictor`, `batch_layout_mapper` and `observability_event_recorder`. Each carries `SOURCE-MAP.md` (the llama.cpp anchors to edit, read or protect), `METHOD.md` (how to verify) and `GUIDE.md` (how to build).
- **Analysis (22):** read traces, counters and profiles and return findings that a verifier can recompute.
- **Tools (11):** run an existing lab, runner or benchmark and return a verified receipt. The lab manager sends work to a lab agent and records its checked report.
- **Factory workers (11):** one factory step each, such as evidence intake, qualification, integration or follow-up method.

Each release is sealed. After editing a capsule, bump its `cc.yaml` version and run `scripts/factory/reseal_capsules.py`; `tests/factory/test_capsule_release_pins.py` enforces this.

## Component map

Each builder's `ONTOLOGY.yaml` is the factory's component map for the engine it changes. It names the engine regions the builder modifies, the quantities it reports and the slices a task can target (`constraints.engine_slice`). `jiuwenswarm/factory/ontology.py` checks these names. The map is written from code that runs: every quantity names the line the engine prints it on, and each builder's `SOURCE-MAP.md` gives the source anchors it edits.

A separate System Ontology describes inference engines in generic node types (its draft 0.9 has 44 types). It is not part of this branch. It can be added later without changing the factory code:

- The checker ignores fields it does not know, so a slice can carry the types it implements (for example `node_types: [expert-cache, expert-fetch]`) and the file can carry its own mapping block.
- The checker should then validate those names against a pinned copy of the node types, in the same way it validates regions and quantities today.
- Editing a capsule's `ONTOLOGY.yaml` changes its sealed release: bump its `cc.yaml` version and reseal, as for any capsule edit.

Recorded runs keep the ontology set they were pinned to. The 2026-11-20 contract `star-deepseek-v1` is one example.

## Tests

`tests/factory` and `tests/ccv2` need Linux (`fcntl`). They use the bundled lab kit, so no other checkout is needed.

```bash
python -m pytest tests/factory tests/ccv2 -o addopts="--asyncio-mode=auto" -m "not docker"
```

## A full run

The [DGX Spark demo of 2026-11-20](../../../ops/spark/demo-20261120/README.md) records one contract-to-result run: five builders applied to llama.cpp running DeepSeek V4.1 Flash, measured against stock llama.cpp and Strata.
