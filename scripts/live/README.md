# Live POC run: build the image, run the clean fixture

These scripts build one image generation, initialize it, and run the clean POC fixture once (Intent to Delivery). They replace the one-off scripts from the October sweep. Nothing here holds a credential or a hard-coded machine path. Roots come from arguments and environment variables.

| Script | Job |
|---|---|
| `deploy_live.py` | `build`, `override`, `initialize`, `doctor` for one generation. Dry run unless `--execute`. Reserves a receipt before it changes anything. |
| `refresh_runner_token.py` | Issues a 24 hour runner grant through the running app and stores it in the runner credential volume. Never prints the token. |
| `run_trap.py` | `install-tool`, `prepare`, `run-cc`, `collect` for the clean fixture. Dry run unless `--execute`. Journals every attempt. |

## Arguments and environment

- `GEN`: generation name, for example `r5h`. You choose it. A used name is refused, so each build is new.
- `IMG`: image tag, for example `ai4r:live-r5h`. Refused if it already exists.
- `OUT`: a working directory outside the repo. Receipts, attempts, sessions and the ledger live below it.
- `FIXTURE`: the clean fixture directory. It holds `cases.json` and `inputs/` (with `data.json` and `scoring-pins.json`). Today that is the `poc-product-public-feasible-05` folder of the October value-discovery output.
- `CHECK_IMAGE`: any existing `ai4r` image, used only for the "profile is fresh" check before a build.
- `AI4R_REPO`: repository root. Default is the checkout that holds these scripts.
- `AI4R_APP_CONTAINER`, `AI4R_BOOTSTRAP_SESSION`, `AI4R_RUNNER_VOLUME`: used by `refresh_runner_token.py`. The defaults are the compose names (`ai4r-local-ai4r-1`, `/var/lib/ai4r-accounts/sessions/reusable-bootstrap.json`, `ai4r-local_runner_credentials`). The bootstrap session path is read inside the app container. No token value is stored in any file here.

## Before you start

1. The checkout is on the branch you mean to test and the working tree has the repaired code. Check that the release pins verify:
   `python deploy/m1/freeze_builder_release.py` prints `Builder and Benchmark release pins verified`.
2. The compose volumes `ai4r-local_state`, `ai4r-local_inputs`, `ai4r-local_results`, `ai4r-local_runner_credentials`, and the holdout in `ai4r-local_private_qa` already exist, and `ai4r-local_inputs` holds the fixture dataset at `datasets/local/data.json`.
3. The Docker engine is up. The model account has quota.

## Commands (PowerShell, from the repo root)

Set the names once.

```powershell
$GEN = 'r5h'; $IMG = 'ai4r:live-r5h'; $OUT = 'D:\ai4r-live'; $CHECK_IMAGE = 'ai4r:live-r5g'
$FIXTURE = 'C:\Users\m50066326\huawei\outputs\cc-value-discovery-2026-10-26\poc-product-public-feasible-05'
$common = @('--generation', $GEN, '--image-tag', $IMG, '--out', $OUT, '--fixture', $FIXTURE)
```

Review the whole plan first. These print only.

```powershell
python scripts/live/deploy_live.py plan @common --check-image $CHECK_IMAGE
```

Build the image `r5h`. This is the step that needs memory and time.

```powershell
python scripts/live/deploy_live.py build @common --check-image $CHECK_IMAGE --execute
```

Write the compose override, then capture the profile and initialize the app. Initialize recreates the app on `127.0.0.1:5175`.

```powershell
python scripts/live/deploy_live.py override   @common --execute
python scripts/live/deploy_live.py initialize @common --execute
```

Read `$OUT\receipts-r5h\initialize.json`. It must say `initialized` with no diagnostics. Take the build id from `$OUT\receipts-r5h\build.json`.

```powershell
$BUILD = (Get-Content "$OUT\receipts-$GEN\build.json" | ConvertFrom-Json).build_id
```

Issue the runner grant. The first grant right after initialize can return 401 or 502 because the app is still starting. Run it again once the app answers.

```powershell
python scripts/live/refresh_runner_token.py --image-tag $IMG
```

Create a fresh ledger (once per ledger), install the intake tool into the results volume (once per results volume), then prepare. Prepare uploads the public inputs and makes no model call.

```powershell
python -B -m benchmarks.harbor_suite.value_schedule init --ledger "$OUT\ledgers\$GEN.sqlite3"
$run = @('--out', $OUT, '--fixture', $FIXTURE, '--ledger', "$OUT\ledgers\$GEN.sqlite3", '--expected-build', $BUILD)
python scripts/live/run_trap.py install-tool @run --execute
$PREP = "trap-$GEN-" + [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
python scripts/live/run_trap.py prepare @run --attempt-id $PREP --execute
```

Run the CC arm once, then collect. `run-cc` is the live run. It spends model calls (about 13 for a clean pass). It cannot be replayed: a second `run-cc` for the same `$PREP` is refused.

```powershell
python scripts/live/run_trap.py run-cc  @run --prepared $PREP --execute
python scripts/live/run_trap.py collect @run --prepared $PREP --execute
```

The records land in `$OUT\sessions\$PREP\collection\cc\`. The stop reason of a halted node is in `runs\*\run_record.json` and in the `protected-invocation-stop` record, field `executor_fault`. Run status also lists it in `reasons`.

Every action also accepts no `--execute`, which prints the exact commands and writes only the attempt journal. Use `python scripts/live/run_trap.py plan @run` for the whole set.

## What a pass looks like

All seven stages reach `Completed`: intention_compiler, search, screening, hypothesis, builder, benchmark, evaluation, delivery. If a node stops, the stop reason names the real cause; it must not read as a bare `integrity_fault`.
