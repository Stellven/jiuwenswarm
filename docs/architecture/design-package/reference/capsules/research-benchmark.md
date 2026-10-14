# Research Benchmark capability capsule (`research.benchmark`)

**Reading level: AI reference.** Naming note: this is the scientific Research Benchmark CC. It measures a baseline and a treatment inside one research run. It is not the platform benchmark, which is the external runner that tests the AI4Research system.

**Summary for reviewers**

- A deterministic tool installs the frozen dependency lock, runs the unmodified baseline, then runs the treatment, and repeats as often as the blueprint says.
- It records raw repeats, aggregates and deltas. It never judges the result. Success, failure and classification belong to Scientific Evaluation.
- The protected executor writes two receipts (what ran, and what was installed). The payload points to them, and host checks compare all three against the frozen blueprint and lock.
- A failed install or a failed baseline run ends the node for human triage. A failed treatment run is recorded as an unmeasured metric with a reason.

## 1. Purpose and place in the run

The CC sits after Builder and before Scientific Evaluation in the static template. It is a fixed template node. The Planner may not select, skip or reorder it. The protected provisioner and executor do the effects. The CC assembles the measurements from what they record.

## 2. Declaration

Example: [research_benchmark_capsule.json](../examples/research_benchmark_capsule.json). It validates against the [declaration schema](../schemas/capsule-declaration.schema.json).

| Item | Value |
|---|---|
| Name and kind | `research.benchmark`, `tool`. No model is used in M1. |
| Inputs | `poc_manifest`, `poc_artifact_bundle`, `build_receipt`, `hypothesis_blueprint`, `baseline_resource`, `validation_resource`, `environment_lock` |
| Outputs | `benchmark_payload`, `execution_receipt`, `provisioning_receipt` |
| Effect class | `compensable`. All writes stay in the run workspace `/workspace/poc/`, which the run can remove. |
| Network | Allowlist egress to the approved package index during provisioning only. No network during measured runs. |
| Resources | Write `workspace_poc`, read `baseline_resource`, exclusive `gpu_device` (single GPU in M1). |
| Budget | 3600 s wall, 1 invocation, hard. |
| Pinned checks | The check bundle in section 6 and the criteria in section 7, assigned by the protected binder. |

## 3. Inputs

| Port | Artifact type | Producer | Required | Use |
|---|---|---|---|---|
| `poc_manifest` | `poc_manifest` (`poc-manifest:field-contract:2`) | Builder (output port `manifest`) | yes | Names the bundle, scripts, dependencies and lock the POC was built against. |
| `poc_artifact_bundle` | `poc_artifact_bundle` (`poc-artifact-bundle:field-contract:1`, bytes named by `poc_manifest.archive_ref`) | Builder (output port `bundle`) | yes | The executable treatment. Unpacked into the workspace. |
| `build_receipt` | `build_receipt` (`build-receipt:field-contract:1`) | Host record of the accepted Builder attempt (`host_record` key `build_receipt`) | yes | The Builder's build evidence. The manifest no longer carries evidence. Benchmark starts only when `readiness` is `READY`, the receipt's `manifest_ref` and `archive_ref` equal the inputs and `trial_executed` and `packages_installed` are false. |
| `hypothesis_blueprint` | `hypothesis_blueprint` (`hypothesis-blueprint:field-contract:2`) | Hypothesis (output port `blueprint`) | yes | The frozen protocol: `metrics`, `repeat_count`, `seed`, `seed_policy`, `baseline_identity`. Read only. The CC never reads `outcome_rules`. |
| `baseline_resource` | `resource_snapshot` (`resource-snapshot:field-contract:1`) | Protected resolver | yes | The supplied baseline, by digest. Run unmodified as the baseline subject. |
| `validation_resource` | `resource_snapshot` (`resource-snapshot:field-contract:1`) | Protected resolver | yes | The fixed validation data, by digest. |
| `environment_lock` | `environment_lock` (`environment-lock:field-contract:1`) | Protected resolver | yes | The exact dependency set to install. |

## 4. Output field contracts

Three artifacts. The plain-language meaning and constraint in each row define the field. Examples only illustrate.

### 4.1 `benchmark_payload` (`benchmark-payload:field-contract:2`)

File `benchmark_payload.json`. Contains measurements only. It has no pass, fail or interpretation field.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | string | yes | `2.0.0` | Format version. |
| `id` | string | yes | `benchmark_payload` | Artifact identity. |
| `blueprint_ref` | Ref | yes | Must equal the input blueprint's Ref | The frozen protocol the runs followed. |
| `poc_ref` | Ref | yes | Must equal the input `poc_manifest` Ref | The POC that was run as the treatment. |
| `environment_lock_ref` | Ref | yes | Must equal the input lock and `blueprint.environment_ref` | The lock that was installed. |
| `resource_refs` | Ref[] | yes | min 1. Must equal the blueprint `resource_refs` as a set | The baseline and validation data used. |
| `configuration_ref` | Ref | yes | Resolves to the run configuration | The effective run configuration (model route, seed policy). |
| `execution_receipt_ref` | Ref | yes | Resolves to an `execution_receipt` | The per-run record. |
| `provisioning_receipt_ref` | Ref | yes | Resolves to a `provisioning_receipt` with status `succeeded` | The install record. |
| `repeat_count` | integer | yes | min 1. Must equal `blueprint.repeat_count` | Number of repeats per role. |
| `seed` | integer | yes | Must equal `blueprint.seed` | The registered seed. Blueprint `seed_policy` `fixed_same_for_all_runs` means every run of both roles uses it. |
| `run_order` | string[] | yes | Each item is `baseline` or `treatment`. Length is `2 * repeat_count`. All `baseline` items come before every `treatment` item. | Execution order of the runs, copied from the receipt so the payload is self-checking. |
| `metrics` | BenchmarkMetric[] | yes | Exactly one item per blueprint metric. No extras. | Every registered measurement. |
| `raw_evidence_refs` | Ref[] | yes | min 1. Must contain `empirical_results_ref` and every run's `stdout_ref` and `stderr_ref` from the receipt | Evidence the values came from sandbox execution. |

`BenchmarkMetric`

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `metric_id` | string | yes | Equals a blueprint `metric_id` | The registered metric. |
| `unit` | string | yes | Equals the blueprint unit | Unit of every value. |
| `aggregation` | string | yes | enum `min`, `max`, `mean`, `median`. Equals the blueprint aggregation | How repeats combine into `value`. |
| `baseline` | MetricSide | yes | none | Baseline measurements. |
| `treatment` | MetricSide | yes | none | Treatment measurements. |
| `delta` | nullable-number | yes | Non-null exactly when both `value` fields are non-null. Then `delta = treatment.value - baseline.value` within relative 1e-9 | Absolute difference, always treatment minus baseline. Never a percentage. |

`MetricSide`

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `repeats` | number[] | yes | Length equals `repeat_count` when `value` is non-null. Length 0 to `repeat_count` otherwise. Finite numbers only | Raw value of each completed repeat, in repeat order. |
| `value` | nullable-number | yes | Null exactly when `unmeasured_reason` is non-null. Otherwise equals `aggregation` applied to `repeats` within relative 1e-9 | The registered aggregate. |
| `unmeasured_reason` | nullable-string | yes | Null or enum `run_failed`, `timeout`, `metric_not_emitted`, `non_finite_value`, `resource_limit_exceeded` | Why no value exists. Every metric side has a value or a reason, never both and never neither. |

Examples: [valid](../examples/benchmark_payload.json) · rejected by `metric_value_or_reason`: [benchmark_payload_invalid_missing_treatment_reason](../examples/benchmark_payload_invalid_missing_treatment_reason.json) · rejected by `baseline_before_treatment`: [benchmark_payload_invalid_treatment_first](../examples/benchmark_payload_invalid_treatment_first.json)

### 4.2 `execution_receipt` (`execution-receipt:field-contract:1`)

File `execution_receipt.json`. Written by the protected executor from what it observed. The worker cannot edit it.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | string | yes | `1.0.0` | Format version. |
| `id` | string | yes | `execution_receipt` | Artifact identity. |
| `blueprint_ref` | Ref | yes | Equals the input blueprint | Protocol the runs followed. |
| `poc_ref` | Ref | yes | Equals the input `poc_manifest` | POC under test. |
| `hardware_inventory` | HardwareInventory | yes | none | Hardware observed once, before the first run. |
| `empirical_results_ref` | Ref | yes | Resolves to an `empirical_results` file | The parsed metric values of every run. |
| `runs` | RunRecord[] | yes | min 2. `sequence` is 1..N with no gaps. Exactly `repeat_count` baseline runs and `repeat_count` treatment runs | One record per run, in execution order. |

`RunRecord`

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `sequence` | integer | yes | min 1. Unique | Global execution position. |
| `role` | string | yes | enum `baseline`, `treatment` | Which subject ran. |
| `repeat_index` | integer | yes | min 0, below `repeat_count`. Unique within a role | Repeat number within the role. |
| `seed` | integer | yes | Equals `blueprint.seed` for every run (policy `fixed_same_for_all_runs`) | Seed passed to the run. |
| `subject_ref` | Ref | yes | Baseline: equals `blueprint.baseline_identity.resource_ref`. Treatment: equals the manifest `archive_ref` | Exactly what was run. Proves the baseline was unmodified. |
| `command` | string[] | yes | min 1 item. First item is an interpreter or executable | The command line as executed. |
| `exit_code` | integer | yes | none | Process exit code. 0 means success. |
| `started_at` | string | yes | UTC ISO 8601. Not earlier than the previous run's start | Run start time. |
| `wall_time_s` | number | yes | min 0 | Elapsed time. |
| `timeout_s` | number | yes | Greater than 0. `wall_time_s` is at most this unless the run timed out | Time limit applied. |
| `stdout_ref` | Ref | yes | Resolves to stored bytes | Captured standard output. |
| `stderr_ref` | Ref | yes | Resolves to stored bytes | Captured standard error. |
| `hardware_ref` | string | yes | Equals `hardware_inventory.hardware_id` | Hardware the run used. All runs use the same value. |

`HardwareInventory`

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `hardware_id` | string | yes | non-empty | Identity runs refer to. |
| `gpu_model` | nullable-string | yes | Non-null when `gpu_count` is above 0 | GPU name. |
| `gpu_count` | integer | yes | min 0 | Number of GPUs visible to the runs. |
| `gpu_memory_mb` | nullable-integer | yes | Non-null when `gpu_count` is above 0 | Memory per GPU. |
| `driver_version` | nullable-string | yes | none | GPU driver. |
| `cuda_version` | nullable-string | yes | none | CUDA or equivalent runtime. |
| `cpu_model` | string | yes | non-empty | CPU name. |
| `cpu_cores` | integer | yes | min 1 | Logical cores. |
| `ram_mb` | integer | yes | min 1 | System memory. |
| `os` | string | yes | non-empty | Operating system and kernel. |
| `captured_at` | string | yes | UTC ISO 8601, before the first `started_at` | Capture time. |

`empirical_results` (file named by `empirical_results_ref`): `{schema_version, id: "empirical_results", runs: [{sequence: integer, metrics: {<metric_id>: number}}]}`. One entry per receipt run, same `sequence`. The protected executor builds it from the one JSON line that `run_benchmark.py` prints for each run, in the [output log format](builder.md#output-log-format) that the Builder's static check `output_log_format` verified. The payload repeats must equal these values.

Examples: [valid receipt](../examples/execution_receipt.json) · [valid empirical results](../examples/execution_receipt_empirical_results.json). No invalid receipt example. The ordering check `baseline_before_treatment` is shown on the payload.

### 4.3 `provisioning_receipt` (`provisioning-receipt:field-contract:1`)

File `provisioning_receipt.json`. Written by the protected provisioner.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | string | yes | `1.0.0` | Format version. |
| `id` | string | yes | `provisioning_receipt` | Artifact identity. |
| `environment_lock_ref` | Ref | yes | Equals the input lock | The lock that was meant to be installed. |
| `poc_manifest_ref` | Ref | yes | Equals the input manifest | The bundle that was unpacked. |
| `status` | string | yes | enum `succeeded`, `failed` | Outcome. `failed` ends the node and no payload is produced. |
| `python_version` | string | yes | non-empty | Interpreter version in the virtual environment. |
| `venv_path` | string | yes | Starts with `/workspace/poc/` | Where the environment lives. |
| `runner_user` | string | yes | Not `root` | Unprivileged user that owns the environment. |
| `packages` | InstalledPackage[] | yes | Name set equals the lock's package set. Empty when the lock lists none | What is installed. |
| `network_policy_used` | string | yes | enum `none`, `allowlist` | Network mode applied while installing. |
| `network_allowlist` | string[] | yes | Empty when policy is `none` | Hosts the policy allowed. |
| `unlisted_network_requests` | integer | yes | min 0. Must be 0 for `succeeded` | Requests to hosts outside the allowlist, all blocked. |
| `effects` | ProvisioningEffect[] | yes | min 1 | Changes made to the workspace, in order. |
| `limits` | object | yes | `{wall_s_limit: number > 0, wall_s_used: number >= 0}` | Install time limit and time used. |

`InstalledPackage`: `name` (string, non-empty), `locked_version` (string, exact, from the lock), `installed_version` (string, must equal `locked_version`), `hash_verified` (boolean, must be true when the lock carries a hash).

`ProvisioningEffect`: `op` (enum `unpack_bundle`, `create_venv`, `install_package`), `target` (string, a path under `/workspace/poc/`), `outcome` (enum `ok`, `failed`).

Examples: [valid](../examples/provisioning_receipt.json). The synthetic lock lists no packages, so `packages` is empty. No invalid example.

## 5. Producer obligations

The runner must:

1. Read the blueprint and take metrics, aggregation, `repeat_count` and `seed` from it. Never choose its own.
2. Unpack the bundle and install only the frozen lock into an unprivileged virtual environment under `/workspace/poc/`. Never add, remove or upgrade a package. Never resolve conflicts.
3. Run all baseline repeats first, then all treatment repeats, on the same hardware, data and seeds. Run the baseline from the unmodified supplied resource.
4. Block network access during measured runs.
5. Parse metric values only from `empirical_results`. Never estimate, fill or smooth a value. Record an unmeasured reason instead.
6. Compute aggregates and deltas with one routine: aggregate by the blueprint rule, then `treatment - baseline`.
7. Write no pass, fail, ranking or recommendation anywhere.

Self-review before emitting the payload: re-read the blueprint and confirm each metric appears once, each side has a value or a reason, the repeat count matches, and the order is baseline first. Confirm each receipt `sequence` has an `empirical_results` entry.

## 6. Deterministic check bundle

The host runs these before the verifier. They read inputs and runtime records.

| Check ID | Rule | Outcome on failure |
|---|---|---|
| `payload_schema` | All three outputs match their field tables, enums and ranges above. | reject |
| `build_receipt_ready` | Input check. The `build_receipt` input has `readiness` `READY`, its `manifest_ref` and `archive_ref` equal the manifest and bundle inputs, and `trial_executed` and `packages_installed` are false. A failed check halts the node before provisioning. | halt |
| `refs_resolve` | Every Ref resolves to stored bytes with the stated sha256. | reject |
| `protocol_matches_blueprint` | `blueprint_ref`, `repeat_count`, `seed`, `seed_policy`, per-run seeds, `resource_refs`, and each metric's id, unit and aggregation equal the frozen blueprint. | reject |
| `metric_coverage` | Each blueprint metric appears exactly once. No extra metric. | reject |
| `metric_value_or_reason` | Each `MetricSide` has a value or a reason, never both and never neither. | reject |
| `baseline_before_treatment` | `run_order` and the receipt `sequence` and `started_at` place every baseline run before every treatment run. The payload and receipt orders agree. | reject |
| `baseline_unmodified` | Baseline `subject_ref` equals `blueprint.baseline_identity.resource_ref`, and the baseline command runs its `entry_point`. Treatment `subject_ref` equals the manifest `archive_ref`. | reject |
| `environment_lock_match` | Payload, receipt, manifest and blueprint name the same lock. Installed packages equal the lock set with exact versions. | reject |
| `hardware_inventory_captured` | `hardware_inventory` is complete and every run's `hardware_ref` equals it. | reject |
| `raw_repeats_present` | Each measured side has `repeat_count` repeats. Each run has stored stdout, stderr and an `empirical_results` entry. | reject |
| `values_match_empirical_results` | Every payload repeat equals the value in `empirical_results` for that run and metric. | reject |
| `arithmetic_consistent` | Each `value` and `delta` recomputes from the repeats within relative 1e-9. | reject |
| `network_policy_respected` | Provisioning used the declared policy with no unlisted requests, and runs had no network. | reject |

## 7. Verifier criteria

The verifier sees only the declaration and the exact payload. Reduced assurance applies: it cannot confirm the values are true, only that the output is coherent.

| Criterion ID | Question | Blocking |
|---|---|---|
| `no_interpretation` | Does the payload avoid any judgement, classification, recommendation or success wording? | yes |
| `side_has_value_or_reason` | Does every metric side show either an aggregate value or an unmeasured reason, but not both? | yes |
| `run_order_baseline_first` | Does `run_order` list every baseline run before any treatment run? | yes |
| `repeats_match_aggregate` | Do the listed repeats agree with the stated aggregation, value and delta, and does each full side have `repeat_count` repeats? | yes |
| `delta_direction_consistent` | Is every delta treatment minus baseline, in the metric unit? | yes |

## 8. Gate rule

Accept when every host check passes and no blocking criterion fails. Reject for any host check failure, with no fabricated repair. Halt for human triage when the build receipt is not `READY`, provisioning fails or the baseline run fails. The Benchmark CC has three outputs (`benchmark_payload`, `execution_receipt`, `provisioning_receipt`). The verifier runs once for each output artifact, each time with the same pinned declaration. The criteria in section 7 apply to the `benchmark_payload` run. The generic criteria of the checking profile apply to every run.

## 9. Failure outcomes

| Condition | Outcome | Kept |
|---|---|---|
| Build receipt not `READY` | Halt, no payload | Build receipt |
| Provisioning `failed` | Halt, no payload | Provisioning receipt, logs |
| Baseline run exits non-zero or times out | Halt, no payload | Receipts, logs |
| Treatment run fails or times out | Payload emitted with `unmeasured_reason` `run_failed` or `timeout` on the treatment side | All receipts, payload |
| A metric not emitted | Payload emitted with `metric_not_emitted` | All receipts, payload |
| Host check fails | Reject. One retry as the plan allows. | Rejected output, check result |

A payload with unmeasured sides is valid data. Scientific Evaluation classifies it `INCONCLUSIVE`.

## 10. Examples

| File | Role | Rejected by |
|---|---|---|
| [benchmark_payload.json](../examples/benchmark_payload.json) | valid | none |
| [execution_receipt.json](../examples/execution_receipt.json) | valid | none |
| [execution_receipt_empirical_results.json](../examples/execution_receipt_empirical_results.json) | valid supporting file | none |
| [provisioning_receipt.json](../examples/provisioning_receipt.json) | valid | none |
| [benchmark_payload_invalid_missing_treatment_reason.json](../examples/benchmark_payload_invalid_missing_treatment_reason.json) | invalid | `metric_value_or_reason` |
| [benchmark_payload_invalid_treatment_first.json](../examples/benchmark_payload_invalid_treatment_first.json) | invalid | `baseline_before_treatment` |
| [research_benchmark_capsule.json](../examples/research_benchmark_capsule.json) | declaration | none |

The older one-line placeholders `baseline_execution.txt`, `treatment_execution.txt` and `provisioning_example.txt` remain as synthetic stdout files. They are no longer the execution or provisioning contracts.

## 11. Future seams

- Multi-GPU, distributed and remote execution add fields to `HardwareInventory` and `RunRecord`. They do not change the payload.
- Other seed policies (per-repeat seeds) change only the per-run seed rule. Interleaved baseline and treatment order would change only the order rule. The `sequence` field already records order.
- A Model Router or Generalist may call this CC with another blueprint unchanged. The CC takes no model route.
- Capsule admission can reuse the `execution_receipt` shape as run evidence.
