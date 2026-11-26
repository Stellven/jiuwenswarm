# Muse v4: next phase runbook (from 2026-11-26)

Goal: by Nov 28, a demo of JiuwenSwarm taking the plan to a built engine image (contract rev 8), shown on a fixed
demo board, plus one small lab result on that image. Status and history: `MUSE-V4-STATUS-20261126.md`.

## Decisions (owner, 2026-11-26)

1. The other CC is prefill batch sizing (`engine.size_prefill_batch`).
2. Accuracy of the new 2-bit pack: the Q2_K paired MMLU result of Nov 25 is shown as indicative; no new test.
3. Continue the Nov 26 run (task `muse-2bit-ttft-v4`): apply rev 8 to it, finish the remaining nodes.
4. JiuwenSwarm does the work. The scheduler agent uses Codex `gpt-6.2-astra` (worker and reviewer stay on
   `gpt-6.2-sol`). The contract and plan must be clear enough that node contracts derive cleanly, and the scheduler
   must know the work and the CCs well.

## Contract rev 8 (`scripts/factory/make_muse_2bit_v4_rev8.py`)

Graph: pin_inputs, ingest_nvfp4, wire_expert_scales, build_base_engine, requant_2bit, record_profile (all done) ->
size_prefill_batch (E0 + 2-bit pack: plan from a default-batch load log, one capped load with the plan) ->
build_image (factory.builder Docker image of the owned checkout at cd8937e4f, `--version` check without a model,
run configuration for the lab) -> deliver_to_lab (the gate: ships image, run config, manifests, profile; lab task
for arms B and P). Removed: measure_accuracy (rev 7), port_ttft_cache, build_candidate.

Arms: A = Nov 25 baseline (E0 on NVFP4), cited not rerun; B = image on the 2-bit pack; P = B + batch plan.
Reviewer findings advisory on the new nodes (`review: "advisory"`); capsule verifier and host checks decide.
Each node still to finalize carries a `briefing` (summary, facts with sources, pitfalls, how to fill slots).

## Factory changes (in progress, parallel)

- Scheduler brief: task title/purpose/scope, the plan with states, neighbour objectives, capsule docs (SKILL.md,
  capability descriptions, verification units, earlier use in this run), `factory.scheduler.capsule` to read a
  capsule's files. Node contract field `briefing`. Scheduler model default `gpt-6.2-astra`.
- Operator `revise <task> <reason> [--dry-run]`: apply the contract's current revision to the live graph in one
  graph revision (cancel removed nodes, add new ones, rewire pending dependencies). Needed because `retire` alone
  would leave build_candidate with no dependencies.
- `review: "advisory"` (recorded and shown, does not block; advisory -> blocking allowed in a final, not reverse).
- Demo board (port 5175, replay + live) on `monitor.py`, reading a local snapshot of `~/muse-demo/graph-v4`.

## Steps

1. Merge the three branches, regenerate the contract, local tests; bundle to the Spark, full suite in
   `~/muse-demo/wt-v4b`.
2. Scheduler dry run (no GPU): copy `~/muse-demo/graph-v4` without `packs/` (link it) to a scratch home, `revise`
   there, run only the scheduler agent (astra) on size_prefill_batch, build_image, deliver_to_lab. Read each brief and
   final: slots filled from evidence, right CCs bound, no refusals that point at a contract gap. Fix the contract.
3. Live: update `~/muse-demo/wt-v4`, `revise --dry-run` then `revise` on the real run; record operator inputs for
   baseline A and the indicative accuracy; `STEP=1 run_muse_v4_graph.sh run`. GPU: size_prefill_batch about 2 loads
   (~10 min); build_image compiles (~5 min, no model).
4. Lab once: `scripts/factory/lab_v4_fast.py`, arms B and P from the image (container memory cap), cold + warm at
   512 and 2048 (~35 min).
5. Snapshot the finished run for the board's replay; dress rehearsal Nov 27-28.

## Risks

- build_image: the builder needs a `dependency` revision even for llama-server (briefing says: pass the owned
  checkout); first llama-server image through `factory.builder` on this run.
- Lab from the image: Docker is outside the capped runner's cgroup. `lab_v4_fast.py` arms take `image` (and
  `expect_sha256`): it copies `/opt/llamacpp` out of the image and runs it natively under the same systemd cap and
  `-fitt` budget, recording the image id and binary digest.
- Done nodes keep their recorded finals; rev 8 only edits their text (requirement ids, hands_to).
