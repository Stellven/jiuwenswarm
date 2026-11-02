# SIMLAB user and developer guide (phase 1)

SIMLAB builds, runs, records and reports physics experiments for AI4R or any agent. It never judges results: the requester owns the science. Phase 1 provides the experiment core, the MuJoCo 3.17.0 executor, authoring tools, records, checks, world-state save, restore, branch and replay, traces and queries, the capability registry and the doctor, all through one tool interface (MCP server, Python client and CLI with the same operations).

## Install and start

```sh
cd labs/physicalai_sim
docker build -f docker/Dockerfile -t simlab-runner:dev .      # from uv.lock; base images pinned by digest
python tools/runner.py up --data-dir ~/simlab-data              # no network, no published port, no secrets
python tools/runner.py exec -- simlab doctor                    # readiness with typed failures
```

Run data lives in the declared data directory (`SIMLAB_DATA_DIR`, outside the repository; the store refuses a directory inside one). The service listens only on `<data dir>/runner.sock` (JSON-RPC 2.0). For development without Docker: `uv sync --frozen`, then `SIMLAB_DATA_DIR=~/simlab-data .venv/bin/simlab serve`.

## Tools

- MCP (stdio): `docker exec -i simlab-runner simlab mcp`. Each operation is one tool.
- Python: `from simlab.interface.client import Client; c = Client("~/simlab-data")`, then `c.<operation>(**params)`.
- CLI: `simlab <operation> --params '<json>'` (or `--params -` for stdin); `simlab ops` lists them.

| Operation | Purpose |
|---|---|
| `capability` | What is supported, excluded (with reasons) and missing |
| `draft_create`, `geometry_put`, `collision_put`, `model_file_put`, `procedure_put`, `intervention_put`, `measurement_put`, `observation_put`, `component_put`, `artifact_list`, `artifact_get`, `artifact_delete` | Author an experiment in a draft |
| `bind` | Freeze the draft into an immutable manifest and return the experiment |
| `validate` | Every finding at once (typed `{code, message, path, severity}`) |
| `submit`, `status`, `wait`, `result`, `cancel` | Run and follow it |
| `query`, `fetch` | Traces, measurements and events by run, arm, trial, time range and signal |
| `replay`, `branch` | Exact replay (same machine and build); a new draft from a saved checkpoint |

Reserved for later phases: `preview`, `pilot`, `release_inspection` (phase 2), `fresh_replication` (phase 3), `pause`, `resume`, `stream` (phase 4).

### Writing an experiment

- **Scene:** an MJCF model file bound to an arm at the `scene` extension point; `${name}` placeholders are set by arm parameters, factor levels and random variables.
- **Configuration:** `resolved_configuration` declares every engine setting (timestep, integrator, solver, iterations, tolerance; cone, impratio, gravity and flags when used). Auto-reset after a numerical failure is always disabled, so failures surface.
- **Design:** arms, factors, conditions, pairing, replicates, episodes and randomness (seed policy, random variables). Counted comparisons must declare unit of inference, pairing, aggregation and required precision.
- **Procedure:** steps (with optional end-of-step requirements), initial state, events (contact begin and end, threshold crossings), interventions, and checkpoints at declared points.
- **Signals:** `time`, `qpos:<joint>`, `qvel:<joint>`, `xpos:<body>`, `xipos:<body>`, `xquat:<body>`, `linvel:<body>`, `angvel:<body>`, `ctrl:<actuator>`, `act:<actuator>`, `actuator_force:<actuator>`, `sensor:<name>`, `energy:{potential,kinetic,total}`, `momentum:total`, `contact:count`, `contact:penetration_max`, `contact:normal_force:<geom>[:<geom>]`, `contacts` (a contact table).
- **Measurements:** trial scope (`final`, `initial`, `at_time`, `max`, `min`, `mean`, `max_abs`, `range`, `displacement`, `first_crossing_time`, `period`, `fit_acceleration`, `decay_rate`, `relative_drift`, `event_time`, `event_count`, `velocity_ratio_at_event`, `component`), pair scope (`pair_difference`, `pair_ratio`), set scope (`set_mean`, `set_std`, `set_min`, `set_max`, `set_count`).
- **Components:** `controller` code defines `control(obs, params, ctx)`; `measurement` code defines `measure(traces, params)`. Both run confined: kernel-filtered sockets and process creation, rlimits, a credential-free environment, and recorded denials.
- **Checks:** watchdogs (non-finite state is INVALID; declared speed, penetration and energy bounds stop a trial as COMPLETED), reruns over engine settings and assumed values, independent recomputation of every standard measurement, known-answer checks and control arms. A failed required check marks its measurements invalid and keeps them visible.

Trial attempt statuses: `COMPLETED`, `INVALID` (`numerical_failure`, `protocol_violation`, `incorrect_intervention`, `missing_required_observation`, `corrupted_record`, `invalid_state_or_action_delivery`), `LIMIT_REACHED`, `INTERRUPTED`, `BLOCKED` (a missing dependency). Every attempt is kept; there are no automatic retries.

## Checks and benchmarks

```sh
python tools/check_groups.py --group core|executors|benchmark|all       # in the image: no network, 4 GB cap, read-only source
python tools/check_groups.py --group core --negative-control source-change   # exit 2
python tools/check_groups.py --group core --negative-control timeout         # exit 124
python tools/import_check.py      # no AI4R import under labs/physicalai_sim
python tools/port_audit.py        # no SIMLAB host port
```

Evidence goes to `.test_logs/simlab/<group>/<run>/` (`launch.json`, `source-manifest.json`, `pytest.log`, `junit.xml`, `result.json`). Live tests are opt-in (`--live`) and otherwise reported as skipped. SIMLAB-Bench is described in `benchmarks/simlab_bench/README.md`.

## Operator tools

`tools/feasibility.py` runs the X1.1 local-fit check (the AI4R app, one governed model request and a simulator together, with resource sampling). `tools/agent_only.py` runs the X1.4 agent-only check. `tools/fresh_checkout.py` runs the X1.6 reproduction from a clean clone. `tools/measure.py` records the resources of any command. Every run appends a row to `missions/PAS-M1/compute-log.csv`.
