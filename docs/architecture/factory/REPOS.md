# Two repositories, one software factory

The factory is a **software factory that uses CCs** (Capability Capsules) to improve software — here, an inference engine. It is not a factory of CCs.

| | `Stellven/jiuwenswarm` branch `ai4r/iterative-cc-factory` | `Muxite/siminfeng` (submodule `lab/siminfeng`) |
|---|---|---|
| Role | The software factory: the agent loop and the CCs | The Satay lab: the hardware-facing tools and the research record |
| Holds | controller (agent turns, budgets), evidence store, task graph, durable job client, Manager (image admission, evaluation), CC runtime (ccv2 + MCP), capsules (`engine.expert_streaming`, builder, inspector, lab_client, evidence, methodology), story/replay/telemetry/monitor/views, demo | job queue `bin/jobq` (+ `bin/heavy`), `cc/build_engine` (CUDA image builds), `cc/om_run` (one containerized engine run with telemetry, watchdog, page-cache and contention records), `cc/abrun` (ABBA experiments and gate), patches and research tools, experiments (J-OM*, J-XS*), evidence logs, campaign status |
| Lineage | descends from AI4Research-Main `141c1c4` via the CC-v2 donor branch | independent research repo (c1/c2 campaigns) |
| How they connect | `jiuwenswarm/factory/config.py` points `SIMINFENG_ROOT` at `~/projects/siminfeng` (the live host lab with the shared queue); on a fresh clone without it, the pinned submodule `lab/siminfeng` is used | the factory calls `bin/jobq`, `build_engine.py`, `om_run.sh` and `abrun` as subprocesses inside durable jobs |

Update the submodule pin with `git -C lab/siminfeng fetch && git -C lab/siminfeng checkout <commit> && git add lab/siminfeng`.
