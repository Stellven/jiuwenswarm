# AI4Research ten-case Harbor suite

Ten development cases, two each for CC, model routing, RSI, verifier and the
general pipeline. Each case was authored by its own GPT-6.1-Sol subagent.
Harbor owns trial lifecycle and offline verification; the existing AI4Research
runner and protected interfaces retain execution authority.

Keep hardware addresses, endpoint inventories and deployment credentials in
private operator handoffs outside the product repository.

Reusable deployment workflow and `ai4r.py harbor` commands:
[Harbor deployment integration](../../deploy/m1/HARBOR-INTEGRATION.md).

**Case definitions and oracle tests are not product acceptance results.**

For the October 26 continuation checkpoint, read [BENCHMARK-HANDOFF.md](BENCHMARK-HANDOFF.md)
and [the work summary](WORK-SUMMARY-2026-10-26.md). Case assets are distributed
separately from this repository: set `AI4R_BENCHMARK_CASES_DIR` to their extracted `cases/`
directory, or pass `--cases-root` to `prepare`/`validate`. Comparison preparation
uses the environment setting too. Existing frozen bundles remain self-contained;
missing external assets cause an error rather than fallback to local fixtures.
The original case tree is Git-ignored. Asset-dependent unit checks explicitly
skip when no release is installed; an explicitly configured but missing release
fails. Independent transport/runtime tests continue to run without the release.
Keep the environment set when running the full benchmark integration checks.

Prepared finite E3 bindings now support selected CC variants; the evaluation
transfer and valid-pinned binding controls passed live development trials.
Default tasks without their protected overlay remain unavailable. Other module
bindings and protected fault controllers still need qualification. The ordinary
pipeline has an existing-runner bridge and still needs its scientific executor.
See [current serial validation status](SERIAL-VALIDATION-STATUS.md).

| Case | Research or control obligation | Interface | Applicability |
| --- | --- | --- | --- |
| `cc01-transfer` | Exact admitted capsule transfer: extraction, screening and evaluation boundaries | Protected E3 | M1 |
| `cc02-binding` | Version, declaration, admission, standing and port binding | Protected E3 plus owning-validator capture for early rejection | M1 |
| `mr01-quality` | Paired calibration, fixed/routed correctness, regret and full expense across C01–C08 | Frozen routing campaign | M2/M3 progress |
| `mr02-compatibility` | Capability exclusion, router fallback and provider failure without silent switching | Frozen routing campaign and fault capture | M2/M3 progress |
| `rsi01-improvement` | Matched known-good, no-gain, overfit, regression and inconclusive controls | Preapproved custodian job | M2/M3 progress |
| `rsi02-containment` | Protected access, evidence, budgets, admission and activation threats | Custodian job plus independent fault audit | M2/M3 progress |
| `vf01-mechanical` | Schema, stale identity, runtime, forbidden code, environment and gate locking | Protected E2 plus live scheduler capture | M1 |
| `vf02-semantic` | Citations, arithmetic, comparison fairness, limitations and valid scientific negatives | Protected E2 plus live scheduler capture | M1 |
| `pipeline01-experiment` | CPU incremental index update versus full rebuild through the complete research pipeline | Ordinary E1 runner | M1 |
| `pipeline02-recovery` | Fixed workflow handoffs, source fidelity, failure, cancellation and interrupted collection | E1 plus protected frozen fault controller | M1 fast analogue |

The two verifier families define fixtures for all ten Requirements 12.1 / PRD
4.2.9 outcomes. E2 replay cannot establish causal live gate locking or Delivery;
those checks stay unavailable without actual scheduler evidence. Real
long-horizon reliability is outside this fast suite. The case READMEs specify
exact joins, remaining interface gaps and semantic limits.

## Evidence and scoring

Every case contains public research inputs, protected referee material, an
independent stdlib oracle and adversarial unit tests. Missing observations are
`unavailable`; failed and missing attempts stay in campaign denominators. No
model judge is used. Broader semantic judgments require independent human
review. All authored fixtures are development material; neither hidden paths
nor three repeats establish independent held-out custody.

Ordinary-run evidence is independently joined to original terminal status,
collection confirmation, artifact manifest, original ZIP, original Refs and
byte hashes. The isolated E2/E3 decoder uses `EvaluationRecords` and the neutral
schema publication. A producer verdict alone never establishes correctness.
Typed E1 contracts use the protected `contracts/` publication. Output types are
resolved only through each actual invocation's exact subnode contract and its
declared output schemas, with unique neutral-schema matching of the original
Ref bytes. A payload cannot assign itself a record kind.
RSI signature/custodian and routing projections remain blocked until their
documented supported bindings can be validated; arbitrary normalized JSON or
claimed security booleans are not accepted as an import path.

Harbor receives four numeric reward dimensions: evidence integrity, execution
availability, case correctness and correctness with verified baseline model.
The detailed assessment retains null correctness for unavailable evidence,
individual checks and critical violations. Reports separate availability from
correctness among scored trials. There is no weighted aggregate quality score
or automatic M1 release-acceptance declaration.

The requested baseline defaults to `gpt-6.1-sol`. Case-authoring subagent model
selection is separate from the app's effective inference model. The earlier
live pilot used the catalog's `gpt-6-luna` and halted at Intention Compiler on
incomplete JSON; it did not establish baseline suite performance. This suite
does not modify, repair or substitute those scored outputs.

## Validate and prepare

From the repository root, using a Python environment containing Harbor 0.24.0,
pytest, jsonschema and the existing runner's dependencies:

```sh
python -m benchmarks.harbor_suite.validate
python -m pytest --noconftest -p tests.benchmark_case_assets -o addopts= tests/unit_tests/harbor_suite tests/unit_tests/harbor_pilot -q
python -m benchmarks.harbor_suite.prepare \
  --destination /absolute/new-suite-bundle \
  --profile smoke \
  --python-image python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
```

Prepare on the same OS/host path namespace that will run Harbor. For this Windows
host, Docker/Harbor runs in WSL; prepare there with `/mnt/d/...` paths. The bundle
is immutable: use a fresh destination after changes. `smoke` creates one task
per variant and is only a wiring check. `campaign` creates three distinct
variant/repeat tasks, each mapped to one runner attempt; MR calibration/repeats
also have their own stricter case obligations. No automatic retries or parallel
product requests are enabled.

The generator pins source, public input, protected material and grader bytes.
Each task follows Harbor schema 1.4 with a separate no-network verifier. Both
Docker contexts have explicit allowlists. Verifier dependencies are pinned and
installed at image build, with runtime networking disabled. See the
[Harbor task format](https://docs.harborframework.com/tasks/overview).

## Run the preflight wiring check

Create a host-only config outside both bundle and output roots; create the
output directory first:

```json
{
  "schema": "ai4r-harbor-suite-config:1",
  "bundle_root": "/absolute/new-suite-bundle",
  "output_root": "/absolute/separate-suite-evidence",
  "mode": "preflight"
}
```

```sh
export AI4R_HARBOR_SUITE_CONFIG=/absolute/private/suite-config.json
export PYTHONPATH=/absolute/jiuwenswarm-benchmark-suite
harbor run --config /absolute/new-suite-bundle/job.json
```

Expected preflight result: Harbor runs its lifecycle and isolated verifier,
each trial reports `unavailable`, availability and correctness rewards are
zero, and no app/model request is sent. This validates packaging and truthful
blockage, not the product obligations in the table.

For the supported ordinary pipeline experiment, set `mode` to `live` and add
`runner_config`, an absolute reference to the existing host-only
`ai4r-harbor-config:1` config documented in `../harbor_pilot/README.md`. Its bundle
and output roots must match this suite config; use the qualified app build,
scoped token file and only port 5175 for localhost. Credentials must stay
outside all bundle, exported evidence and sandbox paths. All other cases remain
blocked until their specific supported launcher/normalization is implemented.
Do not use ordinary task prompts as isolated CC, routing, verifier or RSI tests.

The shared runner bridge uses a durable single-active pointer, frozen input
pins, reconciliation on resume and bounded cancellation/collection. An
unresolved earlier delivery/execution/collection keeps later dispatch locked.
Harbor's cancellation classification survives the export attempt. No private
evaluation cancellation API is invented.

## Read a campaign

Harbor saves each `verifier/assessment.json` and `verifier/reward.json`. Select
one immutable job result directory when aggregating:

```sh
python -m benchmarks.harbor_suite.report \
  --bundle /absolute/new-suite-bundle \
  --job-results /absolute/new-suite-bundle/harbor-results/ONE_JOB \
  --output /absolute/new-campaign-summary.json
```

Missing trials remain explicit. Duplicate/foreign assessments or a changed
baseline are rejected. The case classification does not convert a blocked
mandatory M1 obligation into an acceptance pass.

Requirements authority: repository `AGENTS.md`, approved
`docs/code/Missions/docs/source/QA/BENCHMARK_REQUIREMENTS.md` v0.12, and maintained
product schemas/architecture. The proposed interface document v0.5 supplies no
new product authority. `AUTHORING.md` defines benchmark-owned metadata only.

## Local validation checkpoint (2026-10-25)

All ten case contracts and 69 variant task packages validated. The 138 oracle
unit tests and 51 shared/pilot unit tests passed; one optional historical-archive
test was skipped. All 69 generated packages loaded through Harbor 0.24.0's actual
task validator, and the job configurations validated.

A Docker preflight selected one variant from each case: ten completed trials,
zero Harbor exceptions, ten expected `unavailable` assessments, null scientific
correctness and zero reward dimensions. It sent no new product requests or model
calls. This confirms task/container/grader wiring and explicit blockage, not
live module performance or M1 acceptance. Full stochastic campaigns were not run.

The local frozen bundle and `VALIDATION_RESULT.json` are saved under
`D:\Codex Development Runs\harbor-suite-20261025`. The bundle contains protected
referee material and must stay outside evaluated product inputs.
