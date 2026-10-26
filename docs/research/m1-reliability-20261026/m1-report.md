# M1 reliability and readiness status — October 26, 2026

## Status

This note records bounded M1 implementation and verification evidence from the
current integration checkout. Controlled tests exercise mechanics with fixed
responses; they are not live model-quality evidence. No live model calls or ML
acceptance runs were made for this work. No new deployment or verification
image was created.

**Final current-release selection: 319 passed, zero failures/errors/skips.**
The retained run has `source_changes: []` and exit 0. Its source is
`a138e435fe0f6e33a0684ac0458404e3d3d1700b`; the pinned verification image is
`sha256:09979a044c9eace8e3ef17cd142eb26a27306e14ea80939c0628356eaca2e97a`.
An independent Git archive of that commit passed 28 focused tests and the
Planner release-pin check. These selections overlap and are not added together.
[Exact summary, commands and evidence](https://github.com/Stellven/jiuwenswarm/blob/ab0d9c7fe8ceadf45c61d04e94e2dd9b44b867a7/docs/capsules/verification-20261026/ml-readiness/summary.json).

The user requested publication of working code and a status report before the
live campaign was complete. This is a software-verified checkpoint with opt-in
pilot functionality, not live scientific acceptance. The running app was not
replaced, and prior sign-in, frozen runs and captured configurations were retained.

## Findings and fixes

- The utility DAG exposed a real budget mismatch: the old 60-second node
  ceiling could be fully reserved by the worker and independent reviewer, so
  dispatch failed before a utility worker ran. New immutable releases give the
  worker and independent review bounded room (30 seconds for pure workers,
  90-second aggregate node ceiling; Generalist retains its 180-second worker
  ceiling and one-call bound). The 60-second negative case still fails closed.
- The four active utility/generalist candidates now have explicit v2 releases
  with the required blocking `result_schema` check ID. Their v1 manifests are
  preserved under `capsule_extensions/history/v1/`, with reused runtime worker/check dependencies
  hash-pinned separately by v2. Active candidates are `utility.table_normalize
  m1-2`, `utility.calculate m1-2`, `utility.markdown_report m1-2`, and
  `research.generalist m1-2`.
- `utility.summary_to_packet m1-1` is a deterministic, checked adapter from
  paper-summary v1 to work-packet v1. It retains summary, brief, document and
  source references and marks the packet low-trust. `utility.packet_report
  m1-1` remains a separate full-packet formatter. These are not universal
  schema coercion paths.
- Archived v1 source bytes remain available for exact inspection. Startup may
  restore a historical handler only when its existing exact association passes
  current independent admission policy. The archived utility v1 checks use
  `packet_schema`; current policy requires `<output-port>_schema` (for example,
  `result_schema`). That old mismatch is not grandfathered. Such a release
  remains unavailable under current policy unless independently requalified.
- The opt-in evidence-aware per-output review accepts only its bounded, selected task
  source projection and passing Tier 1 check IDs. It does not traverse arbitrary
  references or disclose worker conversations, expected answers or private
  labels. Existing output-only reviewer pins remain unchanged. See
  [the evidence-aware review amendment](https://github.com/Stellven/jiuwenswarm/blob/ab0d9c7fe8ceadf45c61d04e94e2dd9b44b867a7/docs/research/evidence-aware-review-amendment.md).
  E2 replay currently rejects the new v2 profile before a model call; historical
  output-only E2 review remains supported. A v2 replay payload is not silently
  treated as an output-only assessment.
- The ML task-capture helper creates synthetic public signal/no-signal tasks
  and a root-private holdout. Capturing the profile re-executes under permanent
  UID/GID 10001 with no supplementary groups; this was verified in the pinned
  Docker image. Task preparation/capture creates no admission, readiness or
  result. Real science still requires active Builder/Benchmark admissions and
  the protected science runtime.

## Controlled verification

Focused runs on the existing `ai4r-verify:20261025` image passed:

| Scope | Result |
| --- | ---: |
| Actual summary-adapter and 3-stage utility DAG composition | 5 passed |
| Capability extension admission and archived-manifest checks | 7 passed |
| Utility/capsule worker suites | 46 passed |
| ML helper, evaluation-pilot, pilot-budget and subscription-budget selection | 12 passed |
| Check admission, gate, pilot-budget and subscription-budget selection | 26 passed |

These selections overlap; do not add them into a suite total.

The first retained full-check preflight is **not a pass**. At
`C:/Temp/ai4r-ml-readiness-preflight-20261026/repeat-01/`, it ran 257 tests:
254 passed, 3 failed, 0 skipped. It ended `source_changed` (exit 2) because
five source files changed during the run. The failures were three
`test_evaluation_replay.py` cases that returned `entry_point_unavailable`:

- `test_failed_independent_review_retains_actual_model_call_and_once_state`
  expected `provider_error` and received `entry_point_unavailable`.
- `test_actual_verifier_rejection_halts_valid_replay_with_call_evidence`
  expected Tier 2 `FAIL` and received `NOT_RUN`.
- `test_eligible_replay_sends_only_declaration_and_output_to_actual_reviewer`
  received Tier 1 `PASS`, Tier 2 `NOT_RUN`, reason `entry_point_unavailable`.

A second preflight ran 330 tests (328 passed, 2 failed) while source was still
changing. It is also not a clean pass. Both failures are in
`test_finite_startup.py`: native finite readiness and exact root-peer gateway
attachment. A pristine Git archive of parent `e1ca360c`, using the same image,
reproduced both failures (11 passed, 2 failed). Their evidence is retained as a
historical regression limit; that file is outside the selected current-release
launcher groups, not marked xfail or silently treated as passing.

One check was stopped before completion to normalize eight changed Python/JSON
files to LF before committing. Two fresh-archive launch attempts failed before
pytest ran (a mountpoint, then wrong Python); their logs are retained separately.
The final 319-test run and successful fresh-archive check followed those repairs.
All original failures and interruptions remain under the linked evidence folder.

## Reproduction

From the repository root in PowerShell, use a new output directory for every
run. The launcher uses the named existing image and retains exact arguments,
image identity, source hashes, pytest output and JUnit results.

```powershell
./deploy/m1/check-capsules.ps1 -Group ml-readiness -Image ai4r-verify:20261025 -Output C:/Temp/ai4r-ml-readiness-20261026
./deploy/m1/check-capsules.ps1 -Group all -Image ai4r-verify:20261025 -Output C:/Temp/ai4r-all-20261026
```

The launcher disables networking, mounts the source read-only, filters only
the pinned SDK dependency's `SyntaxWarning`, and fails verification if source
changes while tests run. It makes no live model calls. See the
[evaluation-pilot CLI guide](https://github.com/Stellven/jiuwenswarm/blob/ab0d9c7fe8ceadf45c61d04e94e2dd9b44b867a7/docs/research/evaluation-pilot-cli.md) for the separate Docker
commands that author exact E2/E3 request templates. Authoring a template does
not submit it or create a gate decision.

## PRD V10 / user-story evidence

The table separates exercised mechanics from the remaining end-user or live
science claim. `PASS` here means controlled implementation evidence only.

| Story | Mechanism exercised | Still unverified |
| --- | --- | --- |
| US09 — proof of concept | Builder packaging, bounded outputs and independent checks have controlled coverage. | No accepted live ML proof of concept or external scientific task. |
| US10 — baseline comparison | Baseline/treatment protocol, fixed repeats, prediction-only output and trusted host scoring have controlled tests. | No completed live baseline/treatment measurement. |
| US11 — understand scientific outcome | Scoring and evaluation receipt paths are covered by controlled tests. | No live measurement-backed conclusion or validated scientific interpretation. |
| US13 — inspect a halted run | Interrupted-attempt custody, cancellation, recovery and status projections have controlled coverage. | No user study of whether a researcher can diagnose and correct a production halt. |
| US15 — final research report | A PDF summary/delivery run and report retrieval were exercised; utility report generation is controlled-tested. | The PDF demonstration did not establish independent experimental measurements; no final live scientific report is established. |
| US16 — retrieve experiment evidence | A completed run archive was retrieved; export/custody mechanics have controlled coverage. | No reproducible live ML experiment package or scientific raw evidence exists yet. |
| US17 — revisit a previous run | Read-only status and recovery of an existing completed run were exercised without repeating calls. | Broader user-level history review and production reuse are not established by that one recovery. |

The historical PDF workflow and authenticated recovery are described in
[the M1 execution note](https://github.com/Stellven/jiuwenswarm/blob/ab0d9c7fe8ceadf45c61d04e94e2dd9b44b867a7/docs/capsules/m1-local-process.md). The native diagnostic
uses OpenJiuwen's ReAct agent through the existing authorized callback; it is
not a raw JiuwenSwarm upstream comparison. The pinned upstream JiuwenSwarm
source declares OpenJiuwen core `0ab5913b250d565b35bff3828dae438939cb1acd`,
while the verification image pins `9e3390195a9ea15235b2b5f7412cb2aa440622cc`.
The upstream application harness has **not** been executed.

## Pilot preparation and remaining work

`ml_pilot` authors two small synthetic classification examples with public
training/test features and root-private held-out labels. Stop the app before
switching tasks: the quiescence check is an operational guard, not an atomic
lock against a concurrently starting executor. Preserve each task manifest,
private seed/holdout and separate profile directory; do not expose private
answers to Builder or the runner. New ML captures request `gpt-6-luna` explicitly
and preserve their review-mode selection. Existing captured model choices are
not rewritten.

The opt-in durable budget is enabled by `AI4R_PILOT_BUDGET_DIRECTORY` pointing
at an app-owned private directory prepared with `python -m
jiuwenswarm.research.pilot_budget prepare`. It charges attempts before provider
effects, includes failures, survives restart and stops at 900 attempts or
10,800 seconds after the first claim. Controlled tests cover concurrency,
restart and deadline behavior. No live campaign ledger was started here.

Rebuild the application image from this source before using the new commands.
Then prepare scoped runner credentials through the existing issuer, verify
authenticated readiness against the exact build and run a small frozen ML
Builder → independent Benchmark demonstration. The E2/E3 CLI is fixture-tested
authoring; its full Compose source-production procedure remains unvalidated.
The v2 evidence-aware E2 path is explicitly unavailable before a model call;
ordinary per-output v2 review and historical output-only E2 are separate paths.
The diagnostic native agent's 5 controlled tests are not an upstream comparison.

The PRD-story matrix uses the owning `ai4r_muk` source at commit
`889682f0afc3d06c2ad88e71534483a31d2eb560`, file
`docs/product/received-prds/prd-m1-v10-2026-10-15.txt`, SHA-256
`6d85972cdc8cf586a3d76b80d56510d695f03bfcf7838661afc7f71c35f4b3fc`.
Older frozen received sources in M1 were not overwritten.
