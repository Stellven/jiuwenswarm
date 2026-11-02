# Research: PAS-M1-001 - Base simulator
Supporting artifact for [plan.md](plan.md); subordinate to spec.md and TASK.md. Each decision records its source: **spec** (build input section), **repo** (team doc path) or **judgment**. Versions were checked on PyPI on 2026-10-30.

## R1. Engine and version
- **Decision:** MuJoCo 3.17.0 Python bindings (cp312, manylinux x86_64), pinned in `uv.lock`.
- **Rationale:** PRD SL-5.S (MuJoCo when the source simulator is not used) and the test plan adopt "MuJoCo state and batch API (`mj_getState`, 3.17 batch runs)". 3.17.0 (2026-10-22) is the release whose batch API the catalogue (section F) records as bit-identical to a plain loop. Source: spec.
- **Alternatives:** 3.16.x, rejected because the test plan names 3.17 batch runs. Floating version, rejected by ARCH Responsibilities ("Pinned versions").

## R2. Language, packaging and images
- **Decision:** Python 3.12, `uv` with a committed `labs/physicalai_sim/uv.lock`, one Dockerfile at `labs/physicalai_sim/docker/Dockerfile` (base `python:3.12-slim` pinned by digest; `uv sync --frozen`). Image `simlab-runner:<version>`; check groups run in the same image.
- **Rationale:** X1.6 requires rebuilding the images from the lockfile; the owner preflight allows Docker or a locked Python environment, and Docker 28.3.2 is available in WSL. The pattern matches `deploy/m1` (Docker plus `uv.lock`). Source: spec (X1.6, TP check groups) and repo (`deploy/m1/README.md`).
- **Alternatives:** A conda environment, rejected (no lockfile-based image rebuild). Reusing AI4R's `pyproject.toml`, rejected (ARCH: the lab is self-contained and imports no AI4R code).

## R3. Contracts and validation
- **Decision:** Pydantic 2.14 models are the single source of the IF-001@r1 records. JSON Schema is exported to `labs/physicalai_sim/src/simlab/schemas/`, and a check fails if the export drifts. Semantic validators run after schema validation, and all findings are collected into one list.
- **Rationale:** Pydantic reports every field error in one exception, which supports X1.3's "all findings at once". The exported JSON Schema lets the AI4R capsules (phase 2) validate without importing SIMLAB. Source: judgment, constrained by spec (FR-005, IF-001 machine-readable schema).
- **Alternatives:** Hand-written JSON Schema with `jsonschema`, rejected (two sources would drift). Dataclasses, rejected (no aggregated validation).

## R4. Store and traces
- **Decision:** SQLite (stdlib `sqlite3`, WAL mode) holds experiments, manifests, runs, trials, attempts, measurements, checks, checkpoints and provenance. Trace signals are NumPy `.npy` files per (run, trial, attempt, signal) with a sampled-time column. Everything lives under the declared data directory `SIMLAB_DATA_DIR` (default `~/simlab-data`, outside the repository), bind-mounted at `/data` in containers. Content-addressed blobs (`blobs/sha256/..`) hold manifest artifacts and checkpoints.
- **Rationale:** PRD SL-8.S requires a declared durable location and ARCH Placement requires run data outside the repository. NumPy already ships with MuJoCo, so no new heavy dependency. Memory-mapped `.npy` supports time-range queries without loading whole files on a 6 GB machine. Source: spec plus judgment.
- **Alternatives:** Parquet via pyarrow, rejected (about 40 MB more and not needed in phase 1). HDF5, rejected (an extra C dependency, and concurrent-writer issues ahead of phase 4).

## R5. Runner process model and tool transport
- **Decision:** `simlab serve` runs the runner service inside the `simlab-runner` container. It owns the store and runs each trial attempt in a worker subprocess. The API is JSON-RPC 2.0 over a Unix domain socket in the data volume. The Python client speaks that protocol; the CLI wraps the client; the MCP server (`mcp` 2.3.0, stdio transport) wraps the client. Host-side agents start the MCP server with `docker exec -i simlab-runner simlab mcp`. No TCP listener exists in phase 1.
- **Rationale:** PRD SL-9.D requires the same operations on all three tools; SL-9.B forbids a second host port. Unix-socket and stdio transports open no port at all. The private-network listener the AI4R capsules need is added in phase 2 (PAS-M1-002) on the lab's private network, never published on the host. Source: spec plus judgment.
- **Alternatives:** HTTP on a published port, rejected (a host port besides 5175). An in-process library only, rejected (no asynchronous status or cancel).

## R6. Confinement of executors and agent-authored code
- **Decision:** Phase 1 runs the `simlab-runner` container with `network_mode: none`, no secret environment variables and a read-only root filesystem except `/data` and `/tmp`. In addition, each executor worker installs a seccomp filter (libseccomp, `python3-seccomp`) that denies `socket()` for `AF_INET`/`AF_INET6` and sets `no_new_privs`, and applies rlimits (address space, CPU seconds, processes) from the declared limits before loading agent-authored component code.
- **Rationale:** ARCH Placement requires agent-authored code to be "always confined (no network, no credentials, declared limits)". The AI4R platform notes that packaging alone is not confinement and that enforcement must be real (`docs/architecture/design-package/platform/README.md`). Seccomp works unprivileged inside Docker. The per-worker filter keeps executors network-less even after PAS-M1-011 gives the runner a route to the model interface. Source: spec plus repo.
- **Alternatives:** `bwrap --unshare-net`, rejected (needs user namespaces that Docker's default seccomp profile blocks). Python-level socket patching, rejected (not enforcement).

## R7. Determinism, replay and checkpoints
- **Decision:** Replay re-executes from the recorded seeds and the recorded action and decision sequence on the same image digest, and compares SHA-256 digests of per-step state arrays (`time`, `qpos`, `qvel`, `act`, `qacc_warmstart`) plus measurements, bit for bit. A checkpoint stores `mj_getState(mjSTATE_INTEGRATION)`, the RNG `bit_generator.state`, the procedure's pending-event queue, the action history and the step index, all serialized with a SHA-256. Restore uses `mj_setState` into a fresh `MjData` built from the same compiled model.
- **Rationale:** The catalogue (section F) cites MuJoCo's determinism contract: equal `mjSTATE_INTEGRATION` state gives identical output, and warm-start data matters for bit-exact replay from a non-initial state. The test plan says exact replay is expected only on the same machine and build. Source: spec (TP Rules, TB-09) and the catalogue. The experimental `ipc` flag breaks exact replay, so validation forbids it.
- **Alternatives:** Comparing only final states, rejected (it can hide divergence that later cancels out).

## R8. Test-bench oracles
- **Decision:** Each F1 case's `oracle.py` uses the standard library only. TB-01 computes the elliptic integral K by the arithmetic-geometric mean (`math`). TB-06 compares against a reference trajectory computed by an independent fixed-step RK4 at a much smaller step in pure Python and frozen into `referee/`, with its own convergence test. Tolerances for TB-03 to TB-08 are proposed in `referee/criteria.json` with a written reason and marked `confirm: true` (spec Clarifications).
- **Rationale:** The Harbor authoring contract requires "a stdlib-only independent checker" (`benchmarks/harbor_suite/AUTHORING.md`); the test plan requires an independent oracle (B05) and frozen tolerances. Source: repo plus spec.
- **Alternatives:** A SciPy reference, rejected for the oracle (adds a dependency, and the reference must be independent of the code under test).

## R9. Agent-only use (X1.4)
- **Decision:** A headless Claude Code session (`claude -p`) in an empty temporary directory, with `--mcp-config` naming only the SIMLAB MCP server and `--allowedTools` restricted to `mcp__simlab__*`, so no shell, file or web tools. Its transcript and tool log are kept. The check then inspects the SIMLAB store independently. This is an opt-in live test; it is skipped, never mocked, in default check groups.
- **Rationale:** X1.4 needs "a coding agent with no other access". The agent is the subject and the check grades from the store, so the benchmark rule against self-grading is not violated. Source: spec plus judgment. A Codex session is an alternative once a Codex credential exists in WSL (none was present on 2026-10-30).

## R10. Local feasibility (X1.1)
- **Decision:** `labs/physicalai_sim/tools/feasibility.py` starts the unmodified AI4R app through its own operator (`deploy/m1/ai4r.py`, which publishes `127.0.0.1:5175` and uses a 4 GiB app envelope), waits for the owner's one-time model sign-in, makes one real request through AI4R's own control API so that AI4R's governed route makes the model call, and at the same time runs a simulator process (a MuJoCo pendulum loop in the `simlab-runner` image). It samples cgroup memory, CPU, `nvidia-smi` and disk throughout, and writes `feasibility.json`.
- **Rationale:** X1.1 and A-13. AI4R is consumed unmodified (ARCH "AI4R connection"). The repo shows the model route needs the owner to "complete the app's model authentication" (`deploy/m1/OPERATIONS.md`), and there is no Codex credential in WSL, so the sign-in is an owner prerequisite. Source: spec plus repo.
- **Open detail:** Which control-API action yields exactly one governed model call is chosen at implementation from AI4R's existing API (for example intake submission, `POST /api/v1/intakes`) and recorded in evidence. If the AI4R image does not build, or does not fit next to the simulator, the result is FAIL or BLOCKED with evidence and A-13 goes to the owner.

## R11. Resource records and compute log
- **Decision:** Each run, check-group run and benchmark run records `wall_s` (monotonic), `cpu_s` (cgroup `cpu.stat` usage, or `getrusage` of self plus children outside a container), `peak_ram_mb` (cgroup v2 `memory.peak`), `gpu` and `peak_vram_mb` (sampled `nvidia-smi` only when a GPU is used; otherwise `gpu: none` and VRAM `null`), and `disk_written_mb` (data-directory size delta plus `/proc/<pid>/io` `write_bytes`). `simlab compute-log append` writes one row per run to `missions/PAS-M1/compute-log.csv`.
- **Rationale:** PRD SL-10.D resource records; owner coding prompt "COMPUTE TRACKING". The WSL 6.6 kernel supports cgroup v2 `memory.peak`. Source: spec plus owner instruction.

## R12. Memory scheduling on the laptop
- **Decision:** Check groups (4 GB cap [confirm]) run with the AI4R app stopped. X1.1 runs AI4R (4 GiB envelope) together with a lightweight simulator process and records the actual peaks. Nothing in phase 1 runs AI4R and a full check group at the same time.
- **Rationale:** 4 GiB plus 4 GB exceeds the 6 GB WSL limit shared with Docker (`deploy/m1/OPERATIONS.md`; PRD Context hardware). Source: repo plus judgment.
