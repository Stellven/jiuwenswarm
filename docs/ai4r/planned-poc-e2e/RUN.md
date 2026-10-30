# Planned POC end-to-end: run log

Branch `ai4r/planned-poc-e2e`, based on `beb8780e2`. Goal: one planned POC run (`plan_source: planned`, the Planner composes the pipeline) that reaches Delivery. Test baseline: [baseline.md](baseline.md).

Terms used here:
- **pl1 to pl10**: live run generations on this branch. A letter suffix (pl4a, pl4b, pl9b) marks a second failure or a rerun inside the same generation.
- **Carrier**: the host code around a capsule's model call. It builds the prompt and fills fields from bound inputs.
- **Reviewer / verifier binding**: the second model call that judges a stage output against its checks.
- **Pin**: a recorded hash of a capsule body, declaration or checking profile. Changing code under a pin means re-pinning. Muk approved the pin moves in the commits below.

## 1. Status

Run pl11b (app run `run:1953a2c076924e4fbee0ff199ff959eb`, 2026-10-30) completed every stage on the planned path: Intent compiler, Planner, Search, Screening, Hypothesis, Builder, Benchmark, Evaluation and Delivery. Every node gate advanced (Screening PASS, the rest PASS_WITH_KNOWN_LIMITATIONS). The trusted host scorer measured accuracy 0.5 for the majority-class baseline and 1.0 for the Builder's treatment over 3 repeats each, so Evaluation classified the result PASS under the pre-registered rule (treatment > baseline) and judged it plausible. The run made 35 model calls with no transient retry and no reply repair. Its residual risks note that identical fixed-seed repeats give no uncertainty estimate and that the payload reports no test sample count or confidence interval. The benchmark-runner sidecar then failed to collect the run (`collection_failure`, empty detail); that is outside the product path and is being diagnosed.

## 2. Error census

### Stored runs before this branch's fixes

A census of 24 stored runs found:
- Research content from the model never caused a failure.
- Failures were harness bugs, transient provider errors, and replies that broke rules the model was never told.

The fixes on this branch follow from that: tell the model the rule, let the carrier own the field, or fix the harness.

### Live runs on this branch

| Run | Furthest stage | Halt cause | Class | Fix commit |
|---|---|---|---|---|
| pl1 | Hypothesis | Verifier returned INCONCLUSIVE: `max_patch_files` is 1, but `poc_change_scope` names `poc_patch.py`, `run_benchmark.py` and `tests.py`. The field meaning (implementation files only) never reached the reviewer. | untold rule | `bd42204b1` (stage note), then `0f785b5ef` (field meanings for all reviewers; removes the note) |
| pl2 | Builder | `builder_agent_host._check` called `parse_predictions()` without the keyword-only `max_stdout_bytes` (added 10-21). The TypeError showed as an opaque executor fault. | harness bug | `b20a74e48` (cause now shown by `ed84ca879`) |
| pl3 | Screening (at dispatch) | `budget_exhausted` after 0.08 s. The Planner set Screening `time_s` to 120. The host reserves 2 x 60 s for two reviews, so no worker time was left. The Planner sees only `max_limits`. | untold rule (node limit too low) | `6c8f37d9a` |
| pl4a | not recorded in the sources read | A reviewer FAILed a non-blocking criterion and attached a `required_correction`. The verdict was advancing, so `verdict_follows_findings` halted the run. The prompt never said what "blocking" means. | untold rule | `938245634` |
| pl4b | Builder, after 7 calls | `provider_error` with no detail. Every node has one attempt, so one transient error ended the run. | transient | `3b39323de` (one retry); `ed84ca879` (records the provider code) |
| pl5 | Builder | First submitted Builder candidate. The `bounded_development` check required `call.contract_ref`, but model-call records are a closed schema with no `contract_ref`. No live submission could pass. | harness bug | `2805a9a22` |
| pl6 | Builder | 17 deterministic checks passed. The manifest reviewer FAILed `declared_output_conformance`: the host hard-coded `audience` as "authorized researcher". The enum allows only `researcher` or `reviewer`. | harness bug | `3f1de30cf` |
| pl7 | Builder | `contract_invalid` before any reviewer ran: 65 `trace_refs` against `maxItems` 64. | harness bug | `9e79a108b` |
| pl8 | Builder (start refused) | `ENVIRONMENT_BLOCKED`, no reason. A stale workspace lease from pl7's started-then-failed Builder was never released. | harness bug | `2b8c998b1` |
| pl9 | none | Docker engine crashed because drive C: was full. The cycle stopped at `build`. | environment | none (see section 5) |
| pl9b | Screening | `opportunity_statement` was 807 characters against `maxLength` 800. | reply over limit | `882bb7063` |
| pl10 | Evaluation (start refused) | Evaluation passed all 10 checks. Then the verifier binding was refused (`input_authority`): the host bound the optional `review_evidence` port as required. | harness bug | 680c56b3a |
| pl11 | Builder (stopped) | Stopped during its image build to add the verifier host_authority fix found by look-ahead. Not a halt. | n/a | `8fae99885` |
| pl11b | Delivery (completed) | All stages completed and every gate advanced. Collection by the sidecar failed afterwards. | sidecar | under diagnosis |

Final node status of the last two runs, from the cycle logs:
- pl9b: Intent compiler, Planner and Search completed. Screening failed. The other four nodes failed as dependents.
- pl10: Intent compiler, Search, Screening, Hypothesis, Planner, Builder and Benchmark completed. Evaluation failed. Delivery failed as a dependent of Evaluation.

## 3. Fixes by commit

Oldest first.

| Commit | What it does |
|---|---|
| `2aaf1e0da` | Makes the Planner the product plan source. Benches stay on static. Adds `examples/poc-planned` and the baseline. |
| `bd42204b1` | Hypothesis stage note stating the `max_patch_files` allowance (pl1). |
| `b20a74e48` | Builder smoke check passes `parse_predictions` its stdout bound. Adds an AST guard (pl2). |
| `6c8f37d9a` | Planner carrier sets each node's limits to the pinned capsule's declared `max_limits` (pl3). |
| `ed84ca879` | Halted runs name the real cause: a cause chain in the protected stop receipt and the raw provider code in the observation. |
| `3b39323de` | Retries a definitely failed transient model call once (stopgap, approved by Muk) (pl4b). |
| `0f785b5ef` | Reviewers see the output contract's field meanings (stopgap). Replaces the pl1 note. |
| `08a34f475` | `host_limits` counts the granted retry. The retry record names the failed call id. Found by auditing predicates against their record writers. |
| `2805a9a22` | Drops the impossible `contract_ref` predicate from the Builder check (pl5). |
| `938245634` | Reviewer reply normalization (a correction without a blocking finding is kept as a limitation; an outer markdown fence is stripped). The carrier fills the Evaluation fields that checks recompute (pl4a). |
| `3f1de30cf` | Builder manifest `audience` is `researcher` in all four producers (pl6). |
| `9e79a108b` | `trace_refs` capped at the schema's 64. Call and route refs stay; evidence refs fill the rest (pl7). |
| `2b8c998b1` | Started-then-failed attempts are terminal, so leases release. Refused starts record a cause and say why (pl8). Also fixes a bridge regression from `ed84ca879`. |
| `7bbc94297` | Look-ahead fixes for Evaluation and Delivery (section 4). |
| `882bb7063` | One re-ask when a carrier reply fails its own reply schema (pl9b). |

## 4. Look-ahead fixes

Found by reading ahead into stages before they failed live.

- **Evidence-aware reviewer lost its base reply format** (`7bbc94297`). `prepare_evidence_aware_release` replaced the reviewer's whole base instruction with the short evidence text. The reviewer was never told the findings, outcome names or JSON-only reply, so `assemble_assessment` would reject its reply. The evidence text is now appended to the base text.
- **Evaluation text made report-safe** (`7bbc94297`). Blockers, residual risks, followups and notes are single lines. The "Recommendation:" label stays for followups only. Delivery copies these into sections 6 to 8, where a trailing space, an embedded newline or a stray label would fail `carried_content`, `required_sections` or `recommendation_labeling`.
- **Refs filled by the carrier** (`7bbc94297`). `brief_ref`, `blueprint_ref` and `benchmark_ref` come from bound inputs, not from the model copying 64-hex strings.
- **Reply repair** (`882bb7063`). The runner checks a completed reply against the reply schema embedded by `capsules/_common.ask`. On a violation it asks once more with the previous reply and short findings (path, rule, bound; never the offending text). It shares the invocation's single retry allowance. A replay of 90 stored replies found it fires once, on the pl9b failure, and never on a stage that passed.

## 5. Known gaps not fixed here

- Pi route payload does not match the classification benchmark-payload contract.
- `blind_benchmark.py:63`: `invocation_id` is always `None`, so the optional join is skipped.
- Loop and text Builder modes are not covered by the agent-mode fixes.
- `executor.py:295,300`: missing binding kwarg (latent).
- DingTalk `Message(...)` is missing fields.
- The Evaluation plausibility notes rule is untold to the model.
- Delivery m1-6 has untraced numbers.
- Portable `capsule_runtime/semantic.py` halts on any non-PASS. This is the ccbench arm and is left as is.
- `value_semantic` frozen banks pin `gate.py`. They need a fresh bank. Old results stay valid.
- A verifier binding error after a successful work invocation is recorded as a refused start, because the verifier bind in `runner.py` is outside its try block. This misnames the cause. pl10 shows it as "start refused in evaluation".
- The hardware probe (`hardware.py`) refuses when GPU device nodes are visible or `/proc/cpuinfo` lacks a model name. This is likely on the DGX Spark.
- Card-risk trailing whitespace in Delivery section 7 is still compared raw.
- Drive C: was full (2.5 GB free) and Docker's disk needs an admin compact.

## 6. How to reproduce

Script: `outputs/planned-poc-20261029/cycle.sh`.

```
sh cycle.sh GEN PREV_IMAGE
SKIP_DEPLOY=1 sh cycle.sh GEN PREV_IMAGE
```

- `GEN` names the generation (for example `pl11`). It sets the image tag `ai4r:live-GEN`, the receipts folder and the run name.
- `PREV_IMAGE` is passed to `deploy_live.py build` as `--check-image`.
- The script runs: build (expects branch `ai4r/planned-poc-e2e`), override, initialize, select the model, grant, wait for readiness, prepare, run-cc, collect. It prints per-node status at the end.
- `SKIP_DEPLOY=1` skips build, override and initialize and resumes from model selection and grant.
- The model selection must be `codex`. The script selects it inside the container.
- Receipts are write-once. A crashed generation needs a new name. This is why pl9 was rerun as pl9b.
- The fixture is `deploy/m1/examples/poc-planned`. The plan source is `planned`.
