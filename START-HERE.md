# 20261113 Jetson Software Factory Start Here postpresentation

This branch documents and implements the software-factory proof of concept developed on **Satay, NVIDIA Jetson Orin Nano Super 8GB**.

Start with the [branch record](docs/architecture/factory/20261113%20Jetson%20Software%20Factory%20Branch%20Record%20postpresentation.md). It covers the architecture, CCs, task/contract/ontology relationships, completed work, results, failed or inconclusive trials, and reuse instructions.

- **Factory integration proof:** task `cc5e8585...`, image `a15f04f0...`, completed build and fixed-workload correctness screen. Not a speed claim.
- **Historical performance:** separate J-OM13 fill-plus-predictive-read experiment, image `1274abb8...`, 841.5 to 711.4 ms/token. Not the fill-only proof run.
- **Negative results:** Run 5 stopped without a kept component; the recorded fill-only task and J-ASK1 were inconclusive.
- **Next hardware:** Spark requires separate qualification; its follow-up work is not a Jetson branch result.

## Full CC catalog for lab developers

[All 16 factory CCs and 4 runtime examples](docs/architecture/factory/20261113%20CC%20Catalog%20and%20Lab%20Integration%20postpresentation.md) include full declarations, inputs/outputs, every material link, native entry points and the lab integration boundary.

## Read and reuse

1. [Repository boundary](docs/architecture/factory/REPOS.md): JiuwenSwarm owns the factory; Siminfeng is the hardware-facing lab and is pinned as `lab/siminfeng`.
2. [Jetson operating runbook](docs/architecture/factory/RUNBOOK.md): historical prerequisites and paths to inspect before adapting a new owned environment.
3. [Proof instruction and results](docs/demo/recovery/proof-ask-1/README.md): what the operator prescribed, what the agent did and what the screen established.
4. [Task graph](docs/architecture/factory/TASK-GRAPH.md) and [engine/node ontology](docs/architecture/factory/NODE-EXAMPLE.md): traceability and replay, not automatic scheduling or semantic proof.
5. [CC declarations](jiuwenswarm/factory/ccs/), [tasks](jiuwenswarm/factory/tasks/) and [contracts](jiuwenswarm/factory/contracts/): full source definitions.
6. [Local RSI assignment](docs/rsi/2026-11-13/README.md): bounded proposed improvements, not already demonstrated optimizations.

## Historical presentation material

The [recovery package start page](docs/demo/recovery/START%20HERE.md), [proof run](docs/demo/recovery/proof-ask-1/README.md) and [November 12 status](docs/architecture/factory/STATUS-2026-11-12.md) retain original evidence and context. Replay and offline views do not submit builds or rerun inference. Host service status and paths in historical handoffs are not current-state guarantees.

The November 13 presentation was successful according to the presenter. No new presentation is planned here; the next effort is deeper experiments and reusable capabilities.
