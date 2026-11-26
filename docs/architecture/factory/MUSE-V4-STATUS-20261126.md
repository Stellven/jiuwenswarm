# Muse v4: JiuwenSwarm runs the factory graph — status, results and demo plan (2026-11-26)

Branch `demo/muse-q2-ttft-20261130`. Demo: Muse Spark Open 816B-A42B on the DGX Spark (GB10), Nov 30.
Live plan page (private artifact): "Muse Factory Demo Plan". Nothing is pushed; the owner pushes.

## 1. What our section is, and what the demo proves

Our contribution is the factory, from a plan to a built image. The demo shows AI4R JiuwenSwarm do every step:

1. Take a planned task graph whose node contracts are preliminary.
2. The scheduler agent (JiuwenSwarm + Codex gpt-6.2-sol) finalizes each node contract before the node runs: fills
   the open slots, binds the capsules (CCs), and may only make a contract stricter ("never weaker", enforced by
   host code).
3. The worker agent runs the bound CCs. Every output goes through the CC's checker (capsule verifier) and the node
   verifier (independent reviewer); the node closes only on a passing check (the gate).
4. The graph does a new quantization, the source changes the quantization needs, one more CC, then compiles and
   builds the image. That is the end of the task graph.
5. The image is tested once (the lab) against the baseline we already have.

The lab is not our contribution area. It never runs inside the graph ("ship to the lab once"). The demo is a
step-through: when a verifier rejects, we stop, look, and fix or ask for a specific fix; we do not redo the run.
Verifiers are new, so they stay loose for completion.

## 2. Owner directions (chronological, 2026-11-25 and 26)

- JiuwenSwarm does every CC node; reuse nothing built by hand. Keep the scheduler agent at the top. Fully resumable.
- Make a different 2-bit than Q2_K ("produces something of value"): chosen mixed IQ2_XXS gate/up + Q2_K down
  (target `iq2_xxs,down=q2_k`).
- Halt policy so a repair agent can fix things; step checkpoint at every node for the demo.
- Rehearse pipeline parts first. Trim the lab. Skip the shared sweep (big benchmarks are someone else's job).
- Use as much memory as possible for the target statistics.
- Speed things up; the lab can be anything; mix TTFT and decode in the same requests.
- The task graph is implementation only (code, new quantization, source changes, smoke tests, verification and
  review, compile and build the image). Measurement is shipped to the lab once.
- No more lab work or sweeps for a while: other people need the compute. Build code and run tests only.
- Stop the runs to replan (done 2026-11-26 ~10:35). Make a demo plan artifact (done).

## 3. Proven by hand (Nov 25 lab; hand-built engines; Q2_K pack)

One capped server load per arm (96 GiB cgroup), 32 generated tokens, warm = median of 2.

| Arm | Change | TTFT p512 warm | TTFT p2048 warm | Decode p2048 warm | Total p2048 warm |
|---|---|---|---|---|---|
| A | baseline: E0 (stock 9048bad8 + expert scale wiring) on NVFP4 | 201.6 s | 606.7 s | 0.326 tok/s | 996.8 s |
| B | A + Q2_K pack | 98.2 s | 294.3 s | 0.856 tok/s | 442.7 s |
| C | B + seeded expert cache (E1) | 99.3 s | 287.1 s | 0.849 tok/s | 436.7 s |
| D | C + prefill batch -b/-ub 2048 | 96.0 s | 114.3 s | 0.845 tok/s | 264.5 s |
| E | D + decode expert fill (E2) | 107.0 s | 118.4 s | 0.250 tok/s | 627.3 s (negative) |

A to D: 2048-token TTFT 5.3x faster, decode 2.6x, total 3.8x. The seeded cache adds little (cold p512 135 to 109 s).
The two big levers are the quantization (A to B) and the prefill batch (C to D).
Paired MMLU (Q2_K vs NVFP4): pass at 250 questions, loss +0.8 pts, interval [-2.9, +4.7], margin 5.
Sources on the Spark: `~/muse-demo/lab/report-abcde.json`, `~/muse-demo/acc/run.log` and `state.json`.

## 4. JiuwenSwarm runs

### 4.1 Rehearsal r1 (tiny random-weight pack) — accepted

`~/muse-demo/rehearsal-r1`, task `muse-2bit-rehearsal-r1`: build_engine, requant_tiny, trace_profile, accuracy_tiny
done, deliver held. 28 agent turns, 3.3 h (mostly repairs). Found 7 host bugs (job queue, user bus, offline UI build,
stale UI tree, token ids, verifier diagnostics, cross-capsule import).

### 4.2 The real v4 run (2026-11-26, task `muse-2bit-ttft-v4`, home `~/muse-demo/graph-v4`)

Stopped at ~10:35 for the replan. 49 agent turns. Step mode throughout.

| Node | CCs bound by the scheduler | Result | Checks |
|---|---|---|---|
| pin_inputs | factory.engine_inspector, weights.build_muse_nvfp4_reader | inputs pinned, disk and cap recorded | pass |
| ingest_nvfp4 | nvfp4 reader, source_workbench, capped_runner, integration_skill | converter extended; conversion 18 min; 528,942,164,428 B, 11 shards | converter fail (tiny fixture input missing) then pass; pack fail (reviewer: cite converter evidence) then pass |
| wire_expert_scales | weights.build_expert_scale_wiring, workbench, skill, capped_runner | scales applied; KLD 0.0013 (lim 0.005); slice 0.009 (lim 0.05); byte-identical to stock without scales | fail (optional manifest path wrong) then pass at runtime acceptance |
| build_base_engine | capped_runner, lab_manager | E0 built 4 min; cold NVFP4 smoke coherent | MEMORY_LOW halt on first load (host fix, excused); smoke fail (reviewer: show text) then pass |
| requant_2bit | weights.build_weight_pack_compiler, capped_runner | scheduler projected 269 GB from census; probe 134 s/layer; full 136 min; 267,217,595,041 B; 8-prompt smoke coherent | recipe and pack pass first try |
| record_profile | observability.build_runtime_event_recorder, analysis.expert_routing_profile, capped_runner | routing trace ranked into seeded profile | pass |
| measure_accuracy | eval.paired_accuracy, capped_runner | first run: context exceeded (agent fixed: -c 8192 -np 16); second cancelled for the replan at B 160 questions, acc 0.906 (A not started) | — |
| port_ttft_cache, build_candidate, size_prefill_batch, deliver_to_lab | — | not run | — |

Guardrails observed: never-weaker refused margin 5 to 8 (4 times, a deliberate operator test in the driver); the
scheduler refused to guess when its brief lacked the census and the per-question timing; the halt policy paused on
MEMORY_LOW and on repeated failures; the controller restarted many times without losing work; the repeat rule
refused an identical final after a reopen.

New 2-bit pack vs NVFP4 on E0 (60 GiB cache): load 164 s vs 318 s; host experts 214 GB vs 464 GB; cache covers
about 28% vs 13% of experts; compute buffer 1.5 GiB vs 8.4 GiB.

### 4.3 Agent code vs our manual code

- Scale wiring (`src/models/muse-spark.cpp`): identical to the manual change, plus two comments.
- Converter (`conversion/muse_spark.py`, `conversion/base.py`): 212 lines vs manual 41; same pack within 2 KB of
  metadata. The extra code is what the contract asked for (one-expert timing probe, lazy one-tensor writing).
- Quantization: new (never done by hand); 267.2 GB vs 304.7 GB for the manual Q2_K pack.
- Agent checkout: `~/muse-demo/graph-v4/agent-workspace/llama.cpp-muse` (commits 6eeca78bd converter, cd8937e4f
  scale wiring). Manual trees: `/tmp/wt-spike-llama` (E0, uncommitted), `/tmp/wt-e1` (E1).

## 5. Factory design added for v4

- `factory.capped_runner` (`jiuwenswarm/factory/capped_run.py`, capsule 1.4.0): recipes build, convert, quantize,
  serve, accuracy, manifest as durable jobq jobs; every model load under `systemd-run --user --scope
  MemoryMax=96G MemorySwapMax=0`, behind the machine gate (100 GiB available, no foreign GPU process; waits up to
  8 h) with a 6 GiB MEMORY_LOW watchdog. Host-only `capped_run` records.
- Placement: on the GB10, device memory is system memory and is not charged to the cgroup. Every server load gets
  `-fitt` so llama.cpp fit stays inside the device budget (total less 14 GiB, about 110,000 MiB) and `-lm mmap`
  by default.
- Digests: convert and quantize hash every output file and write `<stem>.manifest.json` (factory.pack-manifest/1)
  beside the pack; `manifest` hashes an existing pack (no model load, no gpu_launches).
- Serve rows carry token ids; failed requests carry the server's own error line; cancelled jobs stop their server.
- Halt policy (`halt_policy.py`): halts on 2 failed checks in a row, 2 failed runs of a recipe in a row, or an
  infrastructure failure; writes HALT.md; rerun acknowledges. Step mode (`FACTORY_STEP=1`): holds each node after
  finalization (STEP.md).
- Operator commands include `pause <task> <reason> [--cancel-jobs]`, `revise <task> <reason> [--dry-run] [--json]`
  and `resume <task> [reason] [--no-run]`. Pause stops the controller at its next check and leaves active jobs to
  finish by default. Revise applies the current task contract in one graph revision while the controller is stopped.
  Resume lifts the pause and runs the controller by default.
- While paused, use `note <task> <text>` to queue an instruction for the agent. Use
  `hold|release|reopen|retire <task> <node> <reason>` to manage individual nodes and
  `excuse <task> <attempt> <reason>` to keep a host failure from consuming node limits.
- Scheduler brief: carries the accepted checks of upstream nodes (bounded) and the run's operator inputs.
- Controller: a turn ending in RUNTIME_TIMEOUT or NEW_SESSION_REQUIRED starts a new agent session with context.
- Story (`jiuwenswarm-factory story --demo`): factory records rendered by what they say.
- Prefill batch sizing 1.2.0: `fill_moe_cache_headroom_mib` gives the rest of the device budget to the expert cache.

## 6. Current state (2026-11-26 ~10:40)

- Nothing runs: controller, job worker, servers all stopped; GPU idle.
- Contract `muse-2bit-ttft-v4` revision 7 committed (d82ec6c61) but not applied to the live run: graph ends at the
  image; measure_accuracy and size_prefill_batch moved to the lab; port_ttft_cache without the decode comparison;
  requant smoke without NVFP4 agreement. Live graph still has measure_accuracy (reopened then released, run
  cancelled) and port_ttft_cache (finalized with the decode criterion, released, not started).
- Fast lab tooling ready, not run: `scripts/factory/lab_v4_fast.py` (config JSON; one capped load per arm; cold and
  warm requests give TTFT and decode together).
- Full suite 1686 passed on the Spark (second clone `~/muse-demo/wt-v4b`). Live tree `~/muse-demo/wt-v4`.

## 7. Demo plan (proposed, revision 8)

Graph: pin_inputs, ingest_nvfp4, wire_expert_scales, build_base_engine, requant_2bit (done in the Nov 26 run), then
size_prefill_batch (the one other CC: largest measured gain, 2048 TTFT 287 to 114 s on top of quantization; about
20 min of GPU), build_image (compile, seal the source bundle with build receipt and pack manifests, assemble the
runtime image with `lab_build assemble`, incremental), and the gate. record_profile stays as recorded, off the demo
path. Then the small lab once: two arms on the image (2-bit; 2-bit + batch plan), cold and warm at 512 and 2048,
about 35 min; baseline arm A reused from Nov 25.

Verifiers loose: capsule verifier and host checks decide; reviewer blockers advisory. At each step checkpoint the
operator releases, notes a specific fix, or excuses a host fault.

Fixed UI, "factory demo board", local port 5175, replay (step through the recorded run) and live: task graph with
states; node contract preliminary vs final (filled slots, bound CCs, refusals); CCs in action (capsule calls, capped
runs with cap, time, size); checks (verifier checks, reviewer verdict, fail-to-pass); gate and delivery; operator
actions. Builds on the read-only monitor (`jiuwenswarm/factory/monitor.py`, APIs tasks, plan, story, telemetry, job).

Schedule: rev 8 + reviewer-advisory (1 h, no GPU); demo board (3-4 h, no GPU); remaining nodes in step mode
(about 1 h, 2 loads + build); small lab (35 min, 2 loads); dress rehearsal Nov 27-28. GPU total about 1.5 h, run only
when the owner frees compute.

Open decisions: (1) other CC: prefill batch sizing (recommended) or seeded TTFT cache port; (2) new-pack accuracy:
reuse the Q2_K result as indicative or run the paired check later (~1.5 h GPU); (3) replay the Nov 26 run (real,
with repairs) or a fresh short run on rev 8 reusing its packs (~2 h more).

## 8. Operator how-to (on the Spark)

```
cd ~/muse-demo/wt-v4
export TASK=muse-2bit-ttft-v4 FACTORY_HOME=$HOME/muse-demo/graph-v4 SESSION=muse   # all three are required
STEP=1 bash scripts/factory/run_muse_v4_graph.sh run        # job worker + controller in tmux
bash scripts/factory/run_muse_v4_graph.sh release NODE      # lift a step checkpoint
factory() { PYTHONPATH=$PWD ~/predemo-spark/jiuwenswarm/.venv/bin/python -m jiuwenswarm.factory.cli "$@"; }
factory status "$TASK" --json
PYTHONPATH=$PWD FACTORY_HOME=... python scripts/factory/graph_status.py $TASK     # one-screen status
python -m jiuwenswarm.factory.cli story $TASK --demo                               # the run as a story
```

Apply a contract revision while the run is paused. Wait for the controller to stop before running `revise`.

```bash
factory pause "$TASK" "apply the current contract"
factory revise "$TASK" "apply the current contract" --dry-run
factory revise "$TASK" "apply the current contract"
factory plan "$TASK"
factory resume "$TASK" "contract applied" --no-run
```

Omit `--no-run` to start the controller immediately, or use the step-mode driver above after lifting the pause.

Ship code to the Spark with git bundles (never tar the Windows tree); SHA256SUMS and reseals are computed on the
Spark (LF files). Reseal after editing a capsule: bump cc.yaml version, `scripts/factory/reseal_capsules.py <dir>`.

## 9. Rules kept

Every model load capped and behind the gate; device budget on unified memory; kill only our own processes; no
host names or accounts in shared material; label synthetic and rehearsal data; no Claude trailers in commits; the
owner pushes; no lab work or sweeps until the owner frees compute.
