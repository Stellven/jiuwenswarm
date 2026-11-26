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

## Runtime control (owner, 2026-11-26: fixable and pausable during the run)

- `pause <task> <reason>` / `resume <task>`: run-wide, checked at every controller iteration, while waiting on
  jobs, and before every agent or scheduler turn. Running capped jobs finish; resume reconciles them. PAUSE.md shows it.
- While paused (and while other nodes' jobs run): revise, note, hold, release, reopen, excuse, retire. Only changes to
  a running node itself are refused. A revise clears the final of a node whose prelim changed and that has not
  started, so the scheduler re-finalizes it. The controller uses the current contract revision after resume.
- The scheduler (astra) sees as much as we can show: the full task contract, all node contracts, upstream finals and
  evidence, run history, full capsule docs; it can read any capsule file or evidence record on demand.
- The demo board shows all of it: run state banner (running / waiting on a job / paused / halted / step), revisions
  on the timeline, briefings, the scheduler's brief and proposals, advisory vs blocking reviews; operator buttons only
  with `--operator` on 127.0.0.1.

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

## Fast lab for the completed Muse rev-8 demo

Use a new output directory and this configuration. Replace `/absolute` paths with the run, lab and rendered-prompt paths on the Spark. The prompts should be the rendered inputs used for batch verification. The default completion budget is 32 generated tokens.

```json
{
  "factory_run": {"home": "/absolute/graph-r8", "task_id": "muse-2bit-demo-r8"},
  "out_dir": "/absolute/lab-r8",
  "baseline_report": "/absolute/lab/report-abcde.json",
  "prompts": {
    "p512": "/absolute/prompts/512.rendered.txt",
    "p2048": "/absolute/prompts/2048.rendered.txt"
  }
}
```

```sh
python scripts/factory/lab_v4_fast.py --resolve CONFIG.json
python scripts/factory/lab_v4_fast.py --wait-quiet
python scripts/factory/lab_v4_fast.py CONFIG.json B P
python scripts/factory/lab_v4_fast.py --compare /absolute/lab-r8/report.json /absolute/lab/report-abcde.json
```

The resolve command reads Factory evidence and the baseline without launching Docker or loading a model. The B/P invocation requires the finished `deliver_to_lab` check, the succeeded `build_image` attempt with `verify_image: true`, the attached manifest from the succeeded 2-bit replay, and the passing `size_prefill_batch.batch_plan` check. The delivered package must identify that build attempt and attach its corresponding 2-bit manifest artifact. For the prefill check, pass the exact plan as a multiline JSON string to `verifier_inputs.plan` so the capsule receipt retains the document. A verifier input that names a file must point to the stored path of a Factory artifact cited by the batch plan check.

B uses the recorded image and pack with the verified plan’s cache request at the default batch. P uses the same image, pack and cache request with the verified batch and micro-batch arguments. The server log supplies the actual values for each row. The runner verifies the original manifest bytes and shard sizes before putting the image’s executable under the capped runner.

`report.json` includes the measured rows and the medians for TTFT, decode tokens per second, and request total for each arm, prompt and cache state. The comparison includes the November 25 A sample counts and actual generated token counts. When those counts differ, it displays the observed request totals without a total delta. Build, pack and prompt digests are unrecorded for A. The comparison command reproduces the accepted medians and exclusion reasons offline from the two reports.

Finish builds, test suites and helper jobs before the lab. `--quiet-status` samples readiness once and exits nonzero if blocked. `--wait-quiet` polls until ready and returns without starting the lab. Both show the raw host load and relevant process IDs. If a probe is unavailable, the readiness checks fail closed.

The Factory-mode lab checks the raw one-minute load is strictly below 1.0 and that no foreign build, test or helper process is visible before each model launch and timed request. It samples the host every two seconds and records each request’s start, periodic and end evidence, including all three load averages and the process IDs, states, categories and ownership markers. Recognized workloads and runnable or blocked processes appear in the snapshots. Process recognition uses native process metadata and common workload entry points, so finish all competing work before launching. The raw load includes this lab’s own processes.

The runner records startup load separately and waits on the same capped server for quiet before timing. It retains a timed cell that sees host interference or incomplete evidence with an explicit exclusion and keeps that cell out of medians and deltas. The in-flight request can finish, so a subsequent warm request can use the same cold predecessor after quiet returns. Completed cells are never repeated. After a restart, a pending warm cell whose cold predecessor ran on an earlier load is marked unavailable. The command reports exclusions with a nonzero exit status after the scheduled cells finish.
