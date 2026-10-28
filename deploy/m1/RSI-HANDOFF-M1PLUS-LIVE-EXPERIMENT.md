# Handoff: run live RSI experiments on the M1plus integration

Prepared 2026-10-28. This handoff requests actual model-generated child experiments. It does not record a live experiment as already completed.

## Goal and current authority

Use the integrated backend to generate children, evaluate them, feed measured results back into the next proposal, and automatically retain the best qualifying child (or the original parent). Start with Calculate and Table Normalize, then run the other six supported deterministic capsules. Use the existing loop and benchmark machinery; fix a general pipeline defect if one blocks the run. UI work is deferred.

- Authoritative checkout: `D:/M1plus/jiuwenswarm` (WSL: `/mnt/d/M1plus/jiuwenswarm`).
- Branch: `rsi-loop-m1plus`.
- Verified implementation commit: `2f2f7ff50` (`feat(rsi): bind partner releases and retain evaluated children across capsule experiments`). The subsequent handoff-only commit should be a descendant of this commit.
- Partner base: `37194cc795ae89847327576c8a96a23091069adc`, captured from `origin/ai4r_M1plus`.
- Original source checkouts `D:/CLAUDE/jiuwenswarm` and `D:/Codex Development Runs/jiuwenswarm` were not modified. They are not the integrated execution source.
- No push, live deployment, service restart, live Core/journal changes, or live model experiment was performed during integration. Inspect the current installed runtime and active jobs; their state has not been established by this work.
- Follow the project instructions: one integrated AI4R version, general pipeline fixes, no UI changes, and 5175 as the only local application host port.

## What has and has not run

The catalog benchmark completed **8 tested, 2 explicitly skipped, 0 errors**: all **75 parent correctness cases** passed and **400 paired benchmark jobs** ran. This was a three-repetition, short-batch **A/A baseline**: identical parent code on both sides, **zero model calls**. It produced no generated children and no feedback-driven second round. All improvement claims are false.

Separate end-to-end tests exercised real workers, independent checkers, the Root/controller pipe, feedback iterations, and candidate selection using **scripted model responses**. These prove execution wiring, not a live model's ability to improve a capsule.

Use these terms precisely:

- A **benchmark repetition** repeats a timing measurement; it is not an RSI iteration.
- An **RSI iteration** diagnoses, proposes a child, evaluates it, records a decision, and produces feedback.
- A **session/run** contains several bounded RSI iterations. A rejected first child should feed the next iteration in the same session, subject to the loop's stop conditions.
- A **revision** is a fresh prepared run identity. Automatic preparation of a successor revision is not evidence that another experiment ran. Never replay a consumed revision to get a second proposal.

## Targets and baseline evidence

| Order | Capsule | Selected release | Parent cases |
|---|---|---|---:|
| 1 | `utility.calculate` | `calculate_v4`, m1-4 | 19/19 |
| 2 | `utility.table_normalize` | `table_normalize_v3`, m1-3 | 19/19 |
| 3 | `utility.calculate_typed` | m1-1 | 6/6 |
| 4 | `utility.table_normalize_typed` | m1-1 | 19/19 |
| 5 | `utility.markdown_report` | `markdown_report_v2`, m1-2 | 3/3 |
| 6 | `utility.markdown_report_typed` | m1-1 | 3/3 |
| 7 | `utility.packet_report` | m1-1 | 3/3 |
| 8 | `utility.summary_to_packet` | m1-1 | 3/3 |

Generalist requires its audited model bridge and frozen invocation context; Builder requires governed native execution and an independent task adapter. Their own capsule evaluations remain unsupported by the current generic runner. Do not count them as tested or replace their behavior with fake services. This is separate from using a live model as the RSI proposer for the eight deterministic targets.

Evidence:

- Windows report: `D:/M1plus/analysis-evidence/integration/catalog-benchmark-eight.json`.
- Full WSL captures: `/var/tmp/m1plus-eight-capsule-smoke-20261028/` (check persistence before use).
- Commands/protocol: `docs/rsi-loop/BENCHMARKS.md`.
- Integration history and verification details: `docs/rsi-loop/M1PLUS-ANALYSIS.md`.

Calculate's A/A median ratio was 1.0016; Normalize's was 0.9926. Summary-to-Packet showed an apparent 8.56% gain on identical code: use full protocol sizing for candidate decisions, not the three-repetition smoke configuration. Ratios from local concurrent smoke execution are not production performance claims.

## Live execution route

There is **no new turnkey live-generation CLI** in this integration. `capsule_benchmark_cli run --all` only measures parent A/A baselines. Do not rerun that command and report the requested live experiment as complete.

Read these source entrypoints before materializing the run:

1. `deploy/m1/rsi_capsule_slot.py`: durable template validation, `revision_loop`, exact execution budgets, grants, and fresh revision configuration derivation.
2. `deploy/m1/rsi_capsule_prepare.py`: fresh governed diagnosis/proposal contracts for every iteration, selected declaration validation before claim, and prepared session.
3. `deploy/m1/rsi_capsule_run.py`: `preflight`, `doctor`, and `run`; owns the Root evaluator/controller composition.
4. `deploy/m1/rsi_capsule_launcher.py`: `preflight` and `run`; stopped-worker evidence/publication path.
5. `jiuwenswarm/research_rsi/model_backends.py` and `host_codex_backend.py`: explicit provider configuration, once-only handles, and model-call evidence.
6. `jiuwenswarm/research_rsi/capsule_loop.py` and `capsule_session.py`: feedback, incumbent selection, stop conditions, and final retained result.

Use `deploy/m1/RSI-LOOP-WSL-RUNBOOK.md` as an operational reference, with these integration overrides:

- Its old branch/worktree paths, hashes, release versions, fixture/job counts, and assumed installed state are historical. Use this branch and derive current values from source/configuration.
- Its claim that the worker runtime need not be rebuilt does not apply to these selected partner releases. Capture/verify a compatible runtime **v2**, including the authoritative `target_bindings`, current declared carrier/checker/dependencies, and Python ABI. Do not reuse an original-Calculate runtime-v1 capture as a current-release experiment.
- Regenerate preparation from the full current selected declaration and exact parent bytes. A matching capability name alone is insufficient; selected version and declaration hash must match.
- Its frontend rebuild/UI sections are outside this task. Use the backend execution path and retained artifacts.
- Historical speedup percentages or a historical candidate that once fixed max ties do not establish improvement on Calculate m1-4. The current checker requires first-in-row tie spelling and different numeric bounds.

Inspect the existing host relay, isolated Core bindings, credentials, custody and runtime availability without exposing secrets. Prefer the existing `host-codex` backend when it is available: its source currently pins `gpt-6.1-sol`. Its closed configuration is `{"kind":"host-codex"}`; do not add a `model` field to that backend configuration. Each iteration needs a separate prepared diagnosis/proposal contract pair. Never substitute `FakeBackend` or the test-only `models=` injection for live generation. If the configured provider is unavailable, report the precise missing prerequisite rather than inventing model outputs or changing providers silently.

Use native Linux/WSL source and artifact directories for execution. Prior verification used Ubuntu-24.04, Python 3.12.3, and `/var/tmp/m1plus-analysis-8f4Uyp/venv/bin/python`; this is a test environment, not a verified production installation. Check that it still exists if using it for diagnostics. Parent directories must be traversable by the intended dropped identities; do not run protected jobs directly from a Windows-mounted checkout.

A reasonable initial durable-slot loop fragment is the existing bounded default:

```json
{
  "model_backend": {"kind": "host-codex"},
  "max_iterations": 5,
  "max_no_progress": 3,
  "trials": 3,
  "per_call_s": 120,
  "wall_s": 3600,
  "benchmark": {"repetitions": 11, "warmups": 2, "per_job_s": 6}
}
```

This is a **template fragment**, not a complete runnable configuration. Let the slot/preparation machinery derive the prepared contracts, runtime/grant pins, maximum executions, benchmark workload count, benchmark wall allowance, and full launcher deadline. The default model budget is at most ten diagnosis/proposal calls per five-iteration session (up to eighty across eight such sessions). Keep finite budgets and report early stops; do not silently extend or replay them. The per-job wall estimate must fit the actual execution profile and hardware. Keep each fixture specification's full batch sizes and acceptance gates; do not carry over `benchmark-smoke-config.json`.

Once valid fresh configurations have been derived, the verified module interfaces include:

```sh
# Run from the installed/captured source root and under the required owner.
# Paths/digests below must come from the newly derived configuration.
python -m deploy.m1.rsi_capsule_run preflight \
  --configuration "$RUN_CONFIG" --configuration-sha256 "$RUN_SHA"
python -m deploy.m1.rsi_capsule_run doctor \
  --configuration "$RUN_CONFIG" --configuration-sha256 "$RUN_SHA" \
  --scratch-root "$FRESH_DOCTOR_SCRATCH"
python -m deploy.m1.rsi_capsule_launcher preflight \
  --configuration "$LAUNCH_CONFIG" --configuration-sha256 "$LAUNCH_SHA"
python -m deploy.m1.rsi_capsule_launcher run \
  --configuration "$LAUNCH_CONFIG" --configuration-sha256 "$LAUNCH_SHA"
```

These are entrypoint shapes, not permission/ownership setup commands or a substitute for slot preparation. Honor the configured execution profile. If only local unprotected execution is available, retain that label and do not claim a protected run. Run targets sequentially for the first campaign so simultaneous measurement loads do not obscure the timing comparisons.

## Evidence and selection requirements

For each capsule, retain a unique run ID and fresh evidence directories. Preserve prior Screening, historical RSI publications, consumed claims, and existing journals/Core records. Do not reset them to make a run repeatable. A kept development child is not authority for production activation.

- Verify current parent correctness first. An invalid parent control must stop before proposal calls.
- Capture actual model identity, call evidence, prompts/responses, candidate bytes/hashes, and measured iteration feedback. The next proposal must consume the loop-generated feedback; do not manually write the candidate or feed hidden fixture inputs/outputs into the model.
- Preserve independent selected-release checking, exact passing-parent output bytes, malformed-input behavior, frozen dependencies and declared input port. Summary-to-Packet uses `summary`, not `packet`.
- The selected declared worker is the mutable carrier, even if it delegates. Delegated dependencies and checkers remain pinned. A candidate may inline a compatible implementation inside the authorized carrier; do not quietly edit its immutable dependencies.
- Measure the parent A/A baseline, then parent-versus-child paired benchmarks when correctness permits. Numeric timing gates and incumbent comparison must determine latency keeps. A/A is never a gain.
- Read final `result.selection` and `selection_ref` for the retained subject. Schema: `ai4r-rsi-capsule-selection:1`, with `role`, `body_ref`, `iteration`, `reason`. The legacy top-level `candidate_ref` can describe a rejected diagnostic attempt and must not be mistaken for the retained child.
- A run may honestly retain the parent. Do not loosen gates, invent a success, or discard later regressions to obtain a child.

Return a compact actual-results table: capsule/release, run ID, execution profile, real model calls, completed iterations, each child's correctness and benchmark decision, retained parent/child hash, measured gain and confidence interval when applicable, and stop reason. Link the original session, loop, selection and benchmark evidence. Explicitly separate completed runs, failures, and targets never started. If only the two priority capsules finish, report that coverage accurately and retain the remaining work.

## Verification already completed

Partner/core plus relay: 231 checks passed; capsule/CC scripts: 236 passed. Broad RSI checks found stale cancellation/transport fixtures and a dependency-depth defect; those were fixed and targeted reruns passed. Current-release preparation/session/input bindings, actual local summary dispatch/mutation refusal, and real paired Calculate candidate selection have been exercised. Source closure was complete: 1,133 modules, 71 resources. Exact counts and the scope of reruns are in `docs/rsi-loop/M1PLUS-ANALYSIS.md`; do not claim a single clean full-suite rerun where only focused final repairs were rerun.

Do not spend the next task repeating the completed A/A campaign or broad analysis. Prepare and perform the live bounded experiments, fixing concrete execution blockers if necessary, and report what the model actually produced and what the evaluator actually retained.
