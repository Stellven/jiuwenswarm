# Paired native Codex and AI4Research comparisons

This protocol measures the same frozen public assignment through native Codex
(tool-free, one turn) and the AI4Research component interface. It separates
content quality, complete output formatting, framework binding and human
judgment. A single pair is a development observation, not evidence of a general
improvement. Existing protected benchmark criteria and labels remain unchanged.

## Freeze the common assignment

Use `comparison.prepare()` with an explicit public object:

```json
{
  "task": "Original public assignment text or object",
  "inputs": {"PORT": {"ref": {"id": "original-id", "sha256": "64-lowercase-hex"}, "value": {}}},
  "output_contracts": {"PORT": {"contract_id": "original-contract-id", "schema": {"type": "object"}}},
  "limits": {"wall_time_s": 600, "max_model_calls": 20}
}
```

The caller extracts `task` from the prepared source task, and inputs and full
schemas from the original frozen assignment. Declared Refs retain their original
byte digests; this utility does not pretend a reserialized JSON value proves
the original Ref's bytes. The caller must first validate original input/export
custody. `assignment_digest()` binds the exact shared task, values, declared
Refs, output schemas and common limits through canonical UTF-8 JSON.

The generated baseline prompt contains only the public task, public input
Refs/values, full declared output schemas and a generic JSON response instruction.
It contains no CC implementation, capsule declaration/body, example answer,
private oracle, criteria, gold label, AI4Research output or producer verdict.
Private criteria enter only the subsequent offline comparison. Never feed a
complete operator `prepared.json` into the baseline prompt without this explicit
public projection. Unknown top-level assignment fields are rejected.

## Baseline lifecycle and privacy

The existing qualified native host helper executes the baseline with exact
`gpt-6.1-sol`, medium reasoning and tools unavailable. It uses the existing native
host login in place; this utility does not read authentication files or copy
credentials. Preparation and comparison perform no authentication or inference.

Supply a private JSON payload template with exactly these fields:
`model`, `timeout_s`, `codex_executable`, `codex_sha256`,
`account_fingerprint`, `working_directory`. `model` has the existing qualified
host-Codex model policy fields, including its binary/revision qualification.
The template has no `prompt`; the frozen public prompt is supplied by the runner.
The runner pins a canonical digest of this private configuration and refuses
changed inputs, prompt, command pins or excessive budgets before dispatch.

```python
from benchmarks.harbor_suite import comparison

frozen = comparison.prepare(
    common_public_assignment,
    workspace,                       # fresh operator workspace outside jobs
    private_config=private_payload_path,
    control=shared_private_control,    # same root for every baseline launch
    timeout_s=120,
)
# Only this next call performs the explicitly authorized single native call:
result = comparison.run(workspace, private_config=private_payload_path)
```

Use one private control directory for all baseline cases in this comparison.
An exclusive, fsynced workspace `launched.json` prevents replay. Before the
effect, an exclusive, fsynced shared `active.json` prevents concurrent launches
and blocks later workspaces while an outcome remains unknown. There is no
automatic retry. A validated known outcome preserves the original claim as a
`closed-UUID.json` record; an unknown or invalid receipt leaves `active.json`
in place. Process interruption also leaves the claim. Do not remove the pointer,
choose another control root or resubmit to bypass uncertainty. Investigate the
original native turn and retain evidence before operator recovery.

The existing helper owns its native process, identity checks, timeout and
containment. The baseline performs **one** native call with at most **120
seconds**, within the frozen common **600-second / 20-call** case ceiling.
This does not imply that every arm consumed the ceiling. Report actual calls and
observed usage, and match the qualified model/effort and per-call allowance to
the corresponding CC worker. No output token cap is invented for native Codex.

The shared private control contains original helper responses, exact native
version-2 receipts and any private evidence carrier. It must remain outside all
Harbor job roots and public export/viewer paths; a `jobs` path component is
rejected for this private directory. The account fingerprint and raw native
receipt are never fields in the public result. Publish only the workspace's
`public/` directory, not the private control or whole operator workspace.

The public result retains validated model/effort, actual native terminal,
reported input/output tokens, missing cost as `null`, exact original answer
text, a separate strict JSON parse and per-port schema results. Markdown fences,
duplicate JSON keys, missing/extra ports and schema errors are recorded without
answer repair, reformatting or a second call. External schema resources are not
fetched. `native_call_latency_s` includes the owned helper's startup/identity and
call lifecycle; `latency_s` also includes local receipt validation/persistence.
Neither is claimed to be provider-only generation latency.

CLI equivalents, using the qualified Windows Python environment:

```powershell
python -m benchmarks.harbor_suite.comparison prepare --assignment public-assignment.json --workspace baseline-once --private-config private-payload.json --control private-baseline-control --timeout-s 120
python -m benchmarks.harbor_suite.comparison run --workspace baseline-once --private-config private-payload.json
```

## CC content comparison

The AI4Research side must come from original measurement-linked outputs after
normal export/custody validation. Supply a sanitized CC-side JSON object with
`assignment_sha256`, `outputs` (a map of every declared port to its original
decoded value), `status`, observed `usage`, `latency_s`, `effective_model`,
`reasoning_effort` and a separate `binding_assessment`. Do not reconstruct missing
outputs or attach unrelated model-call usage. Missing fields remain unavailable.

```python
paired = comparison.compare(
    common_public_assignment, baseline_result, cc_result,
    variant=criteria['variants']['screen-missing'],
    quality_port='screening_result',
)
```

Both assignment hashes must match. The default evaluator is the same authored
`cc01-transfer/oracle.py:evaluate_content` used by the CC assessment. The
comparison invokes its content checks without requiring CC lineage from the
plain native baseline. The complete schemas of **all** required output ports
are checked separately for both arms. The preselected common task-quality port
can pass deterministic content while an opportunity-card Ref/hash or another
port fails its full format requirement. Such differences remain visible; the
utility does not calculate missing baseline hashes or construct replacement
cards. CC binding success is its own field and never becomes a baseline quality
penalty. Custom authored content evaluators can be passed through the Python API.

```powershell
python -m benchmarks.harbor_suite.comparison compare --assignment public-assignment.json --baseline baseline-once/public/result.json --cc cc-public-result.json --criteria benchmarks/harbor_suite/cases/cc01-transfer/referee/criteria.json --variant screen-missing --quality-port screening_result --output paired-comparison.json
```

Report exact fixture facts and invariants separately from reason quality,
grounding, assumptions and subjective rubric anchors. The latter need blinded
human review when the shared oracle marks them unavailable. Preselect fixtures,
ports, budgets and adjudication rules before reading either answer. Repeat
across multiple independent held-out assignments before making improvement
claims; preserve failed/unavailable pairs in the denominator and report them.

## Verifier comparison and ablation

Freeze a balanced collection of valid and invalid original artifacts using the
existing benchmark's independent labels. Include the benchmark's relevant
format, factual, unit/boundary and provenance violations. Keep gold labels and
the other verifier's decision out of both prompts. Every paired row binds the
two decisions to the **same artifact SHA-256**, same public requirements/facts
and same declared decision schema. Blind producer identity where possible and
balance producer origins so a verifier is not tested only on its own outputs.

Use the same generic baseline runner for the native verifier assignment.
AI4Research verifier decisions must come from the real protected verifier
entrypoint and original records. Distinguish a valid decision from launch,
binding, parsing, transport or timeout failures; unavailable is not rejection.
`verifier_metrics(rows)` accepts rows containing `artifact_sha256`, independent
boolean `valid`, and boolean-or-`None` `native_codex_tool_free` and
`ai4r_verifier` decisions. It reports false accepts (invalid artifacts accepted),
false rejects (valid artifacts rejected), true decisions and unavailable counts.
Observed-decision rates expose their denominators and retain unavailable counts
and the full valid/invalid totals separately. It never creates validity labels.

For a verifier ablation, freeze the producer outputs first. Compare those exact
same bytes through AI4Research with its verifier enabled, with that verifier
disabled through an explicit supported configuration, and through the native
tool-free verifier baseline. Freeze each configuration separately and retain
original decisions, costs and binding records. The disabled configuration is a
separate ablation, not a replacement protected benchmark case or edited label.
Compare the downstream acceptance of correct and incorrect artifacts and
availability as well as quality and cost. Re-generating different producer
answers between verifier arms would confound this ablation.

## Offline validation

`tests/unit_tests/harbor_suite/test_comparison.py` exercises real native receipt
validation with injected fixture responses, exact answer retention, private
receipt isolation, unknown-outcome blocking across workspaces, pin/assignment
mutation rejection, strict parse/schema failures, shared content grading and
verifier confusion accounting. Tests never launch Codex or read authentication.

## Actual Harbor baseline job

`comparison_harbor.py` provides a real custom `NativeCodexBaselineAgent`, not a
result-directory converter. Freeze its task in the Linux/WSL Harbor controller
namespace with `prepare_baseline_task(destination, assignment, variant,
quality_port='screening_result', python_image=digest_pinned_image,
jobs_dir=shared_cc_jobs_root, job_name=unique_job_name)`. This creates a task,
separate protected grader image and serial job config with zero automatic
retries. The variant/oracle exists only in the verifier; the agent receives the
same full public assignment prompt generated by `comparison.make_prompt()`.
Preparation creates no job results and invokes no inference.

The existing Windows wrapper calls `comparison.run()` on its already prepared
native workspace once. Freeze its controller-side routing with:

```python
from benchmarks.harbor_suite.comparison_harbor import freeze_host_config

prepared = freeze_host_config(
    host_only_config_path,
    task_root=bundle_directory / 'task',
    workspace=wsl_path_to_native_workspace,
    command=[wsl_path_to_windows_python, windows_path_to_frozen_wrapper],
    cwd=controller_working_directory,
    public_root=wsl_path_to_native_workspace / 'public',
    private_control=private_observer_control_directory,
    control_files=frozen_executable_wrapper_policy_and_inventory_files,
    control_trees=frozen_implementation_subtrees,
)
actual_harbor_job_config = prepared['job_config']  # bundle/job-host.json
```

Paths are in the controller namespace; arguments to Windows Python keep their
required Windows path spelling. Pin the interpreter, wrapper, private native
payload config, current readiness inventory and every file argument. Pin the
actual implementation/import subtrees used by the wrapper, including the native
helper, receipt validator and comparison runner. Subtree hashes cover all files
except generated Python bytecode/cache files and reject symlinks. Authentication
stores are excluded rather than read or copied. Freeze the final host config
after readiness is confirmed; changed controls need a new reviewed freeze.

`probe_host_config(path)` validates custody without subprocesses or effects.
`job-host.json` pins the host config by SHA-256 in agent kwargs. The agent checks
that hash, controller/source subtrees and exact instruction before dispatch.
It retains an exclusive private dispatch claim before starting the host argv,
and never retries. Host stdout/stderr remain private. The native runner's
separate shared unknown-outcome claim still governs call recovery; cancelling
an observer does not prove provider containment.

Run `job-host.json` through the installed Harbor CLI with `run --config
/absolute/path/to/job-host.json`, from the matching checkout/runtime. Only actual
agent execution plus the independent verifier produces a Harbor trial. Use the
shared CC jobs root so both arms appear in the viewer when Harbor creates their
persisted job structure. No result JSON is synthesized to populate the viewer.

The agent uploads only the native workspace's `public/` directory: result,
original answer and parsed outputs, plus a sanitized host-dispatch record and
finite byte inventory. Unexpected files are rejected. Raw native receipts,
account fingerprints, private policies and host logs are never uploaded.
Harbor usage comes only from sanitized observed usage; missing cost stays null.

The standalone network-disabled grader verifies its frozen controls, rehashes
public bytes, checks assignment identity, reparses the exact original answer,
checks parsed-output equality and all port schemas, and invokes the frozen
shared `cc01.evaluate_content`. Its separate named rewards are
`content_success`, `format_success` and `public_artifact_integrity`. It imposes
no CC binding requirement on plain Codex.

Public artifact consistency does **not independently authenticate provider
provenance**. Original native identity/terminal receipts are validated privately
by the native runner and remain available for operator audit. The isolated
grader explicitly reports native provenance
`independently_verified_by_grader: false`; uploaded reports and self-reported
digests do not become provider authentication.

`test_comparison_harbor.py` validates the installed Harbor job/task models,
mocked one-launch agent dispatch, source/argv custody, public-only upload,
protected grader controls, answer tamper detection and independent content
versus full-format grading. These fixtures launch no model or Docker job.
