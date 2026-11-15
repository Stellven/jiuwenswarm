# Spark end-to-end factory

This is the implemented Spark path: a real JiuwenSwarm/Codex decision maker uses task-scoped CCs; a finite host supervisor runs admitted work while the control container is stopped. Strata uses a separate versioned adapter and repeatability contract. Existing llama.cpp/Jetson contracts remain available.

The agent now has diagnosis, out-of-core protocol, ablation and follow-up-input CCs in addition to expert streaming. Read [methodology cycles](SPARK-METHODOLOGY-CYCLES.md) for tool shapes, ontology, candidates and limits. These tools propose experiments; they do not authorize contract changes or automatically promote generated components.

## Prepare and launch

The current workspace is `/home/user2/software-factory-spark-20261113`; the source checkout is its `sources/cc-dgx-spark`. Commands below run there. They use the existing private factory environment; no global installation is required.

```sh
export PYTHONPATH="$PWD"
FACTORY_PYTHON=/home/user2/rsi-expert-streaming-001/factory-env/bin/python

# Offline packaging of the existing validated ARM64 runtime/toolchain.
# See deploy/spark/ROLE-IMAGES.md for arguments and receipts.
"$FACTORY_PYTHON" deploy/spark/build-role-images.py --help

# Hash all existing model assets once and prepare an isolated source checkout.
"$FACTORY_PYTHON" deploy/spark/prepare-mission.py

# Register the operator input separately; this launches no workload.
"$FACTORY_PYTHON" -m jiuwenswarm.factory.cli \
  --home /home/user2/software-factory-spark-20261113/mission-store init \
  /home/user2/software-factory-spark-20261113/mission-store/operator-task.json

# Run/resume that approved mission; reuse or own a finite bridge.
"$FACTORY_PYTHON" deploy/spark/run-mission.py
```

Do not rerun `init` against an existing task. Preparation refuses changed existing contracts/tasks. Use a new version/task when changing a workload or acceptance rule. The launcher accepts explicit root/home/task/role-receipt/auth/queue paths; defaults refer to this lab. It requires the existing shared queue worker and does not start a competing worker.

Role image identities are recorded in `results/mission-role-images.json`. The control runtime uses an immutable image for its dependency closure plus a read-only `/factory` source bind during development. Record that source manifest when exporting a run; image identity alone does not identify the bound framework code. Native builds have a pinned compiler image, clean source commit, pinned GGML revision, configuration/cache identity and executable/image receipts.

Authentication stays in one operator-owned file mounted read-only into the control profile. It is excluded from image build contexts and evidence. The launcher grants the approved task's effects or an explicitly selected subset, never a superset. The host bridge is trusted same-user infrastructure, not a hostile-code sandbox.

## Execution and recovery

The default mission is four hours / 24 agent turns, at most two build attempts and six lab attempts. Failed attempts consume these limits. The fixed workload requests all six experts, uses the 1,471-token prompt, two requests capped at 128 generated tokens each, explicit no drafting and static expert caching. Three successful fresh cells establish the intended repeatability campaign. It is not a scored optimization or task accuracy benchmark.

The control process publishes decisions and submits durable work, then yields. The supervisor observes the entire control container stopped, records a per-attempt quiet receipt and removes the container. Only then may a Strata worker start. Batched submissions receive separate barriers. The same supervisor restarts a fresh agent session for review after work completes.

Native builders acquire shared leases; lab recorders acquire an exclusive lease. The compiler and recorder pass their lease to independent guardians, preserving exclusion when their parent dies. Containers use exact ownership nonce/name/image/CID evidence; recovery never uses a global reaper.

The recorder captures raw stdin/stdout/stderr, phase records, monotonic events and host/cgroup/process-IO samples. It fsyncs periodically, records observed synchronization gaps and seals manifests atomically. Scheduler/IO delays can exceed the nominal one-second cadence. A dead recorder produces partial evidence, never a successful measurement. Host memory guards remain necessary because CUDA unified memory was incompletely represented by cgroup accounting.

The finite supervisor preserves its wall deadline and failure allowance across restart. It permits two automatic fresh-controller restarts after nonzero control exits; submitted jobs finish or reconcile before new review. An unknown submission is not resubmitted blindly. Reboot, power-loss, disk-full and Docker daemon failure recovery remain outside this qualification.

### Repairing a missing prerequisite

```sh
"$FACTORY_PYTHON" -m jiuwenswarm.factory.cli \
  --home /home/user2/software-factory-spark-20261113/mission-store note \
  spark-strata-e2e-001 'Operator repair completed; read the cited reconciliation evidence and resume the unchanged task.'
"$FACTORY_PYTHON" deploy/spark/run-mission.py
```

Publish concrete repair/reconciliation evidence before the note. Notes use a durable append-only inbox, so a concurrent controller checkpoint cannot overwrite them. Delivery is acknowledged after a successful model turn; an interrupted turn can receive the note again. Explicit operator notes can reopen `partial`, `report_inconclusive` or `stop_missing_prerequisite`; accepted/rejected tasks stay terminal. Contract, grants and budget remain unchanged.

A failed lab attempt needs a fresh attempt key after its outcome and cleanup are known. An uncertain acknowledgement requires reconciliation of the same key first. The experiment contract's file path and internal identifier both resolve to the same approved file; its content hash remains mandatory.

## Evidence and interpretation

Use existing `factory status`, `story`, `show` and `export` for task review. The store contains build/lab receipts, decisions, evaluations, raw artifacts and failures. Successful Strata ingestion independently checks actual image/boundary, exact GPU and argv, read-only mounts, tokenized input, raw event coverage, host guard/OOM samples and sealed asset identities before recomputing metrics.

The Strata contract distinguishes raw-stream integrity from canonical token IDs and finish reason. Timing-bearing stdout cannot be a byte-identical output golden. Missing or corrupt evidence invalidates a result; it never becomes a zero-valued metric. Repeatability diagnosis can compare fresh cells only when their explicit experiment identity matches.

Historical screening results, CPU-only failure probes, synthetic unit tests and new real-agent runs have distinct attribution. Earlier short-cell request metadata used cap64 while its retained wire used GEN128; those historical files are preserved and must not be silently imported as a new contract. The new fixed protocol binds its token cap directly.

Full model hashes are now retained in `assets/deepseek-full-identity-v1.json`; each cell checks stable file identity and pack/tokenizer hashes without rereading all weights. This is not a cold-cache campaign. Never globally evict host caches or stop unrelated services to improve a result.

## Implemented boundaries

- Local commits are permitted in the task-owned engine checkout. Builds reject another checkout or changed pinned dependencies. Push, merge, publication and automatic CC promotion remain unavailable.
- `strata-v1` is currently a non-scoring repeatability contract. `ab_submit` rejects it explicitly. A scored Strata comparison requires a separately approved contract and gate; legacy A/B contracts are not weakened.
- Methodology/component discovery is assisted by authored methods and source maps. Candidate benefits are unknown. The system is not an automatically learned optimizer.
- The control/runtime, builder and validation containers are transient. The host needs Docker/NVIDIA integration, the finite supervisor/bridge, the existing queue worker and durable storage. No driver changes or global package installation are included.

## Qualified run and successor inputs

The initial real mission completed three valid cells and returned an inconclusive
reference because outputs differ across fresh starts. A second real agent task
with objective “Make the decoder faster” selected repeatability diagnosis and
launched no builds or inference. See [implementation notes and results](SPARK-IMPLEMENTATION-NOTES-2026-11-13.md).

Successor tasks keep separate state under `FACTORY_HOME/missions/TASK`; original
legacy receipts remain under `FACTORY_HOME/mission`. Factory supervision stays
serialized across the workspace. `prepare-followup.py` prepares a diagnostic
input from an existing report; it does not admit or run it. Explicit prior-task
read grants preserve report provenance. New approved tasks can select the final
self-contained agent image with `--roles ROOT/results/final-role-images.json`.
