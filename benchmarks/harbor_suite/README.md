# AI4Research benchmarks

Run development benchmarks against AI4Research using Harbor, inspect original
execution evidence and compare selected tasks with a plain Codex baseline.
Harbor schedules and grades trials; AI4Research owns application execution.
Standard application runs use Docker Compose and do not require Harbor.

## Cases and current support

The included [10-case ZIP](assets/AI4Research-Benchmark-Cases-2026-10-26.zip)
contains **69 development variants**, inputs, grading criteria, independent
oracles, oracle tests and a SHA256 manifest. **These are public development
benchmarks, not held-out evaluation data.** The archive README mirrors this
guide; run its commands from the product repository.

| Case | Variants | What it tests |
| --- | ---: | --- |
| `cc01-transfer` | 3 | Extraction, Screening and Evaluation capsule input/output transfer |
| `cc02-binding` | 7 | Version, declaration, admission, standing and port binding |
| `mr01-quality` | 8 | Routing quality, regret and expense against fixed-model controls |
| `mr02-compatibility` | 7 | Capability exclusions, fallback and provider failures |
| `rsi01-improvement` | 5 | Improvement, no gain, overfitting, regression and inconclusive controls |
| `rsi02-containment` | 13 | Access, evidence, budgets, admission and activation boundaries |
| `vf01-mechanical` | 9 | Schema, identity, runtime, dependency and gate checks |
| `vf02-semantic` | 10 | Citations, arithmetic, fairness, limitations and scientific negatives |
| `pipeline01-experiment` | 3 | Incremental index updates versus rebuild through the research workflow |
| `pipeline02-recovery` | 4 | Handoffs, faults, cancellation and interrupted collection |

See [case overview](CASE-OVERVIEW.md) for success criteria and
[validation status](SERIAL-VALIDATION-STATUS.md) for measured coverage. Only
CC01 `evaluate-boundary` and CC02 `valid-pinned` have passed individual live
development trials at the recorded checkpoint. Other variants still require
their documented bindings/resources. The complete suite is not yet validated.

## 1. Set up and extract the cases

Use Python 3.12 and Harbor **0.24.0**. A Linux controller with Docker is
recommended; Windows users can run the controller in WSL. From the repo root:

```sh
uv sync --frozen --no-default-groups --group test --extra codex --extra tui
uv pip install --python .venv/bin/python -r benchmarks/harbor_suite/requirements.txt
. .venv/bin/activate
python -m zipfile -e benchmarks/harbor_suite/assets/AI4Research-Benchmark-Cases-2026-10-26.zip ../ai4r-benchmark-assets
export AI4R_BENCHMARK_CASES_DIR="$(cd ../ai4r-benchmark-assets/AI4Research-Benchmark-Cases-2026-10-26/cases && pwd)"
```

PowerShell extraction/configuration equivalent:

```powershell
Expand-Archive -LiteralPath benchmarks/harbor_suite/assets/AI4Research-Benchmark-Cases-2026-10-26.zip -DestinationPath ../ai4r-benchmark-assets
$env:AI4R_BENCHMARK_CASES_DIR = (Resolve-Path ../ai4r-benchmark-assets/AI4Research-Benchmark-Cases-2026-10-26/cases).Path
```

Use a fresh extraction destination. The [archive checksum](assets/AI4Research-Benchmark-Cases-2026-10-26.zip.sha256)
covers the ZIP; `manifest.json` inventories every payload's size/hash. Keep the
ZIP in Git and extracted assets outside the checkout. `prepare` and `validate`
also accept `--cases-root /absolute/path/to/cases`; explicit root overrides the
environment. Comparison preparation reads the environment too. An invalid
selected root fails without fallback. Use Linux paths inside WSL.

## 2. Check fixtures without inference

```sh
python -B -m benchmarks.harbor_suite.validate --case cc01-transfer --case cc02-binding
python -B -m pytest --noconftest -p tests.benchmark_case_assets -o addopts= tests/unit_tests/harbor_suite tests/unit_tests/harbor_pilot -q
```

Omit the `validate --case` filters to check all ten cases' oracle tests. These
checks make no model calls and do not establish product performance. Asset
checks explicitly skip when no release is installed; a configured but missing
release fails. Independent runtime/transport checks do not require the release.

## 3. Freeze a selected variant

Choose a new absolute bundle destination with an existing parent. Prepare on
the same OS/path namespace that will run Harbor:

```sh
python -B -m benchmarks.harbor_suite.prepare \
  --destination /absolute/new-cc-bundle \
  --case cc01-transfer --variant evaluate-boundary --profile smoke \
  --expected-model gpt-6.1-sol \
  --python-image python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
```

Repeat `--case` to select more cases; omit case/variant filters for all 69
variants. `smoke` freezes one task per variant; `campaign` freezes three repeats.
Jobs use one trial at a time, one attempt and zero automatic retries. Generated
bundles contain pinned inputs, schemas, graders, `task-index.json` and `job.json`.
Never overwrite a frozen bundle or change assets used by a retained run.

## 4. Run a model-free Harbor preflight

Create a separate evidence directory, then a host-only `suite-config.json`
outside the bundle and evidence directories. Substitute actual absolute paths:

```json
{
  "schema": "ai4r-harbor-suite-config:1",
  "bundle_root": "/absolute/new-cc-bundle",
  "output_root": "/absolute/separate-suite-evidence",
  "mode": "preflight"
}
```

```sh
export AI4R_HARBOR_SUITE_CONFIG=/absolute/private/suite-config.json
export PYTHONPATH="$(pwd)"
harbor run --config /absolute/new-cc-bundle/job.json
```

Expected: Harbor exercises task/container/grader wiring without product/model
requests. Trials report `unavailable`, with zero availability/correctness rewards.
This checks wiring, not scientific performance or application readiness.

## 5. Run against AI4Research

Start the app with [Docker Compose operations](../../deploy/m1/OPERATIONS.md),
then follow [Harbor deployment integration](../../deploy/m1/HARBOR-INTEGRATION.md)
for deployment prepare/doctor/stage/run commands and host-only configuration.
The controller, application and inference endpoint may run on separate hardware.
Keep credentials, account profiles and endpoint inventories outside Git, task
bundles and grader containers.

Supported execution depends on the selected module:

- **CC:** prepare actual admitted resources, exact capsule pins, fresh finite
  E3 request/slots, approved profile and scoped credential. Freeze one smoke
  variant with its protected `--evaluation-overlay` and configure the existing
  evaluation sidecar through `evaluation_config`.
- **Pipeline:** use the ordinary E1 runner/deployment bridge with matching
  build/auth/runtime and scientific resources. Model connectivity alone does
  not establish experiment readiness.
- **Verifier:** E2 needs an admitted original source observation, output schema
  and checking assets; live gates also need scheduler capture. The opt-in
  evidence-aware semantic mode remains unsupported in E2 replay.
- **MR/RSI and fault controls:** these need their documented routing, custodian
  or fault-controller bindings. Missing support remains `unavailable`.

Public benchmark status does not mean supplying expected answers to the agent:
stage only selected public inputs, keeping `referee/`, oracles and tests with
the grader. Use fresh run scopes and submit once. Reconcile ambiguous delivery
using the same request ID; preserve failed/unknown attempts and original exports.
See [model recovery](../../deploy/m1/LOCAL-MODEL-RECOVERY.md) before new work after
uncertain inference. Rebuild/requalify bindings when source/runtime changes;
do not reuse another deployment's image IDs, credentials or frozen scripts.

## 6. Inspect results and compare agents

```sh
harbor view /absolute/path/to/jobs --port 5175
python -B -m benchmarks.harbor_suite.report \
  --bundle /absolute/new-cc-bundle \
  --job-results /absolute/path/to/the-job \
  --output /absolute/new-report.json
```

Use a host/address where port 5175 is available. For the shared workstation,
follow [viewer setup](../../deploy/m1/HARBOR-VIEWER.md) to keep app and viewer on
separate loopback addresses at port 5175. `--job-results` points to the concrete
job directory containing trial folders.

Reports separate evidence integrity, execution availability, case correctness
and correctness with the verified requested model. Missing observations retain
null correctness and remain in denominators. There is no weighted quality score
or automatic release-acceptance declaration. Some judgments need human review.

For AI4R versus plain Codex, follow [the comparison protocol](COMPARISONS.md):
freeze identical public assignments, inputs, output schemas, model, effort and
budgets. The current native Codex baseline is constrained to a tool-free turn.
Report shared content/format scores separately from AI4R-specific binding
checks. A single development pair does not establish general improvement.
