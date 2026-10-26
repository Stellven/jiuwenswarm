# Two-case Harbor compatibility pilot

This pilot packages the existing CPU classification and paper-summary demos for
Harbor **0.24.0**. It keeps AI4Research's supported runner/client, request
reconciliation, collection manifests, and product gates.

Two execution modes are deliberately separate:

- **Live:** `adapter:AI4ResearchAgent` calls the existing sequential runner on
  the **Harbor host**, which talks to an explicitly pinned AI4Research HTTP
  origin. The Docker agent environment carries exported evidence only. This
  host placement is a development compatibility experiment; it differs from
  the normal two-container runner quick start in
  [OPERATIONS.md](../../deploy/m1/OPERATIONS.md).
- **Historical replay:** `replay:HistoricalReplayAgent` transports frozen
  October 23 exports into Harbor and its separate grading container. It makes
  no app/model call and proves no fresh execution, cancellation, or recovery.

These are development demonstrations, not M1 acceptance or held-out scores.

## Install and prepare

Use Python 3.12+ for the pinned Harbor release and a working local Docker engine
with Compose. The commands below use a Linux/WSL host. Prepare and run on the
same host so generated absolute paths are valid; do not reuse Windows paths
unchanged inside WSL.

```sh
cd "/absolute/path/to/jiuwenswarm-benchmark-suite"
export PYTHONPATH="/absolute/path/to/jiuwenswarm-benchmark-suite"
export PILOT_ROOT="/absolute/path/to/new-pilot"
mkdir -p "$PILOT_ROOT"
python3.12 -m venv "$PILOT_ROOT/runtime"
export PILOT_PY="$PILOT_ROOT/runtime/bin/python"
"$PILOT_PY" -m pip install 'harbor==0.24.0'
```

The custom adapters import from this checkout through `PYTHONPATH`; installing
the full application into Harbor's environment is unnecessary. Retain the
installed dependency versions with the run records.

`--sample-root` expects the supplied layout:

```text
demo-benchmarks-20261023/
  cases/demos-20261023/case1-cpu.json
  cases/demos-20261023/case3-paper.json
  inputs/demos-20261023/case1-cpu/{train.csv,test.csv,data-description.md}
  inputs/demos-20261023/case3-paper/chunk-recomputation-2610.31019.pdf
```

Provide independently controlled criteria in a separate `--criteria-root`:
`cpu.json`, `paper.json`, and the exact CPU labels file referenced by
`cpu.labels_path`. Criteria use `schema: "ai4r-harbor-criteria:1"`,
`case_id: "cpu"` or `"paper"`, and `allowed_custody: ["live"]` for a live
pilot. CPU criteria can specify `labels_path`, `prediction_path`, `id_column`,
`label_column`, `prediction_column`, and an optional frozen
`baseline_accuracy`/`min_accuracy_gain`. Paper criteria specify `artifact_path`
and `checks: [{"id": "...", "patterns": ["reviewer-defined regex"]}]`.
The default prediction columns are `id,label`. A reference baseline is not
evidence that the app executed that baseline.

```sh
"$PILOT_PY" -m benchmarks.harbor_pilot.prepare \
  --sample-root /absolute/path/to/demo-benchmarks-20261023 \
  --criteria-root /absolute/path/to/protected-criteria \
  --destination "$PILOT_ROOT/bundle" \
  --python-image 'python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258' \
  --harbor-version 0.24.0
```

Preparation refuses an existing bundle, copies only declared public inputs,
removes old provenance/setup commands, and hashes the selected bytes. It emits
`cases/{cpu,paper}.json`, `inputs/`, two `tasks/`, `job.json`, and
`bundle-manifest.json`. Fresh live inventory comes from the bridge.

**The bundle contains protected grading material. Never mount or upload the
whole bundle root into AI4Research or an evaluated agent environment.** Each
task's `environment/` build context contains only the artifact-transport image
definition. Protected criteria, labels, and `grade.py` are copied only into
that task's separate `tests/` image. Both Harbor environments have no network.
The independent grader receives only declared `/app/ai4r-evidence` exports and
has no product-control credential.

## Live run

Start a supported app separately using the existing deployment runbook. The
user must complete model authentication. Provision a scoped runner credential
through the supported issuer; never copy a browser session token. Record the
actual expected app build, not this checkout's commit as a substitute.

Create a host-only config outside the task bundle and output root:

```json
{
  "schema": "ai4r-harbor-config:1",
  "bundle_root": "/absolute/path/to/new-pilot/bundle",
  "output_root": "/absolute/path/to/new-pilot/live",
  "endpoint": "http://127.0.0.1:5175",
  "token_file": "/absolute/host-private/runner-token",
  "expected_build": "ACTUAL_APP_BUILD_ID",
  "cancel_timeout_s": 45
}
```

`http_authority` is optional when a supported virtual-host connection requires
it. The credential file must be outside both bundle and output roots.

```sh
mkdir -p "$PILOT_ROOT/live"
export AI4R_HARBOR_CONFIG=/absolute/host-private/harbor-live.json
"$PILOT_PY" -m jiuwenswarm.research_sidecar doctor \
  --cases "$PILOT_ROOT/bundle/cases/paper.json" \
  --inputs "$PILOT_ROOT/bundle/inputs" --output "$PILOT_ROOT/live" \
  --endpoint http://127.0.0.1:5175 \
  --token-file /absolute/host-private/runner-token \
  --expected-build ACTUAL_APP_BUILD_ID --json
"$PILOT_ROOT/runtime/bin/harbor" run -c "$PILOT_ROOT/bundle/job.json"
```

The job explicitly uses one concurrent trial, one attempt per task, no retries,
and `environment.delete=false`. Outputs remain on the host. In Harbor 0.24's
Docker backend, this still removes trial containers with Compose `down`, while
retaining images and volumes. It is not a container-retention guarantee.
Inspect and confirm retained evidence; no global Docker cleanup is part of the pilot.

## Recovery and cancellation

`bridge.py` exposes `Config.load()` and async `run_trial()`; it is not a CLI.
The adapter derives its campaign identity from the case and durable Harbor
trial log directory. Re-enter the **same trial/log identity** to resume that
attempt. Creating fresh trial IDs is a new attempt, not recovery.

The bridge pins case/input/build identities and uses an OS lock plus durable
`.harbor-pilot-active.json`. An uncertain request, unconfirmed cancellation, or
incomplete collection keeps new dispatch locked. Cancellation calls the
existing runner's cancel/reconcile/collection path with a bounded containment
window; an unresolved app request remains explicitly unresolved.

The original runner can also inspect or recover its existing campaign:

```sh
"$PILOT_PY" -m jiuwenswarm.research_sidecar status \
  --campaign-dir /absolute/path/to/live/harbor-EXISTING_ID --json
"$PILOT_PY" -m jiuwenswarm.research_sidecar resume \
  --campaign-dir /absolute/path/to/live/harbor-EXISTING_ID \
  --endpoint http://127.0.0.1:5175 \
  --token-file /absolute/host-private/runner-token \
  --expected-build ACTUAL_APP_BUILD_ID --json
```

Use the same command with `cancel` for an explicit cancellation. Do not delete
active pointers or replace request IDs to escape a block. After manual runner
recovery, re-enter the same Harbor trial to refresh its bridge receipt and
export. If Harbor cannot retain that identity, retain the existing campaign
and resolve it before scheduling a deliberate new attempt.

## Historical replay

Use complete historical exports, including both runs' `originals.zip` bytes;
the smaller copied folder without archives cannot satisfy this check. Pin the
source and its archived inventory outside the original evidence directory:

```sh
"$PILOT_PY" -m benchmarks.harbor_pilot.replay freeze \
  --source /absolute/path/to/complete-historical-campaign \
  --inventory /absolute/path/to/archived-host-preflight.json \
  --destination "$PILOT_ROOT/replay.json"
export AI4R_HARBOR_REPLAY_CONFIG="$PILOT_ROOT/replay.json"
```

Prepare a separate replay bundle whose protected criteria explicitly allow
`historical_replay`. Copy its generated job config to a new `job-replay.json`,
give it a new `job_name`, and replace the agent entry with:

```json
{"import_path": "benchmarks.harbor_pilot.replay:HistoricalReplayAgent"}
```

Run that config with `harbor run -c /absolute/path/to/job-replay.json`. The
source and copied bytes are checked against frozen hashes. Historical custody
is preserved in receipts and results; changing the adapter does not turn an
old run into a live one.

## Read the results

Each export includes `pilot-receipt.json`: case/campaign/request/app-run IDs,
execution and collection states, custody, terminal/evidence flags, recovery
and cancellation observations, an inventory reference, and any error category.
The grader writes `assessment.json` and three labeled rewards:

| Reward | Meaning |
| --- | --- |
| `evidence_integrity` | Required terminal records, collection joins, original bytes, and identities validated. |
| `live_integration` | Validated evidence has live custody; always zero for replay. |
| `execution_completed` | The selected product attempt reached `completed`; a properly retained halt is zero. |

None is a scientific task-success score. CPU accuracy can be recomputed only
when actual predictions exist. Paper checks establish limited number/reference
presence; interpretation and source fidelity require independent human review.
A retained CPU halt may therefore earn evidence integrity without completion.

This workstation's October 25 working outputs are under
`D:\Codex Development Runs\harbor-pilot-20261025` (WSL:
`/mnt/d/Codex Development Runs/harbor-pilot-20261025`). Both real Harbor/Docker
replay trials completed without framework errors. CPU returned integrity 1,
live 0, completion 0; paper returned integrity 1, live 0, completion 1.
The separate Docker verifier rejected a deliberately missing original archive.
See `PILOT_RESULT.json` and the original Harbor results in that directory.
These replays do not establish fresh AI4Research execution. Human scientific
assessment remains separate from the compatibility rewards.

## Live pilot result — October 25

The two fresh live trials ran sequentially against installed build
`689b35177b113cb6ea18ef13986e7309b4d0e26340383a8cc17a12e5de013fc2`.
The signed-in account did not expose the requested `gpt-6.1-sol` baseline;
`gpt-6-luna` was explicitly selected before submission and independently
observed in both actual model calls. This is a declared compatibility-pilot
configuration, not the required baseline-model comparison.

| Case | Product result | Original artifacts | Integrity / live / completed |
| --- | --- | ---: | --- |
| Paper | Halted at Intention Compiler | 3,184 | 1 / 1 / 0 |
| CPU | Halted at Intention Compiler | 4,252 | 1 / 1 / 0 |

Both native final assistant messages contained incomplete JSON, missing the
last root-closing brace. Their native output deltas and final text agreed;
the malformed text preceded product output extraction and Harbor collection.
The product rejected it as `invalid_output` and did not release the compiler.
No artifact was repaired or task automatically retried. A diagnostic appended
brace permits JSON parsing but does not establish schema validity.

Both failed attempts have complete, confirmed, independently checked exports.
CPU submission occurred after paper collection confirmation. Harbor reported
no framework exceptions; neither research task completed, and both scientific
assessments remain unscored. Evidence references and native packet hashes are
in the external `PILOT_RESULT.json`; actual trial results are under
`harbor-live-results/ai4r-harbor-live-20261025/`.

The pilot supports retaining Harbor as a thin control/evidence wrapper. A
successful fresh research workflow, required baseline-model access, and any
broader benchmark acceptance remain unproven. The native catalogue used local
development builtins; model-based checking-asset qualification was not run.
