# Derived records and the records folder

`Tier 3 · Part of: [Reference](README.md)`

This page defines what the app keeps for every CC execution, in what folder layout, and the three records built from it after a run: contract conformance, the capsule scorecard and the sample run export. The adopted integration rules are in [owner rulings](../side-systems/owner-rulings.md#data-foundation) and in [D37](../method/decisions.md#d37).

**Find:** [layout](#records-folder-layout) · [release rule](#release-rule) · [Capsule Run Record](#capsule-run-record) · [failure class rules](#failure-class-rules) · [contract-conformance](#contract-conformance) · [capsule-scorecard](#capsule-scorecard) · [sample-run-export](#sample-run-export) · [library analysis](#library-analysis)

## What this page adds to the platform

Three kinds of data exist for one execution.

1. **Raw evidence.** Inputs, outputs, prompt, full trace, worker workspace, and the raw output of every check and of the verifier. Capture hooks write it while the run happens.
2. **The Capsule Run Record.** One structured line per execution. It is the [invocation observation](field-catalog.md#invocation-observation), completed after the gate decision by the gate host. The gate host is hot-path platform code, so no record builder writes it. It points to the raw evidence and holds no large content.
3. **Derived records.** Conformance (declared against observed), scorecard (per CC version) and sample export (frozen copies). The record builders write only these, after the run, from the records and the raw evidence only.

Everything here observes. Nothing here changes how a CC, a check, the verifier or the gate behaves. Raw evidence is kept, so any derived record can be rebuilt in a new format. A rebuild writes a new record with a new ID and never rewrites a gate decision.

Keys. A record is keyed by `run_id`, `node_id`, `attempt_id` and `subnode_id`, with the observation `id` as the invocation ID. A framework agent ID is never a key ([D37](../method/decisions.md#d37)).

## Records folder layout

`records/` is the root on the persistent volume ([platform](../platform/README.md#data-foundation)). Every file is write-once, except `records.jsonl`, which is append-only. A `Ref` to a file in `records/` has the file's path relative to `records/` as its `id` and the SHA-256 of its exact bytes as its `sha256`. In a folder name, each `:` of an ID is written as `_`.

| Path under `records/` | Writer | When | Contents | Used as |
|---|---|---|---|---|
| `runs/<run_id>/run-start.json` | capture hook at run start | Once per run | Platform and library versions, hash of the active configuration, workflow script hash, shared workspace state, host facts (operating system, CPU model and core count, memory, GPU model and driver when present) | Source of the run bundle `pins` and `configuration_ref` |
| `runs/<run_id>/run-end/` | capture hook at run end, before team cleanup and trace retention remove the originals | Once per run | The workflow run log and the run's trace data | Listed in the run bundle `artifact_refs` |
| `runs/<run_id>/<node_id>/<attempt_id>/<subnode_id>/` | capture hooks around one CC call | One folder per invocation | The per-call files in the rows below | Targets of `trace_refs` and `artifact_refs` |
| `.../<subnode_id>/prompt.txt` | CC runner | Before the CC starts | The prompt exactly as sent. Absent, with a `missing_evidence` entry, for a CC that makes no model call | `trace_refs` |
| `.../<subnode_id>/capsule/` | CC runner | Before the CC starts | The declaration and every `identity.body` file, as they were at run time | `trace_refs` |
| `.../<subnode_id>/inputs/` | CC runner | Before the CC starts | Every input file, named by its `sha256` | Run bundle `artifact_refs` |
| `.../<subnode_id>/outputs/` | CC runner | When the CC returns | Every captured candidate output, named by its `sha256` | Run bundle `artifact_refs` |
| `.../<subnode_id>/trace/` | capture hooks | During the call | `model_calls.jsonl`, `tool_calls.jsonl` (every tool call in order, with name, status, duration and error) and `trace.jsonl` (the full trace, with no length limit) | `trace_refs` |
| `.../<subnode_id>/workspace/` | capture hook at the end of the call | Once | `workspace.tar`, a copy of the worker's workspace | `trace_refs`, and the source of the effects check in conformance |
| `.../<subnode_id>/gate/` | gate host hook | After the check bundle ran | `evidence.json` (the refs of the exact evidence the gate judged) and `checks/<check_id>.out` (the raw output of each check) | `trace_refs` and `check_result_refs` |
| `.../<subnode_id>/verifier/` | gate host hook | After the verifier CC returned | `output.txt`, the verifier's full output | `trace_refs` and `verifier_assessment_ref` |
| `.../<subnode_id>/human/` | gate host hook | Only when a person is asked | `question.json` and `answer.json`, including any edit the person made | `human_answer_ref` |
| `runs/<run_id>/<node_id>/<attempt_id>/node-gate/` | gate host hook | After the node gate decision | Raw evidence of the node gate decision | Run bundle `artifact_refs` |
| `records.jsonl` | gate host (hot path) | Right after the gate decision of the invocation is committed | One completed Capsule Run Record per line | Source of all derived records |
| `conformance/<observation_id>.json` | conformance builder | After the record is complete | One [contract-conformance](#contract-conformance) record | Scorecard, export |
| `bundles/<run_id>/manifest.json` | evidence builder (hot-path platform code, not a record builder) | At run end | The [run bundle](field-catalog.md#run-bundle), one per run | Inspection, benchmark runner, RSI workbench |
| `scorecards/<scorecard_id>.json` and `.md` | scorecard builder | On request or after a run | The [capsule-scorecard](#capsule-scorecard) and its table view | CC owners, RSI workbench |
| `exports/<export_id>/` | export builder | On request | The [sample-run-export](#sample-run-export) folder: `export.json`, `records.jsonl`, and copies of the call folders and bundle manifests | RSI workbench, platform benchmark runner |

The run bundle stays the run-level manifest. The per-call folders are what its `artifact_refs` and the observation `trace_refs` point to. The package identifies call folders by `node_id`, `attempt_id` and `subnode_id` instead ([D37](../method/decisions.md#d37)).

Raw evidence may hold sensitive text, so it is internal. Credentials are never captured. An export keeps protected evaluation data out, as the run bundle does.

## Release rule

Evidence the gate needs blocks release when it cannot be written. That is the platform's durable-commit rule ([commit before successor release](../pipeline/README.md#commit-before-successor-release)). It covers the candidate outputs, the check results, the verifier assessment, the exact evidence the gate judged, and the observation of each invocation.

Every other hook never blocks a run. If a trace copy, a workspace snapshot, the host facts, a human question copy or a derived-record file in the table above (conformance, scorecard or export) cannot be written, the hook logs the failure, the evidence builder names the item in `missing_evidence`, and the run continues. A derived record (conformance, scorecard, export) never blocks a run, and the gate, the scheduler and the binder never read one. The same holds for the appended completed line: the gate host logs a failed append and continues, and no gate input comes from it. A missing value is `unavailable` with a reason. It is never left out and never zero.

## Capsule Run Record

The Capsule Run Record is the [invocation observation](field-catalog.md#invocation-observation). The CC runner writes the observation when the invocation ends. The gate host reads that file. The gate needs it, so hot-path code writes it and no record builder is involved. After the gate decision of the invocation is committed, the gate host appends the completed record to `records.jsonl`. The completed record has the same `id` and the same values, plus the fields only the gate side knows: `failure_class`, `error_fingerprint`, `check_result_refs`, `verifier_assessment_ref`, `human_answer_ref`. The runner's file stays unchanged. A successful execution is recorded as completely as a failed one. An execution that never reached the gate is recorded too, with empty gate-side fields and the failure class its stop reason gives.

How each judgement was produced follows from the field that holds it: a check result is from a deterministic check, a verifier assessment is from a model, a human answer is from a person. The failure class is from the rules below and is never decided by a model.

### Failure class rules

The gate host applies these rules in order and stops at the first match. No model and no person decides the class in M1.

| Order | Condition | `failure_class` |
|---|---|---|
| 1 | `outcome` is `success` and the gate action for the output is `advance`, and the output is not a scientific negative | `none` |
| 2 | `outcome` is `interrupted`, or the gate verdict is `ENVIRONMENT_BLOCKED`, or the runner, the model bridge or the executor reported a platform error (provider error, authentication drop, executor start failure) | `infrastructure` |
| 3 | A mandatory check on an input port failed, or an input does not match its port schema | `input` |
| 4 | The CC is `research.evaluation` and the `classification` of its accepted evaluation verdict is not `PASS`. The verdict is a valid scientific result, not a defect | `scientific` |
| 5 | Anything else: a mandatory output check failed, the CC raised an error, or it ran out of its budget | `capsule` |

`error_fingerprint` is the SHA-256 of the error text after removing volatile details (timestamps, absolute paths, process IDs, run IDs, temporary names, memory addresses, and numbers longer than three digits), so the same error groups across runs. It is null when no error text exists.

## Derived contracts

All three are produced by protected record builders from `records.jsonl` and the raw evidence. A CC cannot write one. The invocation observation, the completed line and the run bundle manifest are not derived records. Hot-path platform code writes them, and the gate needs the observation and the manifest. The builders run off the hot path. A run works when they are absent or broken ([D37](../method/decisions.md#d37)).

### contract-conformance

Purpose: show, for one execution, what the CC declared beside what it did, so differences are visible without reading a trace. It sits on the Capsule Run Record, which is complete whether or not the CC declares anything useful. It never blocks a run and never changes a declaration.

`contract-conformance:field-contract:1` (version 1.0.0) · Producer: conformance builder. Consumers: capsule scorecard builder, sample run export, RSI workbench, CC owners.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this record. A rebuild gets a new ID. |
| `run_id` | `string` | yes | pattern `^[a-z0-9][a-z0-9_.:-]{0,63}$`, equals the record's `run_id` | Run of the execution. |
| `node_id` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,31}$`, equals the record's `node_id` | Node of the execution. |
| `attempt_id` | `string` | yes | pattern `^[a-z0-9][a-z0-9_.:-]{0,63}$`, equals the record's `attempt_id` | Node attempt of the execution. |
| `subnode_id` | `nullable-string` | yes | equals the record's `subnode_id` | Subnode that ran. |
| `observation_id` | `string` | yes | equals the `id` of one line of the records file | The Capsule Run Record this record compares. |
| `records_ref` | `Ref` | yes | the `records.jsonl` file that holds that line | Exact records file read. |
| `cc_name` | `string` | yes | pattern `^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$`, equals the record's `cc_name` | CC that ran. |
| `cc_version` | `string` | yes | pattern `^[a-z0-9][a-z0-9._-]{0,31}$`, equals the record's `cc_version` | Exact version that ran. |
| `declaration_ref` | `Ref` | yes | the declaration bound to the invocation | Exact declaration compared against. |
| `declaration_sha256` | `sha256` | yes | equals the digest of `declaration_ref` and the record's `declaration_sha256` | Join key with the record. |
| `built_at` | `string` | yes | UTC `YYYY-MM-DDTHH:MM:SSZ` | When the conformance builder wrote the record. UTC, whole seconds. |
| `items` | `ConformanceItem[]` | yes | at most 200. Covers the clauses in the table below | One entry per declared clause and per undeclared behavior. |
| `undeclared_count` | `integer` | yes | min 0, equals the number of items with status `undeclared` | Behavior with no declaration. |
| `unused_count` | `integer` | yes | min 0, equals the number of items with status `unused` | Declarations never used. |
| `coverage` | `nullable-number` | yes | min 0, max 1. Null when no observed behavior exists | Share of observed behavior that the declaration accounted for, as a fraction from 0 to 1 (formula in the invariants). Null means nothing was observed, and null is not 0. Reporting only: no gate reads it. |
| `evidence_refs` | `Ref[]` | yes | at most 64 | Tool-call logs, the workspace copy and the check results the builder read. |
| `unavailable_reasons` | `string[]` | yes | at most 50. Non-empty when an item is `unavailable` | Why an observation was not available. |

**ConformanceItem**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `clause_kind` | `string` | yes | enum `port`, `need`, `effect`, `check`, `failure_mode` | Which kind of declaration clause. |
| `clause_id` | `string` | yes | 1 to 200 characters, unique within `clause_kind`. The declaration path of the clause, for example `ports.outputs.intent`, `needs.network`, `needs.resources.original_request`, `changes.effects.model-disclosure`, `guarantees.checks.intent_schema`, `guarantees.failure_modes.<reason_code>`. For an undeclared behavior, the same form for the observed thing | Which clause. |
| `declared` | `nullable-string` | yes | 1 to 500 characters. Null exactly when `status` is `undeclared` | Short text of what the declaration says about this clause, for a reader. Null when the behavior was undeclared. The comparison result is in `status`, not in this text. |
| `observed` | `nullable-string` | yes | 1 to 500 characters. Null when `status` is `unused` or `unavailable` | Short text of what the run did for this clause, for a reader. Null when nothing was observed (`unused` or `unavailable`). The comparison result is in `status`, not in this text. |
| `status` | `string` | yes | enum `matched`, `mismatched`, `undeclared`, `unused`, `unavailable` | How the two compare. |

**Enum `status`**

| Value | Meaning |
|---|---|
| `matched` | Declared and observed agree: the output validates, the tool or resource was declared, the check passed |
| `mismatched` | Declared and observed differ: the output failed its schema, a declared check failed, or a failure used another reason code |
| `undeclared` | Observed with no declaration: a tool used but not declared, a file written outside the declared effects, a failure with no declared reason code |
| `unused` | Declared and never used: an unused tool or resource, an optional port with no file, a check that did not run, a failure mode that did not occur |
| `unavailable` | The observation source is missing, for example the sandbox log is off. It counts as neither matched nor unused |

**Clauses compared**

| `clause_kind` | Declared | Observed from |
|---|---|---|
| `port` | `ports.inputs[]` and `ports.outputs[]`: artifact type and schema | The actual input and output files, and whether they validated |
| `need` | `needs.network`, `needs.resources[]`, `needs.external[]`, `needs.injects[]` | The `effects` list and the tool-call log, and the network use in the sandbox log |
| `effect` | `changes.effects[]` | The files written, from the workspace copy and the tool-call log |
| `check` | `guarantees.checks[]` | The check results of the gate |
| `failure_mode` | `guarantees.failure_modes[]` reason codes | The `failure_reason_code` of the record |

**Invariants**

- `coverage` is the number of items with status `matched` or `mismatched`, divided by the number with status `matched`, `mismatched` or `undeclared`, rounded to six decimals.
- Every declared port name, check ID, failure mode reason code, effect ID, and the network clause and each resource key have an item.
- A tool-call log alone does not prove that no hidden file or network effect happened. When the workspace copy or sandbox log is missing, the related items are `unavailable`.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `conformance_counts_match_items` | `undeclared_count`, `unused_count` and `coverage` recompute from `items` | the record is not written |
| `conformance_clauses_complete` | Every declared port, check, failure mode, effect, network clause and resource key of the bound declaration has an item, and `declaration_sha256` equals the declaration digest | the record is not written |
| `conformance_matches_record` | The identity fields and the CC triple equal the Capsule Run Record line named by `observation_id` | the record is not written |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A host check fails | No conformance record. The run is not affected | The Capsule Run Record and the raw evidence |
| An observation source is missing | The item is `unavailable` with a reason | The record |



**Minimum quality bar.** A CC owner can see every difference between what the declaration promised and what the run did from this record and the declaration alone.

### capsule-scorecard

Purpose: summarize one CC version over a set of runs, so its owner can see how it performs and what it costs. It reports. It grants no release authority, ranks no CC and recommends nothing.

`capsule-scorecard:field-contract:1` (version 1.0.0) · Producer: scorecard builder. Consumers: CC owners, RSI workbench. It replaces the earlier `scorecard` placeholder.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Immutable ID of this scorecard. A rebuild gets a new ID. |
| `cc_name` | `string` | yes | pattern `^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$` | CC scored. |
| `cc_version` | `string` | yes | pattern `^[a-z0-9][a-z0-9._-]{0,31}$` | Exact version scored. |
| `declaration_sha256` | `sha256` | yes | equals the `declaration_sha256` of every record used | Exact declaration scored. |
| `built_at` | `string` | yes | UTC `YYYY-MM-DDTHH:MM:SSZ` | When the scorecard builder wrote the scorecard. UTC, whole seconds. |
| `records_ref` | `Ref` | yes | a `records.jsonl` file | Exact records file read. |
| `conformance_refs` | `Ref[]` | yes | at most 5000. Each is a conformance record of a scored execution | Conformance records behind `undeclared_behavior_count` and `mean_declaration_coverage`. Empty when none were built. |
| `record_ids` | `string[]` | yes | 1 to 5000 unique IDs, each the `id` of a line of the records file whose CC triple equals this scorecard's | Executions scored. |
| `run_ids` | `string[]` | yes | 1 to 500 unique run IDs, equal to the set of `run_id` of the scored records | Runs the executions come from. |
| `release_authority` | `string` | yes | enum `none` | The scorecard grants no release authority. A gate decision never reads it. |
| `execution_count` | `integer` | yes | min 1, equals the length of `record_ids` | Executions scored. |
| `class_counts` | `ClassCounts` | yes | the counts sum to `execution_count` | Executions by failure class. |
| `counted_count` | `integer` | yes | min 0, equals `execution_count` minus the `infrastructure` and `scientific` counts | Executions that count against the pass rate. |
| `gate_pass_rate` | `nullable-number` | yes | min 0, max 1. Equals the `none` count divided by `counted_count`, rounded to six decimals. Null when `counted_count` is 0 | Share of counted executions that the gate advanced, as a fraction from 0 to 1. Reporting only: a gate decision never reads it. Null means no counted execution, and null is not 0. |
| `verdict_counts` | `VerdictCounts` | yes | none | Gate verdicts of the executions that reached the gate. |
| `check_rates` | `CheckRate[]` | yes | at most 64, unique `check_id` | Pass rate of each declared check. |
| `failure_reasons` | `ReasonCount[]` | yes | at most 20, most frequent first | Most common declared failure reason codes. |
| `error_fingerprints` | `FingerprintCount[]` | yes | at most 20, most frequent first | Most common error fingerprints. Each is a SHA-256 hash of normalized error text, never the text itself. |
| `undeclared_behavior_count` | `integer` | yes | min 0, equals the sum of `undeclared_count` over `conformance_refs` | Items with status `undeclared` across the scored conformance records. |
| `mean_declaration_coverage` | `nullable-number` | yes | min 0, max 1. The mean of `coverage` over `conformance_refs`, rounded to six decimals. Null when no conformance record has a coverage | Mean `coverage` of the scored conformance records. |
| `next_node_acceptance_rate` | `nullable-number` | yes | min 0, max 1. Null when unavailable | Share of this CC's outputs, in the window, that a downstream node consumed and whose consuming node gate decision advanced, matched by file hash. A fraction from 0 to 1. Null when no downstream node consumed an output in the window. Null is not zero. Off the hot path: no gate reads it. |
| `median_duration_s` | `nullable-number` | yes | min 0. Null when no execution has a measured duration | Typical duration of one execution, in seconds. Null means no execution has a measured duration, and null is not 0. |
| `median_total_tokens` | `nullable-number` | yes | min 0. Null when no execution has token counts | Typical token use of one execution, as a count of input plus output tokens. Null means no execution has token counts, and null is not 0. |
| `median_attempts` | `nullable-number` | yes | min 1 | Median, over this CC's node executions in the window, of the attempt count per node execution (1 means first attempt). Null when the window has no execution. Off the hot path: no gate reads it. |
| `unavailable_reasons` | `string[]` | yes | at most 50 | Measures that could not be computed, and why. |

**ClassCounts**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `none` | `integer` | yes | min 0 | Executions with no failure. |
| `capsule` | `integer` | yes | min 0 | Failures of the CC. |
| `input` | `integer` | yes | min 0 | Failures caused by the input. |
| `infrastructure` | `integer` | yes | min 0 | Failures of the platform. Reported, not counted against the pass rate. |
| `scientific` | `integer` | yes | min 0 | Valid scientific negatives. Reported, not counted against the pass rate. |

**VerdictCounts**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `PASS` | `integer` | yes | min 0 | Gate verdict `PASS`. |
| `PASS_WITH_KNOWN_LIMITATIONS` | `integer` | yes | min 0 | Gate verdict `PASS_WITH_KNOWN_LIMITATIONS`. |
| `FAIL` | `integer` | yes | min 0 | Gate verdict `FAIL`. |
| `ENVIRONMENT_BLOCKED` | `integer` | yes | min 0 | Gate verdict `ENVIRONMENT_BLOCKED`. |
| `INCONCLUSIVE` | `integer` | yes | min 0 | Gate verdict `INCONCLUSIVE`. |

**CheckRate**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `check_id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$` | Declared check. |
| `executed` | `integer` | yes | min 0 | Times the check ran. |
| `passed` | `integer` | yes | min 0, at most `executed` | Times it passed. |
| `pass_rate` | `nullable-number` | yes | min 0, max 1. Null when `executed` is 0 | `passed` divided by `executed`. |

**ReasonCount**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `reason` | `string` | yes | 1 to 200 characters | Failure reason code. |
| `count` | `integer` | yes | min 1 | Executions with it. |

**FingerprintCount**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `error_fingerprint` | `sha256` | yes | none | SHA-256 of the error text after removing volatile details (see the fingerprint rule above). Groups the same error across runs. Not a secret and not reversible. |
| `count` | `integer` | yes | min 1 | Executions with it. |

**Invariants**

- Infrastructure and scientific failures are reported in `class_counts` and never lower `gate_pass_rate`.
- A scorecard compares no two versions. A comparison on matched inputs belongs to the RSI workbench referee and to the platform benchmark runner, which own the matching rules ([D37](../method/decisions.md#d37)).
- An unmeasured value is null with a reason in `unavailable_reasons`. It is never zero.
- The markdown table at `scorecards/<scorecard_id>.md` is a view of this record. It carries no data the record lacks.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `scorecard_counts_recompute` | `class_counts`, `counted_count`, `execution_count` and `gate_pass_rate` recompute from the named lines of the records file, and every named line has this scorecard's CC triple | the scorecard is not written |
| `scorecard_grants_no_authority` | `release_authority` is `none`, and the only files it refers to are its records file and its conformance records. It names no gate decision | the scorecard is not written |
| `scorecard_check_rates_valid` | Each `passed` is at most `executed`, and each `pass_rate` equals `passed` divided by `executed` | the scorecard is not written |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A host check fails | No scorecard. The run is not affected | The records |
| Fewer executions than needed for a measure | The measure is null with a reason | The scorecard |



**Minimum quality bar.** An owner can recompute every number from the named records file and the stated rules.

### sample-run-export

Purpose: frozen copies of real executions, so other tracks work against realistic data without touching a live run. The RSI workbench and the platform benchmark runner read it. They never write into it, and no path leads from an export back to a live run.

`sample-run-export:field-contract:1` (version 1.0.0) · Producer: export builder. Consumers: RSI workbench, platform benchmark runner, offline development of the verifier CC. This is the record export named in the [invocation observation](field-catalog.md#invocation-observation). It is separate from the [RSI evidence export](rsi-contracts.md#rsi-evidence-export), which the RSI custodian filters by audience.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version 1.0.0. Reject any other value. |
| `id` | `string` | yes | pattern `^[a-z][a-z0-9_.:-]{0,63}$`, equals the export folder name | Export ID. A changed export gets a new ID. |
| `built_at` | `string` | yes | UTC `YYYY-MM-DDTHH:MM:SSZ` | When the export builder wrote the export. UTC, whole seconds. |
| `records_ref` | `Ref` | yes | the `records.jsonl` inside the export folder | The exported records, one line per entry. |
| `bundle_refs` | `Ref[]` | yes | 1 to 500, one run bundle per run in `entries` | Run bundle manifests of the exported runs. |
| `entries` | `ExportEntry[]` | yes | 1 to 5000, unique `observation_id` | The exported executions. Failed executions are included. |
| `files` | `ExportFile[]` | yes | 1 to 100000, unique `path` | Every file in the export folder except `export.json`. |
| `content_sha256` | `sha256` | yes | see the rule below | One hash for the whole export, so everyone can confirm they use the same data. |
| `omitted` | `MissingEvidence[]` | yes | at most 100 | Executions or files left out, with the reason. |
| `redactions` | `string[]` | yes | at most 100 | What this audience does not see, and why. Names the kind of withheld content, never the content. Protected evaluation data is always listed here when present. |

`content_sha256` is the SHA-256 of a UTF-8 text with one line per entry of `files`, sorted by `path` in byte order: the path, a tab, the file `sha256`, and a line feed.

**ExportEntry**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `observation_id` | `string` | yes | the `id` of one line of the exported records file | The Capsule Run Record exported. |
| `run_id` | `string` | yes | pattern `^[a-z0-9][a-z0-9_.:-]{0,63}$` | Run of the execution. |
| `node_id` | `string` | yes | pattern `^[a-z][a-z0-9_]{0,31}$` | Node of the execution. |
| `attempt_id` | `string` | yes | pattern `^[a-z0-9][a-z0-9_.:-]{0,63}$` | Attempt of the execution. |
| `subnode_id` | `nullable-string` | yes | none | Subnode of the execution, copied from the record. Null when the execution has no subnode. The label rule writes null as `-`. |
| `failure_class` | `string` | yes | enum `capsule`, `input`, `infrastructure`, `scientific`, `none` | Copied from the record by the builder, so a consumer can filter without opening it. It is not decided again here. |
| `call_folder` | `string` | yes | a relative path inside the export folder, ending in `/`, a prefix of at least one `files` path | Copy of the per-call folder. |
| `label` | `string` | yes | enum `development`, `held_out`. Fixed by the rule below | Whether a consumer may use the execution for development or must set it aside (`held_out`). The builder sets it by the rule below from the keys alone. A consumer cannot change it. |

The `label` is `held_out` when the first eight hex digits of the SHA-256 of the text `<run_id>/<node_id>/<attempt_id>/<subnode_id>`, read as a number, divide by 5 with no remainder. Otherwise it is `development`. A null `subnode_id` is written as `-`. The rule depends only on the keys, so the same execution gets the same label in every export.

**ExportFile**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `path` | `string` | yes | relative to the export folder, no `..`, no leading `/` | File path. |
| `sha256` | `sha256` | yes | digest of the exact bytes | File digest. |
| `bytes` | `integer` | yes | min 0 | File size in bytes. |

**Invariants**

- The export folder is written once and never changed. A different set of files is a new export with a new ID.
- Failed executions are included. An execution is left out only with an `omitted` entry.
- The export is read-only for its consumers. The builder never writes into a run folder, `records.jsonl` or `bundles/`.
- Every entry's `run_id` has a bundle in `bundle_refs`.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `export_content_hash_recomputes` | `content_sha256` recomputes from `files` by the rule above | the export is refused |
| `export_labels_match_rule` | Every `label` equals the label the keys give by the rule above | the export is refused |
| `export_entries_have_files` | Every `call_folder` is a prefix of at least one `files` path, no `files` path escapes the folder, and every entry matches a line of the exported records file by `observation_id` and keys | the export is refused |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A host check fails | No export is published. The run is not affected | The records and raw evidence |
| Export interrupted | The partial folder is discarded. A later export gets a new ID | The records and raw evidence |



**Minimum quality bar.** Two consumers who read the same export ID and `content_sha256` hold identical data, and a held-out execution is the same execution in every export.

## Library analysis

A file computed from the capsule library alone is library analysis, and it is later work ([D21](../method/decisions.md#d21)). The name `library_snapshot` already means the Planner's list of eligible CCs ([library snapshot](run-plan.md#library-snapshot)) and keeps that meaning ([D37](../method/decisions.md#d37)).
