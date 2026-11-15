# Spark attempt notes — 2026-11-13

These notes distinguish actual execution, retained historical results, static source findings, and proposed work. See [review and implementation gates](SPARK-LAB-REVIEW-2026-11-13.md).

Evidence root `ROOT=/home/user2/software-factory-spark-20261113`; repository `ROOT/sources/cc-dgx-spark`. Paths below are relative to ROOT unless stated otherwise. Large model files were not copied or fully rehashed during this review. No new model/GPU inference or native build was launched in the review tests.

## Attempt history and lessons

| Attempt | Outcome / evidence | Tool or capability needed; implication for CCs |
| --- | --- | --- |
| Isolated approved factory port | Branch `cc-dgx-spark`; original modified checkout preserved. Native Strata build 158.94 s; immutable runtime image packaged. `results/port-summary.json`, build receipts and `port-*` logs | Target-aware admission, host bridge, request hashing/replay, build identity; extend existing builder rather than create parallel build infrastructure |
| Initial container tests | Failures exposed noexec temp paths, host/container Python assumptions, Docker prefix leakage; fixed fixtures. Combined original suite 104 passed (`port-complete-tests.log`) | Container tests must exercise actual mount/runtime assumptions; fake-Docker tests do not establish GPU behavior |
| First Strata protocol attempt | Unknown `--model-dir`; retained failed smoke | Versioned engine inspector/adapter should discover and freeze supported argv before admission |
| Original model profile | Host guard stopped initialization before READY at 34.37 s; MemAvailable 7.72 GiB while cgroup ~10.17 GiB | Host memory telemetry and unified-memory guard required; cgroup memory alone undercounts this workload |
| Conservative Strata smoke | Context/prefill/placement reduced; full six experts; ~2.26 tokens/s and ~81 GiB available | A successful low-memory smoke is a functional control, not a useful performance baseline |
| llama.cpp / GPT-OSS control | GPU output `42`, CPU memory fact, repeated `42`; full GPT-OSS hash checked. Initial wrapper falsely required optional offload log; corrected to owned GPU-process sensor | Qualification must check actual engagement, not a version-dependent string. This smaller model is not evidence for oversized DeepSeek throughput |
| Direct oversized-engine screening | Seven cells, 17 requests, 1,782 generated tokens; all exit 0 and cleaned. `engine-investigation/summary.json`; per-cell `engine-result.json` | Existing generic lab path did not cover Strata; direct collector scripts enabled diagnosis but need consolidation behind lab adapter |
| Placement screening | Conservative 2.93/3.15/4.30, resident 7.81/8.32/13.87, larger resident allocation 8.93/8.32/10.02 tokens/s | More resident allocation did not monotonically improve speed; freeze memory/cache/workload before causal tests |
| Long prompt and cache | No active drafting 6.06/13.09; adaptive cache 6.44/12.67 tokens/s | First/repeat is a cache observation, not treatment/control; keep cache protocol explicit |
| Draft `auto` | 8.48/13.33 but drafter unloaded by heuristic | Parse effective engagement; a requested flag is not evidence the mechanism ran |
| Forced draft | Full six target experts, 1,471-token prompt, 128-token caps, 8.18/17.65 tokens/s; actual accepted draft counters | Working reference achieved. Retain effective config, correctness limitations and read counters; A/A then ABBA remain outstanding |

Direct engine tools are `engine-investigation/run_engine.py`, `prepare_run.py`, `make_long_prompt.py`, `analyze.py`, workload and per-cell configuration/protocol files. The tokenizer used the existing source and existing regex environment; trusted earlier IDs were crosschecked. Their location outside the repository is a packaging gap, not a reusable CC interface yet. The collector is borrowed source at `sources/collector/spark_comparison/docker_cell.py`; its identity and dependencies need to become admitted inputs.

## Independent recorded-result checks (new in this review)

Added repository tool `deploy/spark/check_engine_results.py`. It consumes retained files without launching a model or trusting the aggregate performance summary. It checks:

- Retained collector report and declared artifact digests; optional recomputation of small source/configuration input hashes.
- Created/final CID and image, 8-CPU/104-GiB/no-extra-swap boundary, read-only/network/mount policy, final exit/OOM/Running/PID facts.
- Configured and effective six-expert behavior and environment; absence of expert-skipping settings.
- Raw T/DONE protocol: token count, 128-token cap, prompt/generation timing, draft bounds, prefix reuse, canonical token-ID hashes, independently computed decode rates.
- Pipe sequence and byte coverage, valid JSONL samples/events, memory guard and OOM counters.

Ran against all seven `results/engine-*-128-001` cells with `--verify-inputs`. **Passed: seven cells, 17 requests, 1,782 tokens.** Output: `results/review-engine-evidence-checks.json`. This is functional evidence consistency, not a task accuracy test or scored A/B improvement. Integrity hashes are local evidence checks, not an external signature/trust root.

Added `tests/factory/test_recorded_engine_checks.py`: tiny synthetic two-token successful cell plus corrupt-rate, token-ID, failed-state, cleanup, missing-file, truncated-JSONL, swap-limit, wrong-expert-count, OOM and missing-DONE cases. **11 passed**, `results/review-check-tests.log`. These are synthetic verifier tests, separate from actual model execution.

Reproduction from repository:

```sh
python3 deploy/spark/check_engine_results.py --verify-inputs \
  /home/user2/software-factory-spark-20261113/results/engine-*-128-001
FACTORY_CLI_IMAGE=factory/cli-test:cc-dgx-spark \
  deploy/spark/factory-container.sh -m pytest -q -p no:cacheprovider -o addopts= \
  --tb=short \
  --basetemp=/home/user2/software-factory-spark-20261113/results/review-check-test-tmp \
  tests/factory/test_recorded_engine_checks.py
```

The glob covers the seven retained engine cells today; inspect it when adding future cells. This checker is deliberately specific to this recorded experiment's contract. Generalizing it requires a versioned adapter and schema, not silently loosening these boundaries.

## Live failure probes (new in this review)

Added `deploy/spark/review_crash_probe.py`, a CPU-only proof harness using the existing immutable engine image's Python and the existing collector. Normal/crash workloads have 256 MiB limits; the actual OOM probe allocates 256 MiB inside a 64 MiB container. No GPU, model, agent or build runs. Output is tiny. The probe writes/fsyncs an atomic intent before create and invokes recovery in a fresh process. All cleanup is restricted to the exact intent name and matching immutable image.

| Case | Actual result | Recovery |
| --- | --- | --- |
| Engine exit 23 | Collector records `command_failed`; container exit 23; quiescent | Exact stopped container removed |
| Container OOM | Actual `OOMKilled=true`, exit 137; collector records `oom_event` | Exact stopped container removed |
| Collector SIGKILL | Collector exit -9; partial stdout survives; engine container still running; no final report | Separate process inspects and removes exact container |
| SIGKILL + missing inspection receipt | Same live orphan; original created-inspect quarantined to simulate missing CID record | Finds exact durable intended name, validates image, saves recovered inspection, removes CID |

**Four passed**, `results/review-crash-probes-final/summary.json` and `review-crash-probes-final.log`. Initial probe artifacts are retained under `results/review-crash-probes`. The first harness version's final idempotency recheck overwrote its original recovery receipt; corrected to write a separate uniquely named recheck. The final four-case rerun retains both. The initially executed source is retained as `executed_probe.py` in the first probe directory.

Interpretation: existing collector handles ordinary exit and cgroup OOM, but cannot handle its own SIGKILL. Python `finally` cannot make that guarantee. Raw files survived process death through the OS, which does not prove fsync/power-loss durability. A separate guardian and continuously durable manifest are required. The harness demonstrates scoped recovery but is not wired into production factory quiet/restart behavior. It sets a process-local subreaper to collect its own orphan attach clients; no global host setting changes.

Untested: host reboot, power loss, Docker daemon crash, disk full, GPU faults, true abrupt hardware OOM, and factory service restoration. Do not infer these from process-only probes. Exact names are unguessable UUIDs here; production recovery should also record owner labels/nonce, boot identity and process start time.

## Existing CC execution (new in this review)

Added `deploy/spark/review_existing_ccs.py`, run in the minimal production factory image with read-only source and a read-only first GGUF shard. It uses a separate review store/task and CC runner store, not production task mutations.

- Prepared and materialized `methodology_ab.methodology`, `integration_skill` integrate/repair/preflight, and expert-streaming guide/method/ontology.
- Called existing native expert-streaming `applicability` with an explicit model path and the actual measured Strata argv. It failed `INVALID_INPUT`, `Invalid contract identifier`: dispatch loads the task's scored contract before accepting the explicit path. This identifies an actual pre-contract inspection gap; no contract was fabricated to bypass it.
- Called the Python helper directly for diagnosis. It reports `unknown`; it counts only ~39.07 GB expert data in the single mounted shard, and recognizes neither Strata's CPU placement nor `--mmap-experts on`. This is not a whole-model applicability assessment.
- Parsed actual Strata stderr with the existing llama engagement parser. All mechanism groups are `not_measured`. No missing measurement is treated as zero.
- First evidence-publish attempt used `review:...` IDs. Existing scope checks correctly rejected the host-reserved colon namespace (`SCOPE_DENIED`). Changed harness IDs to agent-legal `review-...` and new replay keys; retained failed attempt in the CC ledger.
- Existing evidence CC published both check summaries as artifacts, published `review-findings`, and queried it successfully. A new container then read the same observation successfully after the original process exited.

Results: `results/review-existing-ccs.json`, `results/review-cc-resume-read.json`; durable stores `review-store/` and `review-ccstore/`. These are ordinary review observations, not host-authoritative build/lab/evaluation receipts. The scope controls remain intact.

A standalone image probe (`results/review-standalone-factory-image.json`) confirms factory present, full server runtime absent, and no `nvcc`, `git` or `docker`. The original port containerizes CLI/CC/store paths under session direction. A complete autonomous factory container remains future work.

## Static source observations to preserve

- `lab_runner.py` and `ab_runner.py` still enforce Jetson labels; target-aware manager admission alone does not complete the Spark CC path.
- `expert_streaming.py` uses llama flags, GGUF single-file layout, fixed type names and a greater-than-2x-available heuristic. Its candidate ordering prioritizes missing/positive measurements; it is not a validated benefit predictor.
- Current Strata protocols contain timing in stdout. Raw stdout hash correctness cannot simply be applied to repeated runs; introduce explicit canonical token identity separately without changing existing contracts after seeing results.
- Collector calls `flush()` for raw samples/streams/events; its final report/hashes are produced in `finally`. It does not continuously fsync a recovery manifest.
- Store uses SQLite WAL/FULL and immutable evidence; telemetry has fsync, but telemetry delivery and SQLite commit are separate operations. Reconciliation must tolerate a committed record with missing notification.
- Queue uses PID/process-group lifecycle and fsyncs jobs; its runner reconciliation has no boot-ID check. Queue status cannot establish Docker cleanup after recorder death. Existing cleanup truthfully reports containers unverified where appropriate.
- The source already includes Strata streaming/store/ahead mechanisms. Instrument their demand-readiness/critical-path behavior before adding another expert filler.

## Environment and remaining discipline

The review introduced no global packages, driver changes, model downloads, shared cache eviction, shared Docker prune, commits or pushes. New proof containers are ephemeral and removed; the preexisting `ai4r-spark-ai4r-1` and BuildKit container are unrelated and were left running. Their potential benchmark interference must be measured or resolved with explicit ownership during future lab admission, not hidden by a claim that the whole machine was idle.

Host compiler use remains the approved port's exception. Proposed next image roles are native ARM64 builder, minimal engine runtime, ephemeral control/review, minimal recorder/sentinel, and transient profiler/validator. Only engine plus critical telemetry/lifecycle should run during a scored cell. Persist intent and evidence first, quiet owned heavy services, and restore review only after result sealing/recovery.

The primary reusable lessons are: verify effective engagement; retain null/failed attempts; distinguish process survival from durable evidence; separate raw integrity from semantic correctness; enforce experiment exclusion at the host; and establish A/A before attributing an improvement. These are the input episodes for future automatically built CCs.
