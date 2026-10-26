# Pipeline02 AI4Research dispatch attempt — October 26, 2026

Source: current `ai4r_M1` commit `0fa35ee38`, isolated branch
`benchmark/pipeline02-ai4r`. The real suite generator froze the four authored
variants. Its actual dispatcher was invoked sequentially with `mode: live`;
the actual independent grader retained unavailable assessments.

| Variant | Dispatch result | Product request launched | Correctness |
| --- | --- | --- | --- |
| dependency-unavailable | BLOCKED before dispatch | No | Unavailable |
| cancel-active | BLOCKED before dispatch | No | Unavailable |
| observer-restart | BLOCKED before dispatch | No | Unavailable |
| collection-restart | BLOCKED before dispatch | No | Unavailable |

All four receipts state:

> protected frozen fault controller and interruption/negative-capture binding are absent

This guard precedes runner-backend selection. No application endpoint or scoped
credential was selected or tested. There were **zero native E1 requests, zero
model calls and zero scientific executions**. No AI4Research run ID exists.
No app deployment, new port, Docker operation, service restart, or RSI/MR change
was needed for this dispatcher attempt. RSI's 5175 service was untouched.

The current scientific resource/metric validators also reject the public cache
workload: the classification resource parser reports `blind_scoring` (another
closed schema), and `validate_metric_ids(['hits', 'misses', 'miss_ratio'])`
reports `metric_protocol_unsupported`, requiring canonical `accuracy`. These
are source-contract diagnostics, not native invocations or scientific failures.

## What is missing

1. The native protected fault controller and authenticated effect/audit joins
   for dependency failure, cancellation, observer restart and collection restart.
2. A supported cache scientific resource/metric/scoring protocol and compatible
   admitted scientific capsules. The current classification/Pi path is not an
   equivalent cache experiment.
3. A qualified isolated app/runner build, fresh scoped credentials and exact
   runtime/resources for that supported protocol before actual E1 dispatch.

The standalone Codex-generated controller is not a substitute for native
authority, cancellation acknowledgements or original sidecar/bridge custody.
Its local fault checks cannot establish this AI4Research arm's acceptance.
The case assumes capabilities the current product integration has not supplied.
This result does not establish a model-account, transport or scientific failure.

## Retained evidence

Local full preparation:
`D:/Codex Development Runs/pipeline02-ai4r-20261026/`.
It contains the frozen bundle, selected live-mode config, four original
`suite-receipt.json` files, independent assessments, report and source hashes.

The [attempt evidence ZIP](examples/pipeline02-ai4r/attempt-results-20261026.zip)
contains the receipts/assessments, `RESULT.json`, `report.json`, source pins and
the exact preparation/dispatch script. No credentials or private case criteria
are included. All four variants remain in the report denominator; correctness
and full-task success are null, and release acceptance is not established.

Next work is implementing the missing native capabilities, not replaying the
same blocked dispatch or running a different prompt under this case identity.
