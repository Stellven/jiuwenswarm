# PhysicalAI-Sim lab: SIMLAB application

The SIMLAB simulator, the application installed by the PhysicalAI-Sim lab. The AI4Research labs brief defines a lab as an AI4R fork, its capability capsules, and installed application code that owns domain behavior (physics, controls, observations).

This folder holds everything for the lab and is self-contained, like `jiuwenbox/`. It imports no AI4R code. Agents reach the simulator through its MCP server, Python client or CLI.

| Part | Location |
|---|---|
| Spec, Spec Kit task records, verification snapshots and reports for milestone PAS-M1 | `missions/PAS-M1/` |
| SIMLAB application: runner, executors, libraries, model interface, tools (added with the code) | `pyproject.toml`, `src/simlab/`, `tests/`, `docker/` |
| Benchmarks | `benchmarks/` |
| The simulator's own user and developer docs | `docs/` |
| AI4R capsules that operate it (the only lab code inside AI4R, which loads capsules from there) | `jiuwenswarm/research/capsule_extensions/simlab_*/` |

The build input in `missions/PAS-M1/source/` is the authority for what goes here.
