# Builder capsule (`research.builder`)

`Tier 3 · Part of: [Reference](../README.md)`

Build page for one CC and its verifier assignment.

**Summary for human review**

- Input: the frozen hypothesis blueprint, the two captured resources and the prepared environment lock.
- Output: a zip bundle with exactly three files (`requirements.txt`, `poc_patch.py`, `run_benchmark.py`) and a readable `poc_manifest` that describes it.
- The Builder writes code and packages it. It runs no trial and installs nothing. Its only evidence is build evidence: does the code compile, does it avoid forbidden modules, are all dependencies pinned. A host-written `build_receipt` records that evidence.
- One build check reads `run_benchmark.py` as text and confirms it prints its metrics in the single JSON line format that Research Benchmark parses (PRD 3.6.4). No code runs.
- The verifier reviews each output (`manifest`, `bundle`) in its own call, with the same declaration.
- Execution evidence (measurements, stdout, installs) belongs to Research Benchmark. This page fixes the older wording in `cc-build-coverage.md` that said the Builder outputs execution evidence.

## Purpose and place in the run

Builder is PRD stage 3.6. It writes the proof of concept for one hypothesis. It reads the frozen blueprint and cannot change the validation data, measurement functions or outcome rules (PRD 3.6.3). It does not repair its own failures. A failed check stops the Builder node and writes an escalation record for later human review; the run does not wait (PRD 3.6.4, 4.9.5).

## Declaration

Declaration example: [builder_capsule.json](../examples/builder_capsule.json). It validates against the [declaration schema](../schemas/capsule-declaration.schema.json).

| Item | Value |
|---|---|
| Name | `research.builder`, kind `agent` |
| Needs | The model bridge with tool calling. The agent work is one synchronous Codex CLI invocation (headless, `codex exec` style) per CC call ([D43](../../method/decisions.md#d43)). Codex does its own tool use (read, code search and write) inside the confined POC workspace, scoped to the `poc_workspace` resource with write access. The launch, the sandbox mode and the credential are fixed in [Tool-use sandbox](#tool-use-sandbox) ([D45](../../method/decisions.md#d45)). No network for tool commands. No external operator is pinned in M1. |
| Effect class | `idempotent`. Writes only under `/workspace/poc/`. Starts no process except the compile check run by the host. |
| Budget | 600 s wall, 1 invocation, 40 tool calls, hard. The runner counts the tool events the CLI reports and stops it at 40 ([D43](../../method/decisions.md#d43)) |
| Pinned check bundle | The declaration pins `manifest_schema`, `bundle_schema`, `required_files_present`, `dependencies_pinned`, `bundle_hash_matches`, `syntax_check` and `forbidden_modules_absent`. The binder adds the other host checks below. The Planner cannot drop or weaken any of them. |
| Output ports | `manifest` and `bundle`. The host-written `build_receipt` is not an output port. It reaches Research Benchmark as a `host_record` input. |
| Verifier runs | Once per output artifact (`manifest`, then `bundle`). Each run gets the same pinned declaration and the same checking profile. A criterion applies only to the output named in the criteria table. |

## Tool-use sandbox

`Standard`. The Builder's Codex CLI call is the only place where a model runs commands. [D45](../../method/decisions.md#d45) amends [D43](../../method/decisions.md#d43) with these rules. The platform page states the confinement they rely on ([platform](../../platform/README.md#deployment-and-boundaries), PLT-11).

| Item | Rule |
|---|---|
| Who launches the CLI | The launcher of the confined executor, under the executor OS identity. The app's own identity does not run it |
| Working directory | The POC workspace |
| Codex sandbox mode | `workspace-write`, with the network disabled for tool commands |
| Approvals | `never`. The CLI never waits for a person |
| Credential | A dedicated Builder model credential. It is budget-limited and revocable. It is never the app's main credential. The credential file is readable only by the executor identity for the duration of the call, and is removed after the call |
| What the executor identity cannot read | Run state, every other credential, the library and the fixtures. Filesystem permissions enforce this, not prompts |
| Residual risk | A tool command inside the call can read the Builder credential. This is accepted and recorded. Its budget limit and its revocation bound the damage |

The CLI process itself reaches the model endpoint. Only the tool commands it starts run without network. The model bridge still writes the route record before the call and the model-call record from the tool events the CLI reports. Criterion PLT-11: a probe from a Builder tool call must be denied when it reads run state, the main credential or a fixture path.

## Inputs

| Port | Artifact type | Producer | Required | Use |
|---|---|---|---|---|
| `blueprint` | `hypothesis_blueprint` | Hypothesis | yes | Intervention, scope limits, metric ids, repeat count and seed to wire into the harness. |
| `baseline_resource` | `resource_snapshot` | protected resolver | yes | The baseline code the harness runs unmodified. |
| `validation_resource` | `resource_snapshot` | protected resolver | yes | Fixed data the harness reads. |
| `lock` | `environment_lock` | protected environment preparation | yes | The only dependencies the bundle may declare. |

## Output field contract

The Builder produces two artifacts. The host adds a third record, `build_receipt`, after it checks the output.

### poc_manifest

Contract `poc-manifest:field-contract:2`, version 2.0.0. This version drops `mechanical_evidence_refs` (the receipt now points to the manifest instead, so the worker cannot forge its own evidence) and adds `dependencies`.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `2.0.0` | Format version. |
| `id` | `string` | yes | non-empty | Record identity. |
| `blueprint_ref` | `Ref` | yes | equals the input blueprint ref | The frozen protocol this bundle implements. The Builder CC copies the input blueprint Ref and cannot choose another. |
| `environment_ref` | `Ref` | yes | equals the blueprint and lock `environment_ref` | The prepared lock. The Builder cannot change it. |
| `archive_ref` | `Ref` | yes | `sha256` equals the SHA-256 of the bundle zip bytes | The bundle zip this manifest describes. Its `sha256` is the SHA-256 of the zip bytes, which Research Benchmark unpacks. |
| `files` | `NamedFile[]` | yes | exactly 3 entries. `path` values are exactly `requirements.txt`, `poc_patch.py`, `run_benchmark.py`, lowercase, no directories. `artifact_ref.sha256` equals the hash of that entry inside the zip. | Every file in the bundle, with the hash of its entry in the zip. No other file is allowed. |
| `dependencies` | `Dependency[]` | yes | `min_items` 0, `max_items` 50. Equals the parsed lines of `requirements.txt`. Each is a subset of the lock pins. | Full list of packages the bundle needs, equal to the parsed `requirements.txt` lines. Empty when only the standard library is used. |

Examples: [valid](../examples/poc_manifest.json)

### Dependency

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `name` | `string` | yes | pattern `^[a-z0-9][a-z0-9._-]*$` | Package name, lowercase. |
| `version` | `string` | yes | pattern `^[0-9]+(\.[0-9]+)*$` | One exact version. No range, wildcard, URL or marker. In `requirements.txt` the line is `name==version`. |



### poc_artifact_bundle

Purpose: the proof-of-concept files Research Benchmark runs. It is a zip file, not JSON. The fields below are its logical parts, and the validator reads them from the zip.

`poc-artifact-bundle:field-contract:1` (version 1.0.0) · Producer: Builder CC (`research.builder`). Consumers: Builder host checks, Verifier CC (through the [zip projection](verifier.md#zip-output-projection)), Research Benchmark.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `archive_format` | `string` | yes | enum `zip`. No password. At most 1 MiB. | Container format. |
| `entry_names` | `string[]` | yes | exactly `requirements.txt`, `poc_patch.py`, `run_benchmark.py` at the root. Lowercase. No other entry, directory, link or path with `..`. | The only files in the zip. |
| `requirements_txt` | `string` | yes | one `name==version` per line. Comments allowed. No `-r`, `-e`, URL, VCS reference, index option or range. Every pin is in the environment lock. | Content of the entry `requirements.txt`. |
| `poc_patch_py` | `string` | yes | valid Python 3 syntax. One standalone file implementing the blueprint `independent_variable`. No forbidden import. | Content of the entry `poc_patch.py`. |
| `run_benchmark_py` | `string` | yes | valid Python 3 syntax. No forbidden import. Runs the unmodified baseline or the patched treatment as its command line says, with the registered seed and validation data. Prints one line in the [output log format](#output-log-format) per invocation, with one value for every declared `metric_id`. | Content of the entry `run_benchmark.py`. |

The fields are the logical parts of the zip. The zip itself is the artifact.

**Enum `archive_format`**

| Value | Meaning |
|---|---|
| `zip` | A standard zip archive with no password |

**Invariants**

- The zip holds exactly the three entries, at the root, with no directory, link or `..` path.
- The SHA-256 of the zip equals the manifest `archive_ref.sha256`, and each entry hash equals its manifest file hash.
- Every pin in `requirements.txt` is in the environment lock.

**Producer obligations (Builder CC)**

- Write the three files only. Never add data, results or a fourth file.
- Never import a forbidden module or use dynamic import.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `bundle_schema` | No password, at most 1 MiB, no directory entry, and the logical parts match `poc-artifact-bundle:field-contract:1` | reject |
| `required_files_present` | The entries are exactly the three required names, lowercase, with no traversal | reject |
| `bundle_hash_matches` | The zip and entry hashes equal the manifest | reject |

The full Builder check bundle is in [deterministic check bundle](#deterministic-check-bundle).

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A host check fails | Reject the output, stop the Builder node and write an escalation record for later human review | The zip, the manifest and the check result |

Examples: [valid](../examples/poc_artifact_bundle.zip). The bundle is a packaging fixture and claims no scientific result.

**Minimum quality bar.** Research Benchmark can unpack and run the bundle with nothing but the lock, and every byte it runs is pinned by the manifest.

### build_receipt

Purpose: the host's record of the Builder checks. It is build evidence only. It never holds measurements.

`build-receipt:field-contract:1` (version 1.0.0) · Producer: the Builder host check bundle, never the worker. Consumers: Research Benchmark (`build_receipt_ready`), Builder gate, Delivery.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `1.0.0` | Format version. |
| `id` | `string` | yes | non-empty | Record identity. |
| `manifest_ref` | `Ref` | yes | resolves to the checked manifest | The manifest this receipt covers. The host writes the receipt, never the worker. |
| `blueprint_ref` | `Ref` | yes | equals the manifest `blueprint_ref` | The frozen protocol. |
| `environment_ref` | `Ref` | yes | equals the manifest `environment_ref` | The prepared lock. |
| `archive_ref` | `Ref` | yes | equals the manifest `archive_ref` | The bundle that was checked. |
| `checker` | `string` | yes | non-empty | Name and version of the compile and import scan tools the host used. |
| `file_checks` | `BuildFileCheck[]` | yes | exactly one entry per bundle file, same paths as the manifest | Per-file result. |
| `forbidden_modules_ref` | `Ref` | yes | resolves to the list pinned in the check bundle | Points at the forbidden-module list pinned in the check bundle, so a reader can see which list ran. |
| `forbidden_scan_result` | `string` | yes | enum `pass`, `fail`. `pass` only when every `forbidden_imports` is empty. | Result of the import scan across all `.py` files. Host-set from a fresh scan, never from the worker. |
| `output_format_check` | `OutputFormatCheck` | yes | see the type below | Static check that `run_benchmark.py` prints its metrics in the output log format. The host runs no code. Written by the host. |
| `dependencies` | `Dependency[]` | yes | full list, equals the manifest `dependencies` | Every dependency, fully listed. |
| `dependencies_all_pinned` | `boolean` | yes | true only when every entry has an exact version | Pin check result, set by the host. True only when every dependency has an exact version. |
| `trial_executed` | `boolean` | yes | must be `false` | Confirms no POC code ran. Host-set from the runtime record, and must be `false`. Compilation does not run the code. |
| `packages_installed` | `boolean` | yes | must be `false` | Confirms nothing was installed. Host-set from the runtime record, and must be `false`. |
| `readiness` | `string` | yes | enum `READY`, `NOT_READY`. `READY` only when every syntax result is `pass` or `not_applicable`, `forbidden_scan_result` is `pass`, `output_format_check.result` is `pass` and `dependencies_all_pinned` is true. | Mechanical readiness for Benchmark. The host sets it from the evidence above, never the worker. Benchmark starts only when it is `READY`. |
| `readiness_reasons` | `string[]` | yes | empty when `READY`. At least one entry otherwise. | Why the bundle is not ready, for people and the escalation record. Empty when `READY`. |

**Enum `forbidden_scan_result`**

| Value | Meaning |
|---|---|
| `pass` | No file has a forbidden import |
| `fail` | At least one file has a forbidden import or a dynamic import |

**Enum `readiness`**

| Value | Meaning |
|---|---|
| `READY` | Every syntax result is `pass` or `not_applicable`, the scan passed, the output format check passed and every dependency is pinned |
| `NOT_READY` | Any of those failed. `readiness_reasons` says which |

**Invariants**

- `trial_executed` and `packages_installed` are false.
- `readiness` is `READY` exactly when the rule above holds, and `readiness_reasons` is empty exactly then.
- `file_checks` paths equal the manifest file paths, and each hash equals the zip entry.
- `dependencies` equals the manifest `dependencies`.

**Producer obligations (host check bundle)**

- Compute every result from the zip, the manifest, the blueprint and the pinned forbidden list. Never copy a worker claim.
- Never run the POC or install a package to fill the receipt.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `build_receipt_schema` | The receipt matches `build-receipt:field-contract:1` | reject |
| `bundle_hash_matches` | Receipt refs equal the manifest, and each file hash equals the zip entry | reject |
| `syntax_check` | Each syntax result equals a fresh compile of the entry | reject |
| `forbidden_modules_absent` | The forbidden imports and the scan result equal a fresh AST scan | reject |
| `output_log_format` | `output_format_check` equals a fresh static scan | reject |
| `dependencies_pinned` | Dependencies equal the manifest and the pin flag is right | reject |
| `build_receipt_ready` | No trial or install is recorded, and `readiness` follows the evidence | reject |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| A receipt check fails | Reject the output, stop the Builder node and write an escalation record for later human review | The receipt, the bundle and the manifest |
| `readiness` is `NOT_READY` | Stop the Builder node and write an escalation record; Benchmark does not start | The receipt with its reasons |

Examples: [valid](../examples/build_receipt.json) · forbidden list: [build_receipt_forbidden_modules.txt](../examples/build_receipt_forbidden_modules.txt) · rejected by `build_receipt_ready`: [build_receipt_invalid_ready_with_forbidden_import](../examples/build_receipt_invalid_ready_with_forbidden_import.json) (`READY` while the scan failed)

**Minimum quality bar.** Research Benchmark can decide to start from the receipt alone, and every result in it can be recomputed from the zip.

### BuildFileCheck

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `path` | `string` | yes | one of the three bundle paths | The file checked. |
| `sha256` | `sha256` | yes | equals the hash of the entry in the zip | Hash of the zip entry that was checked. The exact bytes checked. |
| `syntax_result` | `string` | yes | enum `pass`, `fail`, `not_applicable`. `not_applicable` only for `requirements.txt`. | Result of `python -m py_compile` equivalent. Compiling does not run the module code. |
| `syntax_detail` | `nullable-string` | yes | not null when `fail`. At most 500 characters. | Compiler message. Required when `syntax_result` is `fail`. At most 500 characters. |
| `forbidden_imports` | `string[]` | yes | empty for `requirements.txt` | Forbidden modules found by an AST import scan, plus any use of `__import__`, `importlib`, `exec` or `eval`. |

Examples: [valid](../examples/build_receipt.json) (field `file_checks`)

### OutputFormatCheck

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `result` | `string` | yes | enum `pass`, `fail`. `pass` only when `json_print_calls` is 1, `metrics_key_found` is true and `missing_metric_ids` is empty. | Outcome of the static output log format check. |
| `json_print_calls` | `integer` | yes | min 0 | Number of `print(json.dumps(...))` calls the AST scan found in `run_benchmark.py`. |
| `metrics_key_found` | `boolean` | yes | none | True when the argument of that call is a dict display with the string key `metrics`. |
| `missing_metric_ids` | `string[]` | yes | empty when none are missing | Blueprint `metric_id` values that appear nowhere as a string constant in the file. |

Examples: [valid](../examples/build_receipt.json) (field `output_format_check`)

### Output log format

PRD 3.6.4 asks for a check that the log output conforms to the expected schema. The Builder runs no code, so M1 checks the text of `run_benchmark.py` statically. The format is the one Research Benchmark parses. Each invocation of `run_benchmark.py` prints exactly one line to standard output. The line is one JSON object `{"metrics": {"<metric_id>": <number>}}`. It has one key under `metrics` for every blueprint `metric_id`, and no other key. The protected executor reads that line from each run and writes the run's entry in `empirical_results` (see [Research Benchmark](research-benchmark.md)). The values at run time must be finite numbers. A run that prints anything else has no value for that metric and Benchmark records `metric_not_emitted`.

The static check is the host check `output_log_format`. It parses `run_benchmark.py` with the Python `ast` module and requires all of the following.

1. Exactly one `print` call whose single argument is a `json.dumps(...)` call.
2. A dict display with the string key `metrics` inside that argument.
3. Every blueprint `metric_id` appears as a string constant in the file.
4. No other call to `print`.

The check cannot prove that the values are right. It only shows that the file is built to print the expected line. Benchmark still checks the real output with `values_match_empirical_results` and `raw_repeats_present`.

### Forbidden-module list

The list lives in the pinned check bundle, not in the worker prompt or declaration. The Verifier owner owns it. M1 content comes from PRD 3.6.2: `os`, `sys`, `subprocess`, `requests`, `urllib`, `shutil`. The receipt points at it through `forbidden_modules_ref`, so a reader can see exactly which list ran. An import scan does not confine code. Sandbox confinement at Benchmark is separate.

## Producer obligations

- Read the blueprint. Build only what `implementation_scope` allows. Write one patch file.
- Write the three files and a manifest. Use only the lock's dependencies and pin each exactly.
- Do not run the POC, any trial or any install. Do not fetch packages or data. Do not add or change a dependency after writing `requirements.txt`.
- Do not change the validation data path, measurement functions or outcome rules. `run_benchmark.py` reads them from the blueprint.
- Do not import a forbidden module. Do not use dynamic import to avoid the scan.
- Do not write measured numbers into any file.
- Make `run_benchmark.py` print exactly one line in the output log format for each invocation: `print(json.dumps({"metrics": {...}}))` with one key for every blueprint `metric_id`. Use no other `print`.
- Self-review before returning. Re-read the blueprint and confirm every `metric_id` is a key of the printed `metrics` object in `run_benchmark.py`, the repeat count and seed match, and baseline runs before treatment. Confirm `requirements.txt` lists only pinned lock entries. Confirm the manifest lists all three files with correct hashes.
- On a failed check, do not repair in a loop. The node stops and an escalation record is kept for later human review; the run does not wait.

## Deterministic check bundle

The host runs these before the verifier. It writes `build_receipt` from the results.

| Check ID | Rule | Outcome on failure |
|---|---|---|
| `manifest_schema` | Manifest matches `poc-manifest:field-contract:2`. | reject |
| `bundle_schema` | The bundle is a zip with no password, at most 1 MiB, and its entries and logical parts match `poc-artifact-bundle:field-contract:1`. | reject |
| `required_files_present` | Zip entries are exactly the three required names, lowercase, no extra, no traversal. The manifest `files` paths match. | reject |
| `bundle_hash_matches` | SHA-256 of the zip equals `archive_ref.sha256`. Each entry hash equals the manifest `artifact_ref.sha256`. | reject |
| `dependencies_pinned` | Every `requirements.txt` line is `name==exact version` with no option, URL or range. `dependencies` equals the parsed lines. | reject |
| `requirements_within_lock` | Every pin appears in the environment lock requirements. | reject |
| `syntax_check` | Each `.py` file compiles. Compilation only, no execution. | reject, receipt `NOT_READY` |
| `forbidden_modules_absent` | AST import scan against the pinned list finds none. Dynamic import names are flagged. | reject, receipt `NOT_READY` |
| `output_log_format` | Static AST scan of `run_benchmark.py`, no code runs. Exactly one `print(json.dumps(...))` call, a dict display with the key `metrics` inside it, every blueprint `metric_id` present as a string constant, no other `print` call. The host writes the result to `build_receipt.output_format_check`. Reads the blueprint. | reject, receipt `NOT_READY` |
| `blueprint_unchanged` | Manifest `blueprint_ref` equals the frozen blueprint hash in the run record. | halt the run |
| `environment_unchanged` | Manifest, blueprint and lock agree on `environment_ref`. | reject |
| `no_trial_no_install` | The runtime record shows no POC process, no package manager call and no network use. The build receipt flags `trial_executed` and `packages_installed` are false. | halt the run |
| `build_receipt_ready` | The receipt exists, `trial_executed` and `packages_installed` are false, `output_format_check.result` is `pass` and `readiness` is `READY`. | reject |

## Verifier criteria

The verifier runs once for each output artifact, `manifest` and `bundle`, each time with the same pinned declaration. In the `manifest` run it sees the declaration and the manifest. In the `bundle` run it sees the declaration and the [zip projection](verifier.md#zip-output-projection) of the bundle, a text listing of every file path, hash and full text. It never sees the blueprint, so it cannot judge protocol fidelity. The verifier is a reduced-assurance reviewer. The generic criteria of the [checking profile](verifier.md#checking_profile-contract) apply to both runs.

| Criterion ID | Output | Question | Blocking |
|---|---|---|---|
| `manifest_claims_no_execution` | `manifest` | Does the manifest avoid any claim that a trial ran, packages were installed, or measurements were taken? | yes |
| `no_embedded_results` | `bundle` | Does any script avoid hard-coded measurement results and avoid claiming that a trial ran, so that values come from code that computes them at run time? | yes |
| `harness_orders_baseline_first` | `bundle` | Does `run_benchmark.py` run the baseline before the treatment, using one seed and one data source for both? | yes |
| `patch_is_single_bounded_file` | `bundle` | Is `poc_patch.py` one standalone file with a stated purpose and no code that edits other files? | no |

## Gate rule

Accept when every check passes and no blocking criterion fails. Reject on any failure. A syntax or forbidden-module failure records the receipt as `NOT_READY`, stops the Builder node and writes an escalation record for later human review. The forbidden-import result is a failed package check; by itself, it does not establish that a live integrity boundary was breached. There is no automatic retry or repair, and the run does not wait. Benchmark starts only after acceptance with a `READY` receipt.

## Failure outcomes

| Condition | Outcome | Kept |
|---|---|---|
| Syntax or forbidden import failure | Stop the Builder node and write an escalation record; receipt `NOT_READY` | bundle, manifest, receipt, failure trace |
| Output log format check fails | Stop the Builder node and write an escalation record; receipt `NOT_READY` | bundle, manifest, receipt |
| Unpinned or out-of-lock dependency | Reject the output, stop the Builder node and write an escalation record | manifest, bundle, receipt |
| Missing file or hash mismatch | Reject the output, stop the Builder node and write an escalation record | manifest, bundle |
| Trial or install detected | halt the run | runtime record, bundle |
| Blueprint hash changed | halt the run | both hashes |

## Examples

| File | Role |
|---|---|
| [poc_manifest.json](../examples/poc_manifest.json) | valid manifest |
| [poc_artifact_bundle.zip](../examples/poc_artifact_bundle.zip) | valid bundle fixture (unchanged bytes) |
| [build_receipt.json](../examples/build_receipt.json) | valid receipt |
| [build_receipt_forbidden_modules.txt](../examples/build_receipt_forbidden_modules.txt) | forbidden-module list pinned in the check bundle |
| [build_receipt_invalid_ready_with_forbidden_import.json](../examples/build_receipt_invalid_ready_with_forbidden_import.json) | rejected by `build_receipt_ready` |



| [builder_capsule.json](../examples/builder_capsule.json) | declaration |

The valid bundle contains only standard-library fixture scripts. Its `poc_patch.py` and `run_benchmark.py` are placeholders. `poc_patch.py` defines `transform(value)` that returns its input. `run_benchmark.py` defines a `measurement_placeholder()` that returns a metrics object with `None` values and prints it as one JSON line, so it passes the static `output_log_format` check. It is never run. Neither file implements a real intervention.

## Future seams

- Code Mode or multi-file patches: raise `max_patch_files` in the blueprint contract and extend the `files` list rule.
- A richer forbidden list or a sandbox-enforced one: replace the pinned list. The receipt already records its source.
- Automatic repair loops (M2): a new CC wraps the Builder and consumes the failed receipt.
- Other runtimes or containers: add a new bundle type beside `poc_artifact_bundle`.

## M1 placement

The CC page above does not depend on where Builder runs. In M1 the rules below apply.

- Builder consumes the `hypothesis_blueprint`, so ports place it after Hypothesis. Research Benchmark consumes its manifest, so it runs before Benchmark.
- No extra policy entry is needed. The protected binder enforces the order through the port checks `port_type_compatibility` and `dependency_closure` ([D42](../../method/decisions.md#d42)).
