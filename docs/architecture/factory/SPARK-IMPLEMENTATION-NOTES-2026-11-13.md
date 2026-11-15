# Spark implementation and two real agent cycles — 2026-11-13

This implements the [review's next gates](SPARK-LAB-REVIEW-2026-11-13.md) and the approved reliable-experiment-loop plan. Use the [runbook](SPARK-E2E-RUNBOOK.md) and [methodology guide](SPARK-METHODOLOGY-CYCLES.md). The investigation continued into the Toronto evening; some retained UTC timestamps are November 14.

## What actually ran

A real JiuwenSwarm agent using the existing pinned Codex subscription transport inspected evidence, invoked methodology CCs, published decisions, submitted native builds and Strata lab jobs, reviewed results after fresh controller sessions, and wrote reports/proposed inputs. The decision maker was not a scripted facade. The host enforced admission, attempt caps, task scope, quiet barriers and recovery. Qualification required host/tool repairs, recorded below; this was not an unattended successful first attempt.

Workspace/evidence root: `/home/user2/software-factory-spark-20261113` (`ROOT`). Source remains the isolated `sources/cc-dgx-spark` worktree; original checkouts and prior results were preserved. No pushes, merges, model downloads, global package installs, driver changes or shared Docker pruning were performed.

### Mission 1: oversized Strata reference

Task `spark-strata-e2e-001` used 13 agent turns. It made two build attempts (one failed packaging qualification, one successful native rebuild), and five lab attempts (two failed qualification attempts, then three complete cells). Host repairs and explicit resumptions remained within the original 24-turn/four-hour mission allowance. The final agent decision is `report_inconclusive`, not accept or an optimization win.

The native ARM64 rebuild took **157.33 seconds**, used the pinned CUDA 13/GCC13/CMake4.4.3/Ninja toolchain image and unmodified Strata `ffa80d73133ea5c548aefe57889a16e8085a938f`, and produced image:

`sha256:c22e5406f9c81f5865a2318712c1f3247a86e2d1b1633a5ad19d1d3a09ffdfb4`

The executable SHA256 is `8c6afa35a145434a21d93f777050c2db78f606c8df3f2bceffc44930d1a48db2`. This build occurred inside a native ARM64 container with read-only source/dependency mounts, no network or GPU, eight CPUs, a 16 GiB memory/no-extra-swap ceiling, and sufficient temporary compiler space. Host Docker packaged the resulting executable/libraries; the build container had no Docker socket.

All six model assets now have full SHA256 values in `ROOT/assets/deepseek-full-identity-v1.json`: **256,811,098,112 bytes** in total. Earlier tensor inventory established 248,828,348,128 active text-tensor bytes against 130,661,142,528 OS physical-memory bytes. Model files were reused read-only. Intake hashing is outside timed execution and does not establish a cold-cache workload.

Every successful cell used all six experts, the same 1,471-token prompt, two 128-token-capped requests, explicit no drafting, disabled prefix reuse and static expert caching. Independent retained-evidence verification confirms 768 generated tokens, normal exit, cleanup, image/argv/mount/GPU boundaries, replay integrity and guard telemetry.

| Successful cell | First decode tokens/s | Repeat decode tokens/s | Within-process token equality |
| --- | ---: | ---: | --- |
| `d129efa8ac314ffa958a630e8a735c18` | 7.863 | 13.823 | Equal |
| `173dfd946f2f4e78a84162f860e22aa9` | 7.809 | 13.715 | Equal |
| `9f11709dc3384766852b7df84a46b28f` | 7.754 | 13.795 | Equal |

Median decode rates are **7.809 first / 13.795 repeat**. Minimum sampled host MemAvailable is **31.80 GiB**. Peak sampled cgroup memory is 31.69 GiB, which must not be read as total physical usage: CUDA unified allocations remain incompletely represented there. The 8 GiB host guard and 104 GiB/no-extra-swap container boundary were retained.

**Cross-process correctness is unresolved.** Cell 1 differs from cells 2/3 at zero-based generated-token index 16 (9271 versus 270), despite matching repeats within every process. There are two canonical output identities across the three starts. The host acceptance gate refuses to accept a deterministic reference in this state. We did not weaken correctness, assert semantic equivalence, diagnose a proven cause, or score a speed improvement. Fresh-start placement, numeric execution and initialization are candidate explanations, not findings.

These are engine-native decode rates; they exclude initialization and prefill. First/repeat differences are not an A/B treatment effect. Earlier forced-draft 8.18/17.65 tokens/s remains a separate exploratory working reference. No claim that the new container packaging sped up the model is made.

### Mission 2: a basic input chooses the next method

Task `spark-decoder-followup-001` received the literal objective **“Make the decoder faster.”** It had explicit read access to mission 1, four turns maximum, no build/lab attempt allowance and no GPU grant. It completed in one real agent turn, with zero builds and zero inference attempts.

The agent discovered the expanded CC library, read the three verified observations and prior report, used diagnosis/cache/ablation/follow-up methods, and selected **source-first repeatability diagnosis before tuning**. It cited the first divergence at token 16 and proposed inspecting sampler state/initialization, deterministic execution and asynchronous readiness before choosing one diagnostic variable. Any later cells are separately admitted, non-scoring A/A work. The agent did not blindly enable multiple components or claim a speed gain.

The native methodology tool's authored default is a repeatability candidate. The agent's useful additional judgment was to avoid merely rerunning the already-failed baseline: its final proposal first asks for source/observability evidence. This is an actual report-to-next-input test, not proof of an automatically learned optimizer or autonomous CC promotion.

## Implemented capabilities and interfaces

- Four new native methodology CCs: diagnosis across inference subsystems, out-of-core protocol design, bounded ablation design, and report-to-follow-up proposals. The catalogue also describes seven mechanism/observer candidates with source mappings, prerequisites, bounded changes and unknown benefit.
- A task-scoped lifecycle CC for status and terminal recovery. Active cancellation stays on the existing lab client. Cleanup authority remains host-owned.
- A `strata-v1` contract/adapter and generic lab-client route, with complete pack identity, exact fixed input, native phase parsing, canonical token identity and independent ingestion. Legacy A/B target checks use admitted profiles; the non-scoring Strata reference contract explicitly rejects scored `ab_submit`.
- Strata support in the existing expert-streaming CC: complete approved asset inspection, paired raw-log engagement parsing and native timing/full-six/draft facts. Readiness/inflight measurements remain unknown until actually instrumented; llama.cpp's greater-than-2x/CPU-flag heuristic is not applied to Strata.
- Native ARM64 builder and actual JiuwenSwarm runtime packaging from recorded local dependency/toolchain closures. CLI/validation remain separate images.
- A finite supervisor, per-attempt quiet receipts, shared build/CPU versus exclusive lab leases, independent compiler/recorder guardians, durable journals/manifests and replay-safe partial-result import.
- Task-specific successor mission state, preserving the original task's legacy receipts. Serial factory supervision prevents overlapping mission control. Deadlines, controller failure allowances and model-turn counters persist through restart.
- Durable operator inbox delivery across in-flight turns, explicit resumption of prerequisite-blocked tasks, read-granted cross-task methodology evidence, clearer text/structured-record errors, and contract-path/internal-ID resolution.
- Export preserves historical evaluation contract snapshots and current operator-input origins independently. A contract stored by explicit file path no longer requires a duplicate checked-in file named after its internal ID.

There are **13 top-level CC bundles**, with eight nested existing component bundles: **21 catalogue entries and 28 capabilities**. New component catalogue entries are candidates, not automatically applied patches.

## Failed attempts and tools they exposed

| Attempt / gap | Observed result | Repair and reusable lesson |
| --- | --- | --- |
| Full asset hashing compared whole `stat` objects | Reading a model changed atime and falsely reported mutation | Compare content-relevant size/mtime/ctime/inode/device; retain full hashes. Intake tool repaired; original failure log retained. |
| Source clone inherited Git alternates | Container could not resolve objects outside its mounts | Dissociate into owned Git objects; future clone preparation uses `--dissociate`. The tracked source commit/tree was unchanged. |
| Native compiler smoke was too small | Real eight-worker CUDA compile exhausted 256 MiB `/tmp`; build `77c546…` failed | Raised temporary space to 4 GiB within the existing 16 GiB cap. Future toolchain preflight should cover representative CUDA assembly, not only a tiny C++ binary. |
| File-path versus internal contract ID | Lab submit either rejected the approved path or tried a nonexistent repository contract file | Resolve both aliases to the operator-approved hash-pinned file. Host reconciliation confirmed no lab attempt existed before safe retry. |
| Empty Docker group prefix | Helper treated the joined command as one executable; lab `e05811…` failed before creating a model container | Preserve argv when no wrapper is requested; regression test added. No model data or result was fabricated. |
| New transport closed stdin after QUIT | Both requests in `8cc6e9…` emitted tokens, but shutdown showed an input-reader race and process-IO sampling failed | Preserve the original collector's open-pipe QUIT semantics. A CPU-only test verifies no injected EOF. Process-IO permission loss is explicitly unknown, never zero; the mandatory host guard remains active. That cell remains failed/partial. |
| Operator repair note arrived during a model turn | A stale controller checkpoint could overwrite the queued note | Append-only inbox, pending/delivered IDs and acknowledgment after the model turn. Regression reproduces concurrent arrival. |
| Batched lab submissions shared one barrier | Last attempt ID could overwrite the first queued cell's quiet receipt | Per-attempt receipts, archived at review restart; three-cell batch test added. |
| A second task reused single-task supervisor state | Diagnostic successor found another task's deadline | Task-specific state paths with legacy migration and serialized factory supervision; no budget renewal of the first task. |
| Initial whole-suite execution | Validation image lacked pytest-asyncio; old fixtures assumed 16 capsules, arbitrary target names or inherited host paths | Pinned pytest-asyncio 1.0.0 in validation only; refreshed compatibility fixtures and isolated source/environment assumptions. |
| Malformed build request while reporting failure | Missing target could raise again in `finally`, losing the failure receipt | Failure reporting tolerates missing identity fields and preserves an explicit failed record; dedicated regression added. |
| Export after successful Strata runs | Export tried loading internal contract ID from a nonexistent default file | Export historical snapshots by content identity; test covers explicit-path/operator-file contracts. Initial variable-shadowing error was corrected before qualification. |

The real agent made and repaired some invalid packet/plan calls itself. All failed CC receipts remain in the ledger. Generic JSON inputs still require better task-specific schemas and examples; the lab image input now declares its exact tag/id shape. Host interventions above are distinct from autonomous model decisions.

## Tests and retained evidence

All paths below are relative to ROOT:

- Full factory suite: **449 passed, 1 skipped**, `results/e2e-all-factory-qualified.log`. The skip is the historical llama.cpp patch-series test whose expected read-only fixture checkout was unavailable in that test image. It is not a skipped Strata run.
- The subsequent export alias/snapshot repair: **10 tests passed**, `results/e2e-export-tests-final.log`.
- Five actual CPU-only recorder probes: normal native protocol, exit 23, actual cgroup OOM/137, recorder SIGKILL, and SIGKILL with missing CID receipt. Guardian recovered and removed the owned orphan in both death cases. `results/e2e-lifecycle-live-final/summary.json`.
- Actual native-builder-container SIGKILL recovery and lab fencing: `results/e2e-native-guard-live/summary.json`.
- Exact owned supervisor SIGKILL/restart during qualification retained existing job identities; no duplicate build was created. Receipts: `results/e2e-supervisor-restart-probe.json`, `e2e-supervisor-restart-batching.json`, and original mission control recovery/exit receipts.
- Native QUIT transport proof: `results/e2e-quit-transport-proof/`. Engine fatal stderr and nonzero exit remain invalid; the fix does not turn the failed model cell into success.
- Independent current-cell verification: `results/e2e-strata-verified-summary.json`, produced by `deploy/spark/check-strata-mission.py`.
- Twelve native methodology replay calls against earlier reports: `results/methodology-native-proof.json`. Replay is separately labeled from both real-agent missions.
- Verified exports: `results/export-spark-strata-e2e-001` (**249 files**) and `results/export-spark-decoder-followup-001` (**94 files**). Large binary omissions remain explicit; review does not require keeping an agent alive.
- Readable agent reports/proposals: `results/spark-strata-e2e-001-final-reference-report.json`, `spark-strata-e2e-001-final-followup-proposal.json`, `spark-decoder-followup-001-report.json`, and `spark-decoder-followup-001-proposal.json`.

## Release images and space

The two real missions used dependency image `sha256:57d152e316cdb06e19b6d3c15e6b47c8175bdb71b559e9f8a4b9d166dc732cc7` plus a read-only development source bind. Their original role receipt and closure are preserved. After source qualification, a self-contained release image was built:

`factory/agent:cc-dgx-spark-final` — `sha256:fdeb040accabaddac83749bad037c3fec16ad1e04e6b9e48333f60a1fe364c87`

Its read-only, network-disabled smoke uses no source or authentication mount: actual JiuwenSwarm facade import, current factory modules, Codex CLI 0.163.0, and sealing every top-level CC pass. This is a final-image startup/sealing qualification, distinct from the earlier real-agent execution. Receipt: `results/final-role-images.json`; log: `results/agent-final-standalone-smoke.log`.

Builder image remains `sha256:d893d61a6f641fdeb6d20ce33870868d3ffd497746531a233d988427deff7f87`. No compiler or full app dependency set was added globally to Spark.

Current `docker system df -v` reports about 16.5 GB builder total / 9.50 GB unique, 9.17 GB final agent total / 99 MB unique across retained images, and 8.29 GB engine total / 1.29 GB unique. Agent dependencies are also shared with the retained earlier control image, so its 99 MB unique figure is not the entire agent overhead. Image-inspect API size values in role manifests use a different accounting basis; do not add them to Docker df figures. Shared build cache totals are not wholly attributable to this work.

Owned packaging contexts are approximately 1.48 GB (agent) and 5.89 GB (builder), and the mission store approximately 1.01 GB, by logical file sizes. Models were not duplicated. Detailed current accounting is in `results/e2e-storage-accounting.json`; this is not a before/after physical disk delta. Useful contexts, successful build cache, old working engine and provenance images were retained; shared data was not pruned.

## Remaining work

The next admitted experiment should diagnose fresh-process output divergence at fixed full-model obligations, using the second agent's source-first proposal. A deterministic or predeclared task-quality policy must precede scored optimization. Readiness/waste/inflight instrumentation and observer-overhead measurement are still needed before selecting a streaming change. Strata scored A/B is intentionally not implemented by silently adapting a non-scoring contract.

Automatic method/CC synthesis and promotion remain future work. The present methods are authored heuristics and candidate catalogues; the agent can exercise judgment, retain negative episodes and propose the next input. Admission, contract changes, grants and promotion remain separate decisions. Reboot/power-loss/disk-full/daemon-failure recovery and sustained/concurrent inference are not certified by these bounded tests.

At handoff, all owned engine/build/control/validation containers, guardians, supervisors and the session-owned bridge have exited. The two preexisting unrelated containers and shared queue worker were preserved. Results remain available in the store and verified exports.
