# Exploratory value campaigns

These opt-in host tools reuse the existing Harbor development suite. They do
not change its oracles, protected runtime, default job configuration or release
acceptance. Keep dataset, templates, private configuration and generated reports
outside Git. Use one shared dataset per campaign so unresolved launches cannot
be bypassed by scheduling another job.

Extract the case release and set `AI4R_BENCHMARK_CASES_DIR` as described in
[README.md](README.md). Freeze the workload/graph questions before execution:

```sh
python -m benchmarks.harbor_suite.value_campaign plan --output /new/campaign-plan.json
```

The default plans the 29 existing CC/verifier variants, one execution each.
`--case` and `--repeats` narrow or enlarge discovery without altering the authored
case definitions. Use the existing `prepare` module to create actual Harbor
bundles and the existing deployment/evaluation/comparison procedures to supply
real bindings. Planning is not runtime readiness or execution.

Launch an existing zero-retry, serial Harbor job once:

```sh
python -m benchmarks.harbor_suite.value_campaign launch --dataset /private/dataset --job-config /bundle/job.json --suite-config /private/suite-config.json
```

Run this in the qualified Linux/WSL Harbor controller. A durable claim precedes
dispatch. Failed, interrupted and timed-out controller launches retain an active
claim and must be reconciled using the original Harbor/application request.
There is no automatic recovery/resubmission. The controller does not replace the
existing native-provider unknown-outcome controls. A controller exit is not a
quality score or provider completion receipt.

Import one immutable job at a time using existing strict suite accounting:

```sh
python -m benchmarks.harbor_suite.value_campaign import-job --dataset /private/dataset --bundle /bundle --job-results /jobs/actual-job --revision exact-source-commit
python -m benchmarks.harbor_suite.value_campaign import-comparison --dataset /private/dataset --source /original/paired-comparison.json
```

Suite imports retain missing attempts, failed/unavailable grades, complete
checks/metrics and original JSON bytes. Exact duplicate imports are refused.
Summary-only comparison imports are retained without paired-gain credit. Supply
`--assignment`, `--baseline`, `--cc`, `--criteria`, `--variant`, and
`--quality-port` together to recompute using the existing shared comparator and
retain the inputs. This still does not authenticate private provider receipts.
A tool-free Codex comparison is not a full JiuwenSwarm comparison.

Job imports retain assessments, the task index, available bundle manifest/job
configuration and optional `--source-json` exports. This is explicitly an
assessment/index import, not a complete replayable export. Preserve the original
Harbor job and complete product evidence alongside it. Collect supported original
E1/E3 JSON records with the existing custody normalizer before telemetry adoption:

```sh
python -m benchmarks.harbor_suite.value_telemetry --dataset /private/dataset --bundle /bundle --evidence /original/evidence --task-key frozen-task-key
```

That path retains exact original JSON artifacts, deduplicated model/tool events,
all original record fields and token/cost coverage. Incomplete totals stay null;
partial observed sums are separate. Binary/non-JSON artifacts remain in the
original export. No raw auth or arbitrary directory scan is performed.

Datasets have immutable individual `records/`, content-addressed `artifacts/`
and durable `claims/`. No arbitrary directory or credential-store scan occurs.
Only explicit JSON benchmark exports may be retained as source artifacts.
Known credential fields/text are refused; this is not a general secret scanner.
The dataset remains host-only, not a public export. Retain exposed raw telemetry
and source records; unavailable measurements remain null with their reason.

Direct utility probes and report rendering are optional separate tools. Install
matplotlib in the controller for PNG charts, or use `--no-charts`:

```sh
python -m benchmarks.harbor_suite.value_probe --dataset /private/dataset
python -m benchmarks.harbor_suite.value_probe --typed --paired-with ORIGINAL_RECORD_ID --dataset /private/dataset
python -m benchmarks.harbor_suite.value_report --dataset /private/dataset --output /new/report
```

Direct probes execute actual workers and checks, recording inputs/outputs, source
hashes, each check result, wall/CPU durations and artifact sizes. They do not
invoke the semantic verifier or protected gate, and establish no live-agent
comparison. Every repeated probe remains a separate immutable observation.

Reports contain Part A project health and Part B CC/verifier value, full CSV/JSONL
tables, paired content deltas, selection filters and the dataset snapshot. Use
`--select-record` and `--select-case` for the presentation view; full tables retain
all rows. `--template` accepts an external UTF-8 template with `{{PART_A}}` and
`{{PART_B}}` placeholders. Without it, the renderer uses the meeting's two-part
structure. There is no separate required report template: use the existing
suite's documented fields and report accounting.

An opt-in additional case is registered as `cc03-typed-table`; see its
[case README](additional_cases/cc03-typed-table/README.md). Select it explicitly
with `--case cc03-typed-table --cases-root benchmarks/harbor_suite/additional_cases`.
The original ten-case defaults remain unchanged.

Known limits: live VF01/VF02 still require their documented actual schemas,
admissions, source observations and transport. Evidence-aware E2 remains
unavailable in the core path. Costs, semantic quality, downstream propagation
and full JiuwenSwarm lift remain unmeasured until their actual evidence exists.

## Native skills and bounded development campaigns

`value_cases freeze --output NEW_DIRECTORY` freezes 80 graph-first case designs,
public tasks, private criteria and a competent ordinary Python helper skill.
Sixteen cases have actual runnable utility workers; the remaining designs retain
their explicit product-binding prerequisite. `value_cases offline` runs the
ordinary helper and actual worker, not a native agent or protected CC unit.
Add `--public-source` for eight opt-in cases adapted from pinned CPython CSV and
decimal tests. Exact source links, upstream hashes, licensing and modifications
are in `value_cases/public_source/`; no upstream benchmark score is implied.

`native_value preflight --spec SPEC` checks the native runtime. `native_value run
--spec SPEC --output NEW_DIRECTORY` runs the real JiuwenSwarm facade in a fresh
process with ordinary tools and SkillManager. Use `variant=native-skills` with
explicit `skill_dirs`, or `native` for the ordinary bundled inventory without an
additional task skill. Both preserve bundled skills; bodies load through the
native `skill_tool`. Text-only configuration disables speculative image probes.
Agent mode has offline tool/skill-cycle qualification; team modes require their
own live qualification before any team claim.

Supply either an existing governed relay `binding`, or a private
`completion_directory` with explicit `model=gpt-6.1-sol` and
`reasoning_effort=medium`. The latter is serviced by `value_host`, which uses the
existing host Codex helper and validates original model/effort receipts. Never
mount credentials, private criteria, complete case banks or the whole checkout
in a measured native worker. A small runtime overlay plus public inputs/skills
is sufficient with the dependency-equipped app image. Preserve the actual image,
overlay, skill inventory, source hashes and every failed initialization attempt.

Initialize one shared `value_schedule` ledger with at most 256 calls and three
hours. Reserve whole pairs before dispatch; every actual completion must claim
its original request ID and reconcile against original evidence. Unknown
delivery blocks further dispatch. The host broker caps each invocation against
the remaining campaign wall time. Developer agents and offline checks run in
parallel; model dispatch and Harbor remain serial. Do not run concurrent tests
with a shared coverage database (`-o addopts=` avoids default coverage writes).

For existing app runs, `value_product` prepares the existing sequential runner's
uploads/intakes and exposes persisted request IDs without model dispatch. Reserve
the exact protected aggregate call ceiling with `Schedule.claim_envelope` before
using the existing `benchmark-runner resume`. Do not infer a ceiling from a case
name: the current integrated policy allows 80 calls; the separate document policy
allows 12. Unknown external runs retain their entire charge. Only validated
terminal exports, including linked runs if present, may release capacity through
`finish_envelope`. Report actual observed calls separately from charged bounds.
The existing sequential runner owns cancellation and same-request reconciliation.

`value_evaluation` emits effect-free commands for the existing evaluation-pilot
profile → real source execution → sources → scope lifecycle. It does not create
admissions or observations. E3 measures worker and deterministic checks; E2 is
the separate exact-output semantic replay. Paper-summary shortcuts cannot be
pilot sources under that profile. The usual per-output runtime review is another
distinct path. Never combine these into a fabricated end-to-end gate result.

Use `value_collect --dataset DATA --source OFFLINE_EXPORT` for original case-bank
exports, or add `--native-case CASE_ID --image ACTUAL_IMAGE_ID` for native saved
artifacts. Native terminal status is separate from independent content grading.
The report includes selected checker improvements, competent helper ties, real
native qualification, full missing-result denominators and all project-health
evidence even when experimental selections are narrow.

`value_core_complex --output FRESH_BANK` freezes four full Research Brief
production-contract tasks with original request/source files, public instructions
and schema, an ordinary native skill, and separately pinned private finite
oracles. The grader records unrecognized semantic paraphrases as manual review,
not a successful entailment claim. It separates useful completion, qualified
conflict, invalid promotion and false rejection. The production `check_brief`
diagnostic remains separate from the independent oracle.

These authored upstream Intent fixtures do not establish accepted predecessors,
admission or full-node execution. Their fixed IDs/Refs are valid only for the
specified Requirements component task. A whole-compiler comparison must use
real `IntentionCompiler.run` lineage and a separately frozen original-source
projection of actual run IDs/Refs. Existing single-CC E3 execution disables
semantic review and cannot alone establish worker-plus-checks-plus-review scope.
