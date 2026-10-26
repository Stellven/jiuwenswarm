# Benchmark operator handoff

Checkpoint: October 26, 2026, America/Toronto. Read this before submitting a new trial.

Integration note: the merge candidate is based on updated `ai4r_M1` commit
`ab0d9c7fe`, with Docker Compose retained for standard runs and Harbor optional
for benchmarks. The installed app and retained live results below belong to
the original workstation generation; the merge candidate has not replaced that
deployment. Requalify fresh bindings/runtime/image identities before new live
runs. The updated branch includes upstream Builder/runtime and opt-in verifier
work; evidence-aware semantic review remains unsupported in E2 replay. Case
assets and hardware-specific inventories stay outside the product merge.

## Scope and current result

Continue `D:/Codex Development Runs/jiuwenswarm-benchmark-suite`, branch `ai4r_M1`.
This checkout has substantial uncommitted/untracked integration work. A fresh
clone of the branch does not contain all of it. Do not reset or clean the checkout.
Run one selected variant at a time; leave RSI and MR files unchanged and do not
launch their cases. Use GPT-6.1-Sol/medium through the existing host Codex login.
There is no complete passing research pipeline, full case, or suite result yet.

| Case | Evidence so far | Next requirement |
| --- | --- | --- |
| CC01 transfer | `evaluate-boundary` passed live using implemented `research.evaluation m1-5` | Extraction needs a local-document connector; earlier `screen-missing` remains unscored |
| CC02 binding | `valid-pinned` passed using implemented `research.screening m1-4`; human scientific review remains required | Six controls remain; need attributable owning-validator rejection receipts, complete dispatch census and real standing/version controls |
| VF01 mechanical | Not run; prerequisites inspected | Adopted lookup-cache schema, admitted producer/checking assets and authentic source invocation |
| VF02 semantic | Not run; prerequisites inspected | Admitted output/source/checking closure, independent label approval, actual scheduler capture |
| Pipeline01 experiment | Existing ordinary-run bridge; not ready | Scientific CPU executor/Builder and restricted-runtime qualification |
| Pipeline02 recovery | Not run | Protected fault controller and authenticated interruption/cancellation audit |
| RSI01/02, MR01/02 | Excluded by user | Keep unchanged; not part of the current validation queue |

Missing verifier and pipeline support belongs to AI4R's runtime/admission path.
Harbor schedules and grades trials; installing Harbor does not implement those
product capabilities. Never bypass readiness, admission, schemas or budgets.

The matched Evaluation comparison used the same public assignment, schemas,
GPT-6.1-Sol/medium and one call within 120 seconds. AI4R passed format/content;
plain Codex passed format but incorrectly marked complete measurements missing.
Tokens: AI4R 19,704 input / 824 output; plain Codex 16,726 / 937. This is one
development pair, not evidence of general improvement or comparable cost/latency.

## Retained results and historical attempts

Operational root: `D:/Codex Development Runs/harbor-deployment-20261025/`.

- `cc-evaluation-recovered-run-20261026/`: `RESULT.json`, `PAIRED.md`,
  `paired-verification.json`; 295 original CC files and 17 baseline files retained.
- `cc-binding-run-20261026/`: original request and first observer's HTTP 502.
- `cc-binding-collection-20261026/`: GET-only recovery, `RESULT.json`,
  `retained-original-manifest.json`; 337 original files retained.
- `model-recovery-20261026/`: containment observations, acknowledgements,
  qualification and foreground process records.
- `final-app-update-20261026/`: `DEPLOYMENT-RESULT.json`, `FINAL-VERIFICATION.json`
  and deployed source/image captures.

Harbor jobs: `ai4r-cc-evaluation-boundary-recovered-20261026`,
`plain-codex-evaluation-boundary-recovered-20261026`,
`ai4r-cc-binding-valid-pinned-collected-20261026`.
Original WSL jobs live under
`/home/s50066325/ai4r-codex-cc-harbor-20261025/jobs`.
The first CC02 observer timed out at 30 seconds while the original request
completed in about 32 seconds. Its later passing collection used GET only:
two observations of one scientific request, not two trials.

Keep old failed/unknown attempts and their denominators. Do not rerun frozen
`run_*.py`, `launch_*.py` or `capture_*.py` scripts: they have fixed request IDs,
exclusive-create outputs and source pins. Use them only as templates for a new
scope. Source changes require newly pinned controls and bundles.

## Last verified deployment; recheck before use

- App: `http://127.0.0.1:5175/chat/new`; Bench Hub: `http://127.0.0.2:5175/`.
  Both use the authorized local port 5175. The hub last showed 14 actual jobs.
- Docker project `ai4r-codex-text-20261025`; private network
  `ai4r-codex-text-20261025_private`.
- App image `sha256:f31901c0b25c0856399b17c56bc50f9971d6bc86a7e07e00d57418cd0d7ab9ba`.
- Receiver image `sha256:5bbdf34eda2beedaf0e8e9c05b70536cb6af78171b105cd6eb08b7c92c0c7a48`.
- Build `0afa21a87bc7999e8fb97f550dea10546ae34e64b30b80aeb7cbfa67aa3fcc74`.
- Main profile: `harbor-deployment-20261025/codex-text-run/corrected/operator.json`
  relative to the workspace. Ordinary runner credentials require native refresh.
- Last state: no active runs, unfinished claims or unreleased leases; model ledger
  seven completed requests plus two preserved, acknowledged historical unknowns.
- Current bootstrap is the spent CC02 E3 scope. A new trial needs a fresh finite
  profile, request ID, runtime slots, output namespace and scoped grant. A scoped
  evaluation grant is separate from host account login.

Runtime: WSL `Ubuntu-24.04`, persistent Python
`/mnt/d/Codex Development Runs/.harbor-pilot-runtime/linux-venv/bin/python`.
The old `/tmp/ai4r-harbor-pilot-20261025` runtime is gone. Windows offline Python:
`D:/Codex Development Runs/.harbor-pilot-runtime/venv/Scripts/python.exe`.
Docker's Windows executable is under
`C:/Users/s50066325/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe`.
The established owned WSL launcher is
`harbor-deployment-20261025/codex-text-run/wsl_entry.py` under the workspace.

Private relay state belongs to the operator under
`/home/s50066325/.local/share/ai4r/ai4r-codex-text-20261025/model-control/`.
Do not read/copy authentication caches or put credentials in task bundles, ZIPs,
grading containers or reports. Do not delete the unknown ledger/guard or change
an old request ID to evade it. Existing acknowledgements permit distinct work
after local containment; they do not prove the provider's old outcome. Fresh
unknowns block again. Recheck process ownership and drainage rather than using
historical PID numbers. See [recovery procedure](../../deploy/m1/LOCAL-MODEL-RECOVERY.md).

## External test cases and merge layout

The portable release is outside the product checkout:
`D:/Codex Development Runs/benchmark-handoff-2026-10-26/AI4Research-Benchmark-Cases-2026-10-26.zip`.
It contains all ten authored cases / 69 development variants, public fixtures,
protected criteria, oracles and oracle tests, plus a byte-hash manifest.
See the adjacent `INSTALL-CASE-ASSETS.md` for extraction and verification.

Recommended asset root:
`D:/Codex Development Runs/benchmark-assets/AI4Research-Benchmark-Cases-2026-10-26/cases`.
Keep adapters, runtime/deployment integration and their unit tests in the product
repo. Keep versioned case assets in a separate private asset repository or release.
Existing case copies have deliberately not been deleted or moved. Before merge,
switch active consumers/CI to the external release and verify them, then exclude
the duplicate `benchmarks/harbor_suite/cases/` tree from the merge. Preserve all
historical frozen bundles and their original paths/bytes.

`prepare` and `validate` accept `--cases-root`; shared loaders and comparison
preparation also honor `AI4R_BENCHMARK_CASES_DIR`. Explicit root takes precedence,
then environment, then the legacy repository default. An invalid external root
fails rather than silently falling back. Set the environment for comparison tools
as well; the prepare CLI's argument applies only to that invocation. Frozen
bundles retain pinned local assets and ignore later root changes. Historical
operator scripts with literal repo paths need fresh replacements for new runs.

Only the selected inventoried public inputs may go to AI4R or a baseline model.
The complete asset pack and frozen bundle contain protected grading material;
keep them with the benchmark controller/referee.

## Safe starting commands: offline, no model calls

From the repo root in a WSL shell under the established operator identity:

```sh
export AI4R_BENCHMARK_CASES_DIR='/mnt/d/Codex Development Runs/benchmark-assets/AI4Research-Benchmark-Cases-2026-10-26/cases'
PY='/mnt/d/Codex Development Runs/.harbor-pilot-runtime/linux-venv/bin/python'
"$PY" -B -m benchmarks.harbor_suite.validate \
  --case cc01-transfer --case cc02-binding \
  --case vf01-mechanical --case vf02-semantic \
  --case pipeline01-experiment --case pipeline02-recovery
"$PY" -B -m benchmarks.harbor_suite.prepare \
  --destination '/mnt/d/Codex Development Runs/new-unique-cc-bundle' \
  --case cc01-transfer --variant evaluate-boundary --profile smoke \
  --python-image python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
```

Use a nonexistent destination with an existing parent. Preparation without the
protected evaluation overlay checks packaging only; it cannot launch a qualified
live CC trial. Oracle unit tests validate grading logic, not product performance.
Prepare on the same OS/path namespace where Harbor will run.

## Continuing live validation

1. Check current source/profile/build/image identities, app drainage, Docker/WSL,
   memory and relay ownership. Use the private non-generating relay probe first.
   Do not assume a working account makes ordinary experiment readiness true.
2. Choose one variant with satisfiable prerequisites. The smallest verifier
   candidate is VF01 `missing-field`: adopt the exact five-field output schema,
   admit/calibrate/activate the producer and checking assets through native
   LibraryService, then execute authentic `AdmittedMeasurementResources` source
   preparation/execution. Preserve exact emitted fixture bytes as ProducedArtifact.
   Capture the canonical invocation before schema rejection; Tier 1 should reject
   and Tier 2 skip. This path needs no inference once its assets exist. Do not
   synthesize an observation from ordinary E1/E3 records or dynamically admit an
   arbitrary schema. Other verifier controls may still need runtime controllers.
3. For a CC trial, use `research.evaluation_preparation` with real admitted
   resource handles and exact installed capsule pins. Freeze public input
   migration receipts, approved profile, startup Refs, original snapshot and E3
   request. Use native scoped grant issuance; never copy a spent grant.
4. Freeze one fresh smoke variant with its exact protected `--evaluation-overlay`.
   Pin new control sources and use the sidecar's existing `Runner.execute_evaluation`.
   Keep concurrency one, one attempt, zero automatic retries, and authored budgets.
5. Submit once. On transport ambiguity reconcile GET using the SAME request ID;
   never re-POST to discover whether execution happened. Uncertain model outcomes
   require the documented operator recovery procedure before any distinct work.
6. Retain original EvaluationRecords, archive, original Refs, schema publication,
   snapshots and byte hashes. For completed execution with a failed observer use
   `research_sidecar.evaluation_collection` in a new collection namespace. It
   performs GET only and preserves historical records. Grade independently, then
   update [serial validation status](SERIAL-VALIDATION-STATUS.md).

Full procedural references: [deployment integration](../../deploy/m1/HARBOR-INTEGRATION.md),
[host account route](../../deploy/m1/HOST-CODEX-INTEGRATION.md),
[comparison rules](COMPARISONS.md), [viewer](../../deploy/m1/HARBOR-VIEWER.md).
Independent pre-admission calibration remains NOT_RUN; no M1 acceptance claim.
