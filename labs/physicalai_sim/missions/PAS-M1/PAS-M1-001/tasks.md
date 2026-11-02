---
description: "TASK-native work and acceptance/evidence correspondence"
---
# Tasks: PAS-M1-001 - Base simulator
**TASK**: [TASK.md](TASK.md) | **Spec / Plan revisions**: spec r1 (Clarifications 2026-10-30) / plan r1
**Feature directory**: `labs/physicalai_sim/missions/PAS-M1/PAS-M1-001/`

Verification work is required as defined in spec.md and plan.md. This is the only implementation work list. Do not generate a separate implementation checklist, authorization, review or handoff card.

Before starting each work item, state what will be run, what will be inspected, and the result that would show the implementation is wrong (owner's coding prompt). The last column of plan.md "Verification Design" gives that result for every V ID. Every run, check-group run and benchmark run appends a row to `missions/PAS-M1/compute-log.csv` (T075).

## Work Items
Format: `- [ ] T001 [P?] [US1] Description; block/AC/V references; actual path`. Paths are relative to `labs/physicalai_sim/`. [P] requires disjoint changes and satisfied dependencies; it is not permission to spawn agents or publish. Story labels follow spec.md user stories US1 to US8.

### Foundation / shared definitions (B00)
- [x] T001 Create the package skeleton and `pyproject.toml` (Python 3.12; MuJoCo 3.17.0, NumPy 2.5.x, Pydantic 2.14.x, `mcp` 2.3.0, pytest 9.2.x) and lock with `uv lock`; B00, AC-017; `pyproject.toml`, `uv.lock`, `src/simlab/__init__.py` — done 2026-11-01: pyproject.toml (exact pins), uv.lock (46 packages), src/simlab/__init__.py
- [x] T002 Write `docker/Dockerfile` (base `python:3.12-slim` pinned by digest, libseccomp bindings, `uv sync --frozen`, non-root user) and `docker/compose.yaml` (service `simlab-runner`, `network_mode: none`, no published ports, no secrets, read-only root, `/data` bind from `SIMLAB_DATA_DIR`); B00, AC-017, AC-019; `docker/` — done 2026-11-01: docker/Dockerfile (python:3.12-slim and uv 0.5.9 pinned by digest; non-root), docker/compose.yaml (network none, no ports, no secrets, read-only root, /data bind); tools/runner.py
- [x] T003 [P] Add `.gitignore` for `missions/**/evidence/` and the held-out benchmark volume path; B00; `.gitignore` — done 2026-11-01: .gitignore (evidence/, held-out paths, .venv)
- [x] T004 Create `missions/PAS-M1/compute-log.csv` header (date, task, what ran, wall s, CPU s, peak RAM MB, peak VRAM MB, disk MB, notes) if absent; owner compute tracking; `missions/PAS-M1/compute-log.csv`
- [x] T005 Build the image and record the image digest and build resources; B00; evidence `evidence/<run>.md` — done 2026-11-01: image sha256:ea1e9159f716… (174 MB, build_id df0cfd61…, final phase 1 source; evidence/build/); earlier builds 2c83267e…, 8ad2b374… superseded

### Block B13 - Local feasibility (X1.1, first per build order)
- [x] T006 [US1] Implement `tools/feasibility.py`: start the unmodified AI4R app through `deploy/m1/ai4r.py` (`127.0.0.1:5175`), wait for the owner's sign-in, make one real request through AI4R's control API (record the chosen action, plan U-05), run a MuJoCo pendulum loop in `simlab-runner` at the same time, and sample cgroup memory and CPU, `nvidia-smi` and disk; write `feasibility.json`; B13, AC-001; `tools/feasibility.py` — done 2026-11-01: tools/feasibility.py (start/run/stop; AI4R codex.chat via session.create; resource sampling via tools/hostmon.py)
- [ ] T007 [US1] Execute V-X1.1 with the owner present for sign-in; retain raw samples and AI4R logs; record PASS, FAIL or BLOCKED with evidence; if it fails, raise A-13 to the owner (TASKS §6 C-03); B13, AC-001, V-X1.1; `evidence/<run>.md` — executed three times, not PASS: run 2 FAIL (signed-in Free account lacks gpt-6.1-sol; team workspace blocks device-code sign-in) [RUN-x11-20261101](evidence/RUN-x11-20261101.md); open until an entitled sign-in (TASKS §6 Q-09)

### Block B01 - IF-001@r1 contracts
- [x] T008 [US2] Implement the IF-001@r1 models (Experiment, Result, Manifest, typed error, every enum fixed in TASK §4); B01, AC-002; `src/simlab/contracts/` — done 2026-11-01: src/simlab/contracts/{enums,errors,records}.py
- [x] T009 [US2] Export JSON Schema labeled `simlab-if-001@r1` and add a drift check against the models; B01, AC-002; `src/simlab/schemas/`, `tests/core/test_schemas.py` — done 2026-11-01: src/simlab/schemas/ (4 records, drift check `simlab schema`)
- [x] T010 [US2] Write valid and invalid record fixtures and execute V-BLK-SCHEMA; B01, AC-002, V-BLK-SCHEMA; `tests/core/test_schemas.py` — V-BLK-SCHEMA PASS (12 tests) [RUN-cg-20261101](evidence/RUN-cg-20261101.md)

### Block B04 - Store, traces, provenance, query
- [x] T011 [US5] Implement SQLite store (WAL; write-once triggers on submitted experiments and manifests; append-only attempts), content-addressed blobs and `.npy` trace writer and reader with time-range slicing; refuse a data directory inside the repository; B04, AC-008, AC-013, AC-014; `src/simlab/store/` — done 2026-11-01: src/simlab/store/ (WAL, write-once triggers, attempts change once, blobs, data dir outside the repository)
- [x] T012 [US5] Implement provenance assembly (source revision; dependency, asset and model identities; configuration and randomness; package, run, trial and attempt IDs; raw evidence and analysis references) and the query and fetch logic; B04, AC-013, AC-014; `src/simlab/store/` — done 2026-11-01: src/simlab/runner/results.py (provenance, query, fetch, integrity verification)
- [x] T013 [US5] Execute V-BLK-STORE; B04, AC-008, AC-013, AC-014, V-BLK-STORE; `tests/core/test_store.py` — V-BLK-STORE PASS (5) [RUN-cg-20261101](evidence/RUN-cg-20261101.md)

### Block B02 - Authoring tools and manifest
- [x] T014 [US2] Implement drafts and artifact kinds (geometry, collision, model file, procedure, intervention, measurement, observation, component at a declared extension point) with per-artifact SHA-256; B02, AC-004; `src/simlab/authoring/` — done 2026-11-01: src/simlab/authoring/ (8 artifact kinds, primitives, bounding-box collision)
- [x] T015 [US2] Implement `bind` (content-idempotent `simlab-manifest`, immutable blobs, binding to one experiment) and the post-bind immutability error; B02, AC-004, AC-008; `src/simlab/authoring/` — done 2026-11-01: authoring bind (content identity; E_BOUND after bind)

### Block B03 - Validation
- [x] T016 [US3] Implement schema and semantic validators that collect every finding (objective kind never rejected; origin; parent; comparison completeness; zero trials; undeclared checkpoint; MJCF compile; asset hash; replay-breaking engine flags) using the error catalogue in contracts/; B03, AC-003, AC-005, AC-009; `src/simlab/validation/` — done 2026-11-01: src/simlab/validation/ (schema + semantic, all findings; unknown-field repair keeps semantic findings; one finding per defect across arms)
- [x] T017 [US3] Write one defect fixture per finding code plus clean controls and execute V-BLK-VALID; B03, AC-003, AC-005, AC-009, V-BLK-VALID; `tests/core/test_validation.py` — V-BLK-VALID PASS (15) [RUN-cg-20261101](evidence/RUN-cg-20261101.md)

### Block B06 - MuJoCo executor and sandbox
- [x] T018 [P] [US4] Implement the MuJoCo 3.17.0 executor: compile, step, apply the procedure's events and interventions, record per-step state arrays, events and contacts; B06, AC-006, AC-013; `src/simlab/executors/mujoco/` — done 2026-11-01: src/simlab/executors/mujoco/{scene,worker}.py
- [x] T019 [US5] Implement the worker sandbox (seccomp denial of `AF_INET`/`AF_INET6` sockets, `no_new_privs`, rlimits from declared limits, credential-free environment) applied before component code loads; B06, AC-004, AC-019; `src/simlab/executors/mujoco/sandbox.py` — done 2026-11-01: src/simlab/executors/mujoco/sandbox.py (seccomp BPF via prctl, rlimits, audit-hook denials recorded as events)
- [x] T020 [US5] Implement watchdogs (non-finite state → `numerical_failure`; declared physical bounds recorded and stopping the trial); B06, AC-009, AC-007; `src/simlab/executors/mujoco/watchdogs.py` — done 2026-11-01: worker watchdogs (non-finite, max speed, penetration, energy growth)
- [x] T021 [US5] Execute V-BLK-SANDBOX in the container; B06, AC-004, AC-019, V-BLK-SANDBOX; `tests/executors/test_sandbox.py` — V-BLK-SANDBOX PASS (in container) [RUN-cg-20261101](evidence/RUN-cg-20261101.md)

### Block B05 - Runner and experiment core
- [x] T022 [US5] Implement design expansion (arms, factors, conditions, replicates, episodes, pairing, seed policy) into trials, and pair and set measurement scopes; B05, AC-006; `src/simlab/runner/design.py` — done 2026-11-01: src/simlab/runner/design.py
- [x] T023 [US5] Implement the scheduler and worker lifecycle with attempt persistence, the six invalid reasons, divergence as `COMPLETED`, `LIMIT_REACHED`, `BLOCKED` arms for missing dependencies, cancel (running and queued), new run ID per execution, no verdict and no automatic retry; B05, AC-007, AC-008, AC-014; `src/simlab/runner/` — done 2026-11-01: src/simlab/runner/core.py
- [x] T024 [US5] Execute V-BLK-STATUS with the fake executor; B05, AC-006, AC-007, AC-008, V-BLK-STATUS; `tests/core/test_runner_statuses.py` — V-BLK-STATUS PASS (2; fake executor, block level only) [RUN-cg-20261101](evidence/RUN-cg-20261101.md)

### Block B07 - Checks
- [x] T025 [US5] Implement reruns over declared engine settings and assumed values ([confirm: 5] samples per arm) with variation reported and failure only beyond a declared required precision; independent recomputation of standard measurements from raw traces in separate code; anchoring; measurement validity; evidence level; B07, AC-009; `src/simlab/checks/` — done 2026-11-01: src/simlab/checks/ (rerun, recomputation in checks/recompute.py independent of simlab.measure, known answer, control arm, validity, evidence level)
- [x] T026 [US5] Execute V-BLK-MEAS; B07, AC-009, V-BLK-MEAS; `tests/core/test_checks.py` — V-BLK-MEAS PASS (17) [RUN-cg-20261101](evidence/RUN-cg-20261101.md)

### Block B08 - Save, restore, branch, replay
- [x] T027 [US6] Implement checkpoints (`mj_getState(mjSTATE_INTEGRATION)`, RNG state, pending-event queue, action history, step index, SHA-256) and restore into a fresh `MjData`; reject incomplete checkpoints; B08, AC-012; `src/simlab/state/checkpoint.py` — done 2026-11-01: worker checkpoints (mjSTATE_INTEGRATION, RNG, pending events, action history, step index) and restore
- [x] T028 [US6] Implement replay (recorded seeds and action sequence on the same image digest; `E_NOT_REPLAYABLE` otherwise) and branch (new draft with `parent = {checkpoint_id}`); bitwise digest comparison of per-step state and measurements; B08, AC-011; `src/simlab/state/` — done 2026-11-01: replay (recorded actions; E_NOT_REPLAYABLE across build/host) and branch (Service.op_branch)
- [x] T029 [US6] Execute V-BLK-STATE; B08, AC-012, V-BLK-STATE; `tests/executors/test_checkpoint.py` — V-BLK-STATE PASS (2) [RUN-cg-20261101](evidence/RUN-cg-20261101.md)

### Block B09 - Tool interface
- [x] T030 [US2] Implement the JSON-RPC 2.0 service over a Unix socket in the data volume (`simlab serve`) exposing every phase 1 operation and the authoring tools; B09, AC-015; `src/simlab/interface/rpc.py` — done 2026-11-01: src/simlab/interface/{ops,rpc}.py (JSON-RPC over a Unix socket; long paths fall back to a private runtime dir)
- [x] T031 [P] [US2] Implement the Python client; B09, AC-015; `src/simlab/interface/client.py` — done 2026-11-01: src/simlab/interface/client.py
- [x] T032 [P] [US2] Implement the CLI over the client (same operation names, inputs, outputs, error codes); B09, AC-015; `src/simlab/interface/cli.py` — done 2026-11-01: src/simlab/interface/cli.py
- [x] T033 [P] [US2] Implement the MCP server (`mcp` 2.3.0, stdio) over the client; host agents launch it with `docker exec -i simlab-runner simlab mcp`; B09, AC-015; `src/simlab/interface/mcp_server.py` — done 2026-11-01: src/simlab/interface/mcp_server.py (mcp 2.3.0 low-level server, stdio)

### Block B12 - SIMLAB-Bench F1, F5, adopted references, speed
- [x] T034 [US4] Create `benchmarks/simlab_bench/` following the Harbor authoring contract (case.json, public/, referee/criteria.json, stdlib oracle.py, test_oracle.py, README.md), the release manifest tool (SHA-256) and `smoke` and `campaign` profiles; B12, AC-020; `benchmarks/simlab_bench/` — done 2026-11-01: benchmarks/simlab_bench/ (Harbor-format cases, run_oracle.py, profiles smoke/development/campaign, tests/)
- [x] T035 [US4] Author cases TB-01 (small and large swing; elliptic integral by AGM) and TB-02 with their source tolerances (0.5% [confirm], 0.1%), three variants each; B12, AC-010, AC-020; `benchmarks/simlab_bench/cases/f1-tb01-*`, `f1-tb02-*` — done 2026-11-01: f1-tb01-pendulum, f1-tb02-free-fall (3 variants each)
- [x] T036 [US4] Author cases TB-03 to TB-08, three variants each, proposing each tolerance with a written reason in `referee/criteria.json`, marked `confirm: true` and frozen before the first run; include TB-06's frozen or over-damped and TB-08's gravity-off negative controls; TB-06 reference trajectory from an independent pure-Python RK4 with its own convergence test; B12, AC-010, AC-020, spec Clarifications; `benchmarks/simlab_bench/cases/f1-tb03-*` to `f1-tb08-*` — done 2026-11-01: f1-tb03 to f1-tb08 (3 regular variants each; TB-06 frozen and over-damped, TB-08 gravity-off negative controls; TB-06 reference by independent RK4 with convergence test); tolerances proposed with reasons, confirm: true
- [x] T037 [US6] Author case TB-09 (determinism and restore-and-continue) and the F5 replay cases, three variants each; B12, B08, AC-011, AC-020; `benchmarks/simlab_bench/cases/f1-tb09-*`, `f5-*` — done 2026-11-01: f1-tb09-determinism, f5-replay (3 variants each)
- [x] T038 [US4] Cite in each case README the adopted reference it uses (MuJoCo engine tests, Drake incline and friction tests, arXiv 2603.14634, ContactBench criteria, catalogue A.1), and include the MuJoCo version in each case manifest so a version change forces a rerun; B12, AC-021; case READMEs and `tests/core/test_case_manifests.py` — done 2026-11-01: references in each case README and case.json; engine version in case.json and the release manifest
- [x] T039 [US4] Implement `simlab bench run|report` (hardware inventory before each run, no retries, failed runs kept, three repeats in `campaign`, dated report folder with per-family results and no aggregate score) and `simlab bench speed` (pinned MuJoCo speed harness or recorded fallback, plan U-06; active contact and control); B12, AC-020, AC-021; `src/simlab/bench/` — done 2026-11-01: src/simlab/bench/ (run with inventory before each cell, no retries, isolated oracle, per-family reports; speed; admit)
- [x] T040 [US4] Freeze the F1 and F5 release (SHA-256 manifest) before any campaign run; B12, AC-020; `benchmarks/simlab_bench/releases/` — done 2026-11-01: release pas-m1-phase1-r1 frozen (85 files, sha256 1f1d345d…), before any campaign run

### Block B10 - Registry, doctor, resource records, compute log
- [x] T041 [US7] Implement the capability registry from conformance evidence (MuJoCo `admitted` only after its F1 cases pass; excluded entries with reasons such as Isaac Sim on this laptop; missing entries for phase 3 libraries); B10, AC-016; `src/simlab/registry/` — done 2026-11-01: src/simlab/registry/ (admission tied to the build)
- [x] T042 [US7] Implement `simlab doctor` (pinned versions; data directory declared, writable, outside the repo; read-only source mount; no credentials in env; executor network denied; seccomp available; host port audit; disk, memory and GPU inventory) with typed failures; B10, AC-016, AC-019; `src/simlab/doctor/` — done 2026-11-01: src/simlab/doctor/
- [x] T043 [US7] Implement resource records per run (wall, CPU via cgroup or getrusage, cgroup `memory.peak`, GPU and peak VRAM when used, disk written) and `simlab compute-log append`; B10, AC-016; `src/simlab/resources/` — done 2026-11-01: src/simlab/resources/ (ResourceMeter, compute-log append)
- [x] T044 [US7] Execute V-BLK-REG; B10, AC-016, V-BLK-REG; `tests/core/test_registry_doctor.py` — V-BLK-REG PASS (4) [RUN-cg-20261101](evidence/RUN-cg-20261101.md)

### Block B11 - Check groups, import check, port audit
- [x] T045 [US7] Implement `tools/check_groups.py` after `deploy/m1/capsule_checks.py`: groups `core`, `executors`, `benchmark`, `all`; runs in `simlab-runner` with `--network none`, `--memory 4g` [confirm] and a read-only source mount; writes `launch.json`, `source-manifest.json`, `pytest.log`, `junit.xml`, `result.json` to `.test_logs/simlab/<group>/<run>/`; exit 2 on source change, 124 on timeout; `live` tests skipped unless `--live`; resource record per group run; B11, AC-018; `tools/check_groups.py` — done 2026-11-01: tools/check_groups.py (host launcher + in-container runner; exit 2 and 124)
- [x] T046 [P] [US7] Implement `tools/import_check.py` (AST scan for AI4R imports under `labs/physicalai_sim/`) and `tools/port_audit.py` (host listening sockets during a run); B11, AC-019; `tools/` — done 2026-11-01: tools/import_check.py, tools/port_audit.py
- [x] T047 [US7] Execute V-BLK-IMPORT; B11, AC-019, V-BLK-IMPORT; `tests/core/test_import_boundary.py` — V-BLK-IMPORT PASS (2) [RUN-cg-20261101](evidence/RUN-cg-20261101.md)
- [x] T048 [US7] Execute V-CG-NEG for each group (source-change and timeout negative controls); B11, AC-018, V-CG-NEG; `.test_logs/simlab/<group>/<run>/` — V-CG-NEG PASS: core, executors, benchmark each exit 124 on timeout and exit 2 on a planted source change [RUN-cg-20261101](evidence/RUN-cg-20261101.md)

### Connected boundaries
- [x] T049 [US3] Execute V-X1.3 through the real service socket (≥5 planted defects in one experiment; paired clean controls on real MuJoCo); B03, B05, B09, AC-005; `tests/boundary/test_x13_findings.py` — V-X1.3 PASS: 6 planted defects returned together, no run created, paired clean controls completed [RUN-cg-20261101](evidence/RUN-cg-20261101.md)
- [x] T050 [P] [US2] Execute V-REQ (seven objective kinds; valid and invalid parent); B03, B09, AC-003; `tests/boundary/test_requests.py` — V-REQ PASS (8) [RUN-cg-20261101](evidence/RUN-cg-20261101.md)
- [x] T051 [P] [US2] Execute V-AUTHOR (every artifact category; idempotent bind; post-bind edit attempt; confinement and limits); B02, B06, B09, AC-004; `tests/boundary/test_authoring.py` — V-AUTHOR PASS (2; denials recorded as events) [RUN-cg-20261101](evidence/RUN-cg-20261101.md)
- [x] T052 [US5] Execute V-RUNNER (3-arm, 2-factor, 2-condition, 2-replicate, 2-episode design; each invalid reason; divergence; limits; cancel running and queued; double submission); B05, B06, B09, AC-006, AC-007, AC-008; `tests/boundary/test_runner.py` — V-RUNNER PASS (10) [RUN-cg-20261101](evidence/RUN-cg-20261101.md)
- [x] T053 [US5] Execute V-CHECKS (non-finite state; penetration bound; reruns; recomputation; unanchored run; planted failing required check; unexpected control-arm outcome); B07, B09, AC-009; `tests/boundary/test_checks.py` — V-CHECKS PASS (6) [RUN-cg-20261101](evidence/RUN-cg-20261101.md)
- [x] T054 [P] [US5] Execute V-DATA (every query key and combinations; fetched values; provenance completeness; BLOCKED arm without output); B04, B09, AC-013, AC-014; `tests/boundary/test_data.py` — V-DATA PASS (1) [RUN-cg-20261101](evidence/RUN-cg-20261101.md)
- [x] T055 [US6] Execute V-X1.5 (replay, save and restore, branch with a changed intervention, changed-seed control); B08, B09, AC-011, AC-012; `tests/boundary/test_x15_replay_branch.py` — V-X1.5 PASS (3: replay identical, changed-seed control differs, not replayable across builds, restore-continue bitwise equal, what-if branch) [RUN-cg-20261101](evidence/RUN-cg-20261101.md)
- [x] T056 [US2] Execute V-X1.4 part (a), tool parity across MCP stdio, Python client and CLI; B09, AC-015; `tests/boundary/test_tool_parity.py` — V-X1.4 (a) PASS (2: same 24 operations; equal normalized results and errors across MCP stdio, client, CLI) [RUN-cg-20261101](evidence/RUN-cg-20261101.md)
- [x] T057 [US2] Implement `tools/agent_only.py` (headless agent in an empty temp dir, MCP config with only SIMLAB, allowed tools `mcp__simlab__*`, transcript and tool log kept, independent store inspection afterwards) and execute V-X1.4 part (b) as an opt-in live run with the owner's authorization; B09, AC-015; `tools/agent_only.py`, `evidence/<run>.md` — V-X1.4 (b) PASS: headless agent with only the 24 SIMLAB MCP tools built, ran and inspected a two-arm experiment (41 SIMLAB calls, no other tool; $0.74) [RUN-x14b-20261101](evidence/RUN-x14b-20261101.md)
- [x] T058 [US7] Execute V-OPS (doctor healthy plus at least three degraded set-ups); B10, AC-016; `tests/boundary/test_doctor.py` — V-OPS PASS: healthy doctor in the check container plus 4 degraded set-ups (data dir in repo, credential variable, engine version mismatch, writable source); healthy runner doctor in evidence/ops/doctor-runner.json [RUN-cg-20261101](evidence/RUN-cg-20261101.md)
- [x] T059 [US7] Execute V-ALWAYS (port audit during a real run; executor network attempt; credential scan); B06, B11, AC-019; `tools/port_audit.py`, `tests/boundary/test_always.py` — V-ALWAYS PASS: host port audit during the final campaign (no SIMLAB listener; runner network none, no ports), executor network denied and credential-free worker environment [RUN-ops-20261101](evidence/RUN-ops-20261101.md), [RUN-cg-20261101](evidence/RUN-cg-20261101.md)

### Test benches and benchmark families
- [x] T060 [US4] Run V-TB-01 to V-TB-08 through the tools in the `campaign` profile; report each measured error; mark AC-010 PASS only after the owner confirms the TB-03 to TB-08 tolerances (plan U-03); B12, AC-010; `benchmarks/reports/<date>/` — V-TB-01 to V-TB-08 executed in the final campaign: every measured error within its frozen tolerance, negative controls caught; AC-010 stays BLOCKED until the owner confirms the [confirm] tolerances (U-03, U-04) [RUN-bench-20261101](evidence/RUN-bench-20261101.md)
- [x] T061 [US6] Run V-TB-09 and V-F5; B08, B12, AC-011, AC-020; `benchmarks/reports/<date>/` — V-TB-09 and V-F5 PASS (18 of 18 cells identical) [RUN-bench-20261101](evidence/RUN-bench-20261101.md)
- [x] T062 [US4] Run V-F1 (family campaign; hardware inventory; three repeats; per-family report); then record MuJoCo `admitted` in the registry from that evidence (T041); B12, B10, AC-020, AC-016; `benchmarks/reports/<date>/` — V-F1 PASS (90 of 90 cells, three repeats, inventory first, failed runs kept, per-family report, no aggregate score); `engine:mujoco` admitted for build d5339f6d… with the pending-confirmation note [RUN-bench-20261101](evidence/RUN-bench-20261101.md)
- [x] T063 [US4] Run V-OFFICIAL (references cited; manifests carry the engine version; speed and cost record on the pinned build); B12, AC-021; `benchmarks/reports/<date>/speed.json` — V-OFFICIAL PASS (references cited, engine version in manifests, speed record 14984 steps/s on the final build) [RUN-bench-20261101](evidence/RUN-bench-20261101.md)
- [x] T064 [US7] Execute V-X1.2: `tools/check_groups.py --group all` with every phase 1 test bench to its frozen specification; B11, B12, AC-018, AC-010, AC-011; `.test_logs/simlab/all/<run>/` — V-X1.2 groups executed: `all` 130 of 130 including the full F1 and F5 campaign in the group; the X1.2 claim waits only for the owner's tolerance confirmation [RUN-cg-20261101](evidence/RUN-cg-20261101.md)

### Fresh checkout
- [x] T065 [US8] Implement `tools/fresh_checkout.py` (clean clone at a commit; `docker build --no-cache` from `uv.lock`; rerun a recorded experiment; compare under its rule; record file access limited to the clone and declared inputs); B14, AC-017; `tools/fresh_checkout.py` — done 2026-11-01: tools/fresh_checkout.py, src/simlab/interface/portable.py
- [x] T066 [US8] Run a rehearsal from a clean export of the working tree and record it as a rehearsal (not PASS); B14, AC-017; `evidence/<run>.md` — rehearsal REHEARSAL_REPRODUCED from a clean export (bitwise equal, identical IDs); not PASS [RUN-x16-rehearsal-20261101](evidence/RUN-x16-rehearsal-20261101.md)
- [ ] T067 [US8] Ask the owner to commit; then execute V-X1.6 at that commit; B14, AC-017, V-X1.6; `evidence/<run>.md` — BLOCKED: no owner commit contains the SIMLAB code (owner: no commits); command ready in RUN-x16-rehearsal-20261101

### System contribution
- [x] T068 Hand the phase 1 check commands (V-X1.2 group `all`, V-ALWAYS, V-X1.5) to PAS-M1-SYSTEM for reruns on the integrated candidate; link from that TASK's tasks.md when it exists; SYSTEM/AC-003, AC-005 — phase 1 commands for PAS-M1-SYSTEM listed in reports/PAS-M1_Phase1_Completion_Report.md §System contribution (that TASK has no tasks.md yet; link it there when it is specified)

### Phase 1 exit
- [x] T069 Write `missions/PAS-M1/verification/<YYYYMMDD>/` (byte-exact copies of the phase 1 evidence index, failures beside passes); B15, AC-022; `missions/PAS-M1/verification/` — missions/PAS-M1/verification/20261101/ (75 files, failures beside passes)
- [x] T070 Write `missions/PAS-M1/reports/PAS-M1_Phase1_Completion_Report.md` with every section the test plan lists and a compute summary (totals, heaviest runs, peak memory against 6 GB WSL and 6 GB GPU); B15, AC-022; `missions/PAS-M1/reports/` — missions/PAS-M1/reports/PAS-M1_Phase1_Completion_Report.md (every section, compute summary last)
- [x] T071 Execute V-REPORT (document check of sections and evidence links); B15, AC-022, V-REPORT; `evidence/<run>.md` — V-REPORT PASS [RUN-report-20261101](evidence/RUN-report-20261101.md)
- [x] T072 Update TASKS.md §5 and `notes/state.md` exits table from the matrix below (derived, not copied); TASKS, notes — TASKS §5 and notes/state.md updated from this matrix

### Cross-cutting
- [x] T073 [P] Write the simulator's user and developer docs (install, doctor, tools, data directory, check groups); `docs/` — done 2026-11-01: docs/README.md
- [x] T074 Keep `notes/session-log.md` and `notes/state.md` current at session start, end and notable events; owner coding prompt; `missions/PAS-M1/notes/` — session-log.md and state.md kept through Session 2
- [x] T075 Record every run's resources in `compute-log.csv` via `simlab compute-log append` (feasibility, image builds, check groups, benchmarks, agent-only, fresh checkout); owner compute tracking; `missions/PAS-M1/compute-log.csv` — 224 rows in compute-log.csv (every run, check group, bench cell, build, X1.1 and rehearsal)

## Acceptance and Evidence Matrix
| AC ID / spec link | Block / IF references | Implementation work IDs | Required V IDs / verification work IDs | Current result | Current run evidence / candidate | Reuse or invalidation basis |
| --- | --- | --- | --- | --- | --- | --- |
| [AC-001](spec.md#measurable-outcomes) | B13 | T006 | V-X1.1 / T007 | FAIL | [RUN-x11-20261101](evidence/RUN-x11-20261101.md) run 2 | Open: needs an account entitled to gpt-6.1-sol (Q-09); A-13 decision stays with the owner |
| AC-002 | B01 / IF-001@r1 | T008, T009 | V-BLK-SCHEMA / T010 | PASS | [RUN-cg-20261101](evidence/RUN-cg-20261101.md) | Final build d5339f6d |
| AC-003 | B03, B09 | T016, T030 | V-BLK-VALID / T017; V-REQ / T050 | PASS | [RUN-cg-20261101](evidence/RUN-cg-20261101.md) | Final build |
| AC-004 | B02, B06 | T014, T015, T019 | V-AUTHOR / T051; V-BLK-SANDBOX / T021 | PASS | [RUN-cg-20261101](evidence/RUN-cg-20261101.md) | Final build |
| AC-005 | B03, B05, B09 | T016, T023, T030 | V-BLK-VALID / T017; V-X1.3 / T049 | PASS | [RUN-cg-20261101](evidence/RUN-cg-20261101.md) | Final build |
| AC-006 | B05, B06 | T018, T022 | V-BLK-STATUS / T024; V-RUNNER / T052 | PASS | [RUN-cg-20261101](evidence/RUN-cg-20261101.md) | Final build |
| AC-007 | B05, B06 | T020, T023 | V-BLK-STATUS / T024; V-RUNNER / T052 | PASS | [RUN-cg-20261101](evidence/RUN-cg-20261101.md) | Final build |
| AC-008 | B04, B05, B02 | T011, T015, T023 | V-BLK-STATUS / T024; V-BLK-STORE / T013; V-RUNNER / T052 | PASS | [RUN-cg-20261101](evidence/RUN-cg-20261101.md) | Final build |
| AC-009 | B03, B06, B07 | T016, T020, T025 | V-BLK-MEAS / T026; V-CHECKS / T053 | PASS | [RUN-cg-20261101](evidence/RUN-cg-20261101.md) | Final build |
| AC-010 | B12 | T035, T036, T038, T039, T040 | V-TB-01 to V-TB-08 / T060 | BLOCKED | [RUN-bench-20261101](evidence/RUN-bench-20261101.md) | Every TB within its frozen tolerance (final campaign and in-group); owner confirmation of [confirm] tolerances pending (U-03, U-04) |
| AC-011 | B08, B12 | T028, T037 | V-X1.5 / T055; V-TB-09, V-F5 / T061 | PASS | [RUN-cg-20261101](evidence/RUN-cg-20261101.md), [RUN-bench-20261101](evidence/RUN-bench-20261101.md) | Final build |
| AC-012 | B08 | T027 | V-BLK-STATE / T029; V-X1.5 / T055 | PASS | [RUN-cg-20261101](evidence/RUN-cg-20261101.md) | Final build |
| AC-013 | B04, B06, B09 | T011, T012, T018 | V-DATA / T054 | PASS | [RUN-cg-20261101](evidence/RUN-cg-20261101.md) | Final build |
| AC-014 | B04, B05 | T011, T012, T023 | V-BLK-STORE / T013; V-DATA / T054 | PASS | [RUN-cg-20261101](evidence/RUN-cg-20261101.md) | Final build |
| AC-015 | B09 | T030, T031, T032, T033, T057 | V-X1.4 (a) / T056; V-X1.4 (b) / T057 | PASS | [RUN-cg-20261101](evidence/RUN-cg-20261101.md), [RUN-x14b-20261101](evidence/RUN-x14b-20261101.md) | Part (b) on build df0cfd61; final build changed no interface code |
| AC-016 | B10 | T041, T042, T043 | V-BLK-REG / T044; V-OPS / T058; F1 evidence / T062 | PASS | [RUN-cg-20261101](evidence/RUN-cg-20261101.md), [RUN-ops-20261101](evidence/RUN-ops-20261101.md), [RUN-bench-20261101](evidence/RUN-bench-20261101.md) | Limitation: compute-log rows for Docker image builds record host-side wall time and VM memory, not BuildKit CPU (Convergence T077) |
| AC-017 | B00, B14 | T001, T002, T065 | V-X1.6 / T067 (rehearsal T066 is not PASS) | BLOCKED | [RUN-x16-rehearsal-20261101](evidence/RUN-x16-rehearsal-20261101.md) | Rehearsal reproduced (not PASS); needs an owner commit (U-02) |
| AC-018 | B11 | T045 | V-X1.2 / T064; V-CG-NEG / T048 | PASS | [RUN-cg-20261101](evidence/RUN-cg-20261101.md) | Groups, isolation, five evidence files, exit 2 and 124 controls; X1.2 itself also needs AC-010 |
| AC-019 | B00, B06, B11 | T002, T019, T046 | V-BLK-IMPORT / T047; V-BLK-SANDBOX / T021; V-ALWAYS / T059 | PASS | [RUN-cg-20261101](evidence/RUN-cg-20261101.md), [RUN-ops-20261101](evidence/RUN-ops-20261101.md) | Port audit with AI4R running is part of the X1.1 rerun (Convergence T076) |
| AC-020 | B12 | T034, T039, T040 | V-F1 / T062; V-F5 / T061 | PASS | [RUN-bench-20261101](evidence/RUN-bench-20261101.md), [RUN-cg-20261101](evidence/RUN-cg-20261101.md) | Release pas-m1-phase1-r1 |
| AC-021 | B12 | T038, T039 | V-OFFICIAL / T063 | PASS | [RUN-bench-20261101](evidence/RUN-bench-20261101.md) | Final build speed record |
| AC-022 | B15 | T069, T070 | V-REPORT / T071 | PASS | [RUN-report-20261101](evidence/RUN-report-20261101.md); reports/PAS-M1_Phase1_Completion_Report.md; verification/20261101/ | Document check over runtime evidence (T071); owner approval pending |

## Dependency Order and Execution Notes
- Order: T001 to T005 (B00) → T006, T007 (B13, X1.1 first; needs the owner for sign-in) → B01 → B04 → B02 → B03 → B06 → B05 → B07 → B08 → B09 → B12 → B10 → B11 → connected boundaries (T049 to T059) → benches and families (T060 to T064) → fresh checkout (T065 to T067) → phase 1 exit (T069 to T072). B11's runner (T045) can be built right after B00 and used from B01 onward.
- Parallel opportunities: T018 beside T014 to T017 once B01 exists; T031 to T033 after T030; T046 beside T045; T050, T051 and T054 once B09 exists; T073 at any time.
- Owner prerequisites: sign-in for T007 (U-01); authorization for the live agent run T057; tolerance confirmation for T060 (U-03); commit for T067 (U-02); [confirm] values (U-04).
- Memory: run check groups and benchmarks with the AI4R app stopped (research.md R12).
- Resumable next action: T001 (T004 done in Session 1).

## Current Verification Conclusion
- Candidate identity: final image `simlab-runner:dev` `sha256:daeb5923f7f0…`, build_id `d5339f6d04a9…`, check-group source manifest `a03824db2046…`; HEAD `d3054741d` plus the uncommitted SIMLAB tree (no commit by the agent).
- Required work complete: 73 of 75 original work items; open: T007 (X1.1 rerun with an entitled sign-in) and T067 (X1.6 after an owner commit); Convergence T076 and T077 open, T078 done.
- Required AC/check coverage: 22 of 22 ACs mapped; 18 PASS, 1 FAIL (AC-001), 3 BLOCKED (AC-010 owner tolerance confirmation, AC-017 owner commit; AC-001 is also blocked on the owner's entitled sign-in).
- Exits: X1.1 not passed (FAIL, model entitlement); X1.2 BLOCKED on tolerance confirmation (all benches within frozen tolerances); X1.3 PASS; X1.4 PASS; X1.5 PASS; X1.6 BLOCKED on an owner commit (rehearsal reproduced).
- Conclusion: NOT_READY (three owner actions remain; see the Phase 1 completion report).
- Remaining limitations and next work IDs: T007, T060 confirmation, T067; Convergence T076, T077.

VERIFIED requires all required work complete, all required checks PASS with valid evidence for the candidate and no invalidating dependency. System TASK completion does not by itself establish program completeness without TASKS source coverage.

## Evidence Invalidation
None yet. Rules for this TASK: a change to IF-001@r1, the MuJoCo pin, `uv.lock`, the Dockerfile, a frozen case or a [confirm] value marks the dependent matrix rows STALE and requires rerunning their V IDs; earlier run records are kept.

## Phase 1: Convergence (`$speckit-converge`, 2026-11-01)
Findings from re-reading spec.md, plan.md and this file against the code and the current evidence. Owner-dependent open items already listed above (T007, T060's confirmation, T067) are not repeated.

- [ ] T076 Run `tools/port_audit.py --expect-ai4r` during the X1.1 rerun so the audit shows AI4R alone on `127.0.0.1:5175` beside a running simulator, per AC-019 (partial: audits so far ran with AI4R stopped)
- [ ] T077 Measure Docker image builds' CPU time and peak memory (BuildKit runs in Docker's VM, so `tools/measure.py` records only host-side wall time and VM memory), or record in the compute-log notes why each field cannot be measured, per AC-016 and the owner's compute tracking (partial)
- [x] T078 Record in plan.md the additions the implementation made beyond the named blocks: the `development` bench profile (a pre-freeze pass that is never evidence), `simlab.interface.portable` (export and import for X1.6, B14), `tools/runner.py`, `tools/hostmon.py` and `tools/measure.py` (operator measurement), per plan: Project Structure (unrequested; justified) — done 2026-11-01 in plan.md "Implementation additions"
