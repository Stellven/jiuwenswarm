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
