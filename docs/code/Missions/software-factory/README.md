# Dynamical Workflow Software Factory

This branch integrates a source-producing engineering factory into the existing
JiuwenSwarm Sidebar → Workflow page. Tasks are compiled into explicit acceptance
contracts; actual source discovery then selects executable implementation stages.
The same executor builds and validates the generated C++ project, packages its
source, and retains immutable commands, artifacts and source recipes.

- [Short manager update](MANAGER_UPDATE.md)
- [Factory startup and API](../../../../jiuwenswarm/software_factory/README.md)
- [Task and acceptance specification](sf-001/spec.md)
- [Engineering records and verification](sf-001/tasks.md)
- [Independent audit](reviews/report-cycle3.md)
- [Generated STRATA source projects](deliverables/)
- [Recorded workflow replay](replay/README.md)

## Start the integrated system

From the repository root with the host Python dependencies available:

```sh
python -m jiuwenswarm.software_factory.cli --root .factory-runs --serve --port 19000
```

From `jiuwenswarm/channels/web/frontend`:

```sh
npm ci
FRONTEND_PORT=5175 npm run dev
```

Open `http://localhost:5175/` and select **Workflow**. The task editor accepts a
description, source scope, capability requirements and acceptance criteria. Source
generation, validation and artifact delivery use actual subprocesses and files.

## Inspect an existing run without executing it again

Use **Replay** on a recorded run or open an exported replay HTML. Playback reads
the historical event stream. It does not clone, build, invoke models, or create a
new factory run. Source and artifacts appear at their recorded publication event.

```sh
python -m jiuwenswarm.software_factory.replay_export \
  --run-dir .factory-runs/RUN_ID --output workflow-replay.html
```

## Reproduce an engineering task

```sh
python -m jiuwenswarm.software_factory.cli --root .factory-runs \
  --backend cpu --task-file TASK.json --goal value.report
```

This executes a new task. Use the replay command above for presentation of an
existing recording. The generated project's README and CMake files are its
standalone build entry. Technical verification records preserve the exact scope
of each recorded result.
