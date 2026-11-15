# Dynamical Workflow Software Factory

The existing JiuwenSwarm **Workflow** page presents a real source-producing factory. A task and its source artifacts select executable internal stages from existing subworkflows. The resulting cross-parent production graph generates a C++ source project, compiles its CPU reference, validates its mathematics and publishes the source package.

- [Short manager update](MANAGER_UPDATE.md)
- [Primary generated Ascend source](deliverables/ascend-source/source/src/ascend/)
- [Standalone source ZIP](deliverables/ascend-source/ascend-generated-source.zip)
- [Portable production recordings](recordings/README.md)
- [Technical acceptance and evidence](sf-001/tasks.md)
- [Factory execution/API documentation](../../../../jiuwenswarm/software_factory/README.md)

## Start the existing host with recorded production

From the repository root:

```sh
python -m pip install -r jiuwenswarm/software_factory/requirements-demo.txt
python -m jiuwenswarm.software_factory.demo --build
```

The first build needs Node.js/npm; later starts omit `--build`. The launcher serves the existing host frontend and factory API together on **127.0.0.1:5175**, checks its source/build hashes and opens the packaged recording data without the original run directories. A prebuilt presentation release can start without Node.js. The host sidebar and layout are retained.

Open:

```text
http://127.0.0.1:5175/?view=workflow&lng=en&recording=11a6ce02166b4618baea6db59aaf44ec
```

Use `python -m jiuwenswarm.software_factory.demo --check` to validate local presentation inputs without starting execution.

## Present the production process

1. Start with the recorded request and existing pool. The target is Ascend/CANN source production with separate CPU reference checks. Click **Start walkthrough**; backend-paced original events stop at actual publication checkpoints.
2. Continue to **Internal stages composed**. Function extraction contains `Discover operators → Extract function`; scalar and cooperative implementation each contain `Extract function → Lower`. The task selects the first parent's extraction child and the implementation parents' lowering children, leaving their other children idle. The composition view shows those exact origins and their new dependencies for each real source operation.
3. Continue to **Ascend C++ generated**. Open **Source**: `src/ascend/router.cpp` contains actual CANN math calls. **Code Diff** shows the upstream CUDA algorithm beside the generated Ascend C++.
4. Continue through actual CPU validation. **Run log** retains the worker lifecycle and complete subprocess commands. Select the CPU build or `strata_core_test` command to inspect argv, working directory, PID, exit and literal stdout/stderr. **Build & verification** shows 352 CPU comparisons separately from native-device/model outcomes.
5. Open **Downloads**, save the source ZIP and inspect `src/`, `include/`, CMake, tests and scripts. Its bytes are the original factory-published artifact.
6. Optionally select the historical normalization recording to compare its genuinely different task-selected execution path. Its older library is retained honestly; it does not claim the corrected run's multi-child registry.

Use **Continue**, **Back stage**, **Next event** or the event pointer to inspect the recording at a human pace. Rewinding removes future outputs. Backend SSE carries the original event bytes; replay never dispatches a factory task. Graph changes come from recorded backend graph events, not a frontend animation timeline.

## Reproduce a new engineering task

New construction remains a separate explicit action in the task editor or CLI:

```sh
python -m jiuwenswarm.software_factory.cli --root .factory-runs \
  --backend cpu --task-file TASK.json --goal value.report
```

This executes source acquisition and engineering stages. It is unnecessary for the recorded presentation.

## Current verification scope

Primary run `11a6ce02166b4618baea6db59aaf44ec` fixed STRATA at `13eedf552417a6a791a7d13c6597e24300ee3a09`. Its frozen pool, six actual partial internal-stage imports, 132 events, 54 artifacts and 27-file source package are retained. The generated CANN core includes router, activation and aggregation; its separate CPU reference built and passed 352 numerical comparisons, and the detached ZIP rebuilt successfully.

Native target compilation, device execution, complete original-model inference and original-model comparison remain **NOT_RUN / NOT_COMPLETE**. CPU results do not establish Ascend validation. The full factory acceptance remains in [sf-001/spec.md](sf-001/spec.md); this presentation does not reduce it.
