# Scientific measurements become a verdict

## Starting items

A frozen hypothesis_blueprint expects at least 40% lower peak VRAM, falsifies below 10%, preserves a Brief target of at least 30%, and pre-registers middle_zone_classification=INCONCLUSIVE. It declares one repeat, seed 1234, mean statistic and a trusted peak_vram method. The complete [fixture pack](fixtures/science.json) uses structural hashes; it is not runnable admission evidence.

POC generation supplies a poc_bundle containing the patch, harness and syntax evidence. It does not supply authoritative measured scores.

## Code and trust connections

1. `capsules/research.run_benchmark/` resolves poc_bundle and blueprint Refs through the runner.
2. `cc/security/poc_service.py` provisions a disposable attempt tree using the pinned offline wheelhouse and requests the validated Linux launcher profile. Original repository, data, method code and credentials are not writable/readable beyond declared mounts.
3. The generated harness calls descriptor-bound `measure_next()`. It cannot submit metric values, choose an arm/seed, change a method or rebind to another run.
4. `cc/security/measurement_service.py` resolves the frozen schedule and method. It executes baseline(0), then treatment(0), using seed 1234 and the same data/config/device. It applies the patch only to the treatment copy.
5. The trusted service measures live workload behavior and commits MeasurementEvidence Artifacts with workload-capture refs. It returns BenchmarkSamples for the harness to forward to stdout.
6. The trusted parser matches each sample to its exact committed evidence, checks order/identity/finite values and creates benchmark_payload. Runner commits that output and Observation; Benchmark Gate/release precede Evaluation.
7. `capsules/research.evaluate_results/` calls `cc/measurements/protocol.py`'s pure comparison helper, makes its bounded plausibility turn, and produces evaluation_verdict. Evaluation Gate recomputes arithmetic/classification before report release.

[Measurement protocol](../m1/measurement-protocol.md) owns the exact stream and evidence shapes. [Confinement](../capsule/process-boundary.md) and [deployment](../system/deployment.md) own actual namespace/identity/mount/network mechanisms.

## Numeric example and report

Baseline is 10 GB; treatment is 6.5 GB. Benchmark records raw delta -3.5 GB. Evaluation transforms relative_percent for a lower-is-better metric:

`100 × (10 − 6.5) / |10| = 35%`

Claim predicate 35>=40 is false; acceptance 35>=30 is true; falsification 35<10 is false. The pre-registered default gives scientific INCONCLUSIVE. That is valid experimental information. Infrastructure verification can PASS, allowing a report that states the target was met but the stronger claim was not established.

The same blueprint gives these independent illustrative cases:

| Treatment GB | Improvement | Scientific outcome with complete plausible evidence |
|---|---|---|
| 6 | 40% | PASS |
| 9.5 | 5% | FAIL |
| 6.5 | 35% | INCONCLUSIVE |
| 6.5 | 35% | CONDITIONALLY_ACCEPTABLE only in a different pre-registered blueprint choosing it and satisfying every acceptance/guard predicate |

No post-result switch to the fourth row is permitted in the original run. The fixture checker validates shapes and independently calculates these expectations with Decimal; it is not running production evaluation.

## Failure evidence that never becomes scientific rejection

An invented stdout value, another run's measurement_ref, missing arm, nonzero exit or incomplete stream preserves raw evidence and blocks benchmark release. A zero baseline denominator makes comparison unavailable; it is not a 0% improvement or scientific FAIL. Unsupported hardware/method or unavailable confinement stops at its readiness boundary. Required capture/save failure blocks advancement even when numbers in memory look valid.

The report uses committed scientific evidence and limitations. It cannot rerun the experiment, edit the preregistration or treat generated harness scalar text as a trusted measurement.
