# DGX Spark factory port

**Recovery:** Strata now completes the bounded DeepSeek smoke with a conservative
profile. A llama.cpp / GPT-OSS 20B fallback also passes repeated GPU checks and
has a usable prompt command. See [RECOVERY.md](RECOVERY.md).

This is the `cc-dgx-spark` worktree, based on factory revision
`c7891472b399aecba42735df19b8c80451231355`. The original transferred snapshot and
modified `/home/user2/dev/jiuwenswarm` checkout are preserved. This Codex session
is the decision maker. No independent factory agent, authentication copy,
provider credentials, web service, commit or push is part of this port.

The factory CLI, evidence store API and native CC calls run in a small Python
container. Docker control and native compilation run on the host, through a
finite file bridge and the existing shared queue. The factory container has no
Docker socket. This is a trusted same-user execution channel; the writable
workspace and SQLite store are not a security boundary against hostile code.

## Operation

Run commands from this checkout. The paths below refer to the existing Spark
workspace; `FACTORY_SPARK_ROOT` can select another prepared workspace.

```sh
deploy/spark/build-factory.sh
# In a separate terminal, for at most three hours; no daemon is installed:
deploy/spark/start-bridge.sh
# In the first terminal:
deploy/spark/factory-container.sh -m jiuwenswarm.factory.cli status spark-deepseek-port --json
# Build submission is explicit and idempotent:
deploy/spark/factory-container.sh deploy/spark/submit-build.py
# Inference is also explicit; inspect the saved failure before authorizing a retry:
deploy/spark/factory-container.sh deploy/spark/submit-smoke.py
# Reconcile the queue and evidence before shutdown:
deploy/spark/factory-container.sh deploy/spark/finalize.py
touch /home/user2/software-factory-spark-20261113/port-ipc/STOP
```

The scripts require the prepared `notes/port-*` configuration and workload files,
existing model/pack directories, clean Strata and GGML sources, and the shared
queue worker. They do not download a model. The bridge serves only read-only Git
identity checks, image inspection, owned queue operations and host process-group
cleanup queries. Its inbox has an exclusive host lock; submissions bind the
persisted attempt argv, deadline, class and replayed environment. A request with
changed inputs needs a new idempotency key. Host jobs survive caller/container
exit and are reconciled by their persisted queue identity.

`submit-build.py` intentionally retains the original `deepseek-build-001` key.
Changes to the builder, recipe, environment or source require a new reviewed key;
they cannot silently replace this build. Later builder code additionally includes
compiler environment and recipe material in its cache key. The exact executed
builder whose hash is in the successful request is retained as
`results/port-executed-spark-engine.py`.

Spark requests pin both source repositories and worker/recipe hashes, select
ARM64 / CUDA 13 / SM121, and compile `strata-dsv41` with eight workers and a
90-minute deadline. Jetson retains its CUDA 12.6 / SM87 build path and historical
image-label compatibility. Spark admission requires the task, build receipt,
local immutable image ID, architecture and all hardware labels to agree.

## Initial port execution (retained history)

Workspace: `/home/user2/software-factory-spark-20261113`.
Task: `spark-deepseek-port`; store: `port-store/factory.sqlite`.

- Build attempt `f0bbabf3d74d46c3a2978dd5399016ac` succeeded in 158.94 seconds.
  Strata `ffa80d73133ea5c548aefe57889a16e8085a938f`, GGML
  `3cf03257f219afbe7334045ff7c6a06ac68c627d`; native CUDA 13, GCC 13,
  private CMake/Ninja, `STRATA_BUILD_DSV41=ON`, SM121 real and virtual code.
- Executable SHA-256:
  `ca7db6709d76e6b7e5518c381b97c6b9a7e645592132d08c8c82d1206ab2fcc1`.
- Runtime image:
  `sha256:1b6c3196f68f1c26d2aa873bf8cd9917362ffe7554fbb7e5aff2eee1f4864bbc`.
  It reuses the pinned ARM64 CUDA runtime base and packages the executable and
  linked CUDA libraries. The useful build objects remain under `cache/deepseek-*`.
- Both host-queued cancellation and timeout probes terminated their owned child,
  reaped it, removed their exact container, and reconciled host process groups.
  Records are in `port-store/probes/*/cleanup.json` and store observations.
- Native evidence CC execution succeeded in the factory container. Its receipt is
  in `port-ccstore/attempts/736bf831-06dc-499f-8636-bb9320362eec`.
- The first smoke setup attempt (`2ad83c655c134f25814a06729ebb2077`) failed on an
  unsupported argument before model loading. The corrected model smoke
  (`ba12e051ab9f47a68163e70deef40057`) passed the CUDA allocation, device memset,
  synchronization and device-to-host copy check, then stopped on the collector's
  memory guard after 34.37 seconds. It generated **zero tokens**, exited 137,
  was not reported OOM-killed, and was quiescent before its container was removed.
  **That initial run did not achieve inference output; the recovery above did.**

The corrected smoke requested the fixed garden prompt, at most 32 generated
tokens, 60 minutes, eight CPUs, 104 GiB memory and zero additional swap. It kept
the recorded launch/pack settings and added read-only profile handling. Pack and
model mounts were read-only. No guard was relaxed after failure; no cache was
flushed and no unrelated service was stopped. Full raw stdout, stderr, inspect
records, pipe events and memory samples are factory artifacts under
`port-store/runs/<attempt>/`.

## Unified-memory observations

Admission observed 116.96 GiB available and no unrelated GPU compute. At the
last sample before the guard, host available memory was 7.72 GiB, below the
8 GiB floor. Container cgroup current was only about 10.17 GiB, with no OOM
counter increments. Thus this workload's GPU allocations were not completely
represented by the container memory accounting: the 104 GiB container ceiling
alone did not bound physical unified-memory pressure. The host collector's
memory guard was necessary. These are observed accounting limits, not a claim
that the engine fits the limit or has completed inference.

Model sizes and nanosecond modification times matched existing pack provenance
before and after the smoke. Full model content hashes were not recomputed;
matching sizes and timestamps **do not establish full hash verification**.
Small pack metadata, tokenizer, profile, collector and workload files were
SHA-256 pinned. No performance or semantic-quality result is claimed.

## Dependencies and checks

No global package, driver or host-toolchain changes were made. The production
factory image reuses local base image
`sha256:754ba564cad9bfb5b8196c16721f14fb8b0ba201c272d81aef341cde2fd167c3`
and adds only `rfc8785==0.1.4`. Base validation libraries are inherited at their
pinned image versions. A separate validation image adds pinned pytest and its
three dependencies plus Git for source-history fixtures; it is not a runtime
dependency. Exact image identities and dependency inventories are recorded in
`results/port-summary.json` and related artifacts.

```sh
FACTORY_CLI_IMAGE=factory/cli-test:cc-dgx-spark \
  deploy/spark/factory-container.sh -m pytest -q -p no:cacheprovider -o addopts= \
  --basetemp=/home/user2/software-factory-spark-20261113/results/port-complete-tmp \
  tests/factory/test_builder.py tests/factory/test_controller.py \
  tests/factory/test_store.py tests/factory/test_jobs.py \
  tests/factory/test_lab.py tests/factory/test_spark.py
```

The final combined regression run passed **104 tests**. Initial container test
runs exposed test-environment assumptions (noexec temporary files, host versus
container Python paths, and an overridden Docker prefix); the fixtures now
isolate those settings and the complete run passed. Earlier failing logs remain
under `results/` and are not counted as passes.

Tests use private queues, executable temporary files inside the owned workspace,
and fake Docker/engine fixtures. They are distinct from the actual build,
lifecycle probes, GPU launch check and failed model smoke described above.
Incremental disk and cleanup evidence are recorded in `results/port-summary.json`;
only artifacts introduced by this port are eligible for cleanup. Shared Docker
data, host caches and unrelated processes are preserved.

## Oversized-model review and failure testing

The subsequent oversized-model investigation reached full-six-expert Strata
inference at 8.18 tokens/s on the first long request and 17.65 on its warm repeat.
These are exploratory working references, not an accepted A/B improvement.
The original failed smoke above remains part of the record.

See [lab review and next implementation gates](../../docs/architecture/factory/SPARK-LAB-REVIEW-2026-11-13.md)
and [attempt notes with evidence and commands](../../docs/architecture/factory/SPARK-ATTEMPT-NOTES-2026-11-13.md).
`check_engine_results.py` independently checks the seven retained engine cells;
`review_crash_probe.py` tests CPU-only lifecycle failures;
`review_existing_ccs.py` exercises existing materials/evidence and records adapter gaps.
These review harnesses use workspace-specific paths. They do not implement the
proposed production quiet lease, guardian, or automatic factory restoration.

## End-to-end agent path

The current implementation adds a real agent runtime, native ARM64 builder,
Strata contract/adapter, quiet lifecycle, durable recorder/guardian, and four
methodology CCs plus a lifecycle CC. Start with the
[end-to-end runbook](../../docs/architecture/factory/SPARK-E2E-RUNBOOK.md)
and [methodology cycle guide](../../docs/architecture/factory/SPARK-METHODOLOGY-CYCLES.md).
`prepare-mission.py` seals existing inputs; `run-mission.py` runs/resumes an
already approved task. New scoring contracts and automatic CC promotion remain
separate work.
