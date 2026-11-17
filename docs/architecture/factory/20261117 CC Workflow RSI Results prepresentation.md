# 20261117 CC Workflow RSI Results prepresentation

The factory executed two source-to-build-to-evaluation cycles. The best exploratory screen measured 14.473 to 15.817 decode tokens/s (+9.28%) with exact outputs on the three frozen prompts, but did not meet the frozen 10% target or qualify for independent confirmation. Completed execution is evidence of orchestration; it is not a qualified performance improvement. All measured results and rejections remain retained.

The platform remains the evolved M1-derived inference-engine factory. CCv2 packages and dynamic workflow composition extend that system; no obsolete POC restoration was required.

## Actual measurements

| Phase / stage | Attempt | Baseline tokens/s | Candidate tokens/s | Mean gain | Conservative gain | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| native-design-review-001 / aa | 1920ec8f | 11.257 | - | - | - | inconclusive |
| native-design-review-002 / aa | 13cdad11 | 14.440 | - | - | - | baseline_valid |
| native-design-review-002 / screen | 7d89a882 | 14.456 | 15.655 | 8.30% | 8.30% | target_not_met |
| native-design-review-002 / screen | 0b7f6d0e | 14.473 | 15.817 | 9.28% | 9.28% | target_not_met |

The first A/A phase was inconclusive because its aggregate baseline spread exceeded the unchanged 5% gate. A separately frozen protocol revision supplied matching warmups for all three scored cases, retained the prompts and gates, charged the failed phase to the same aggregate budget, and kept the original deadline. Screens are exploratory. A target-met claim requires a separate unchanged-candidate A-B-B-A confirmation.

## Architecture exercised

The live export contains 61 normalized entries under schema 0.2.0. The selected final graph is design-review-adaptation at revision 5, with 6 executable leaves. Explicit producer bindings: 1. Graph/catalog/event JSON companions retain exact node IDs and derived scopes.

CC packages expose the source workbench, native builder and throughput capabilities. The reusable candidate cycle nests construction and evaluation. The evaluation request receives the collected builder attempt identity through a result-channel binding and bounded template assembly, without manual identity copying. Confirmation, when run, binds to the same builder result across graph revisions. The existing host and Lab Manager remain the execution authority.

RSI read the complete retained historical report, selected a scheduling-only reproduction, preserved the rejected screen and its decision, and received an explicitly labeled external source-review hypothesis about ARM64 relaxation. Its later decisions and experiments are retained in the Qualification ledger. Adaptation changes the engineering plan and source implementation; it does not train model weights or alter the evaluator.

## Per-case evidence

### screen 7d89a882

| Case | Baseline process rates | Candidate process rates |
| --- | --- | --- |
| retained discovery | 13.986 | 15.028 |
| condition-variable code | 14.514 | 15.849 |
| arithmetic reasoning | 14.897 | 16.130 |

Gates: exact_tokens_and_finish=True, fixed_placement=True, baseline_timing_stable=True, suite_case_regression_bound=True.

### screen 0b7f6d0e

| Case | Baseline process rates | Candidate process rates |
| --- | --- | --- |
| retained discovery | 14.023 | 15.446 |
| condition-variable code | 14.466 | 15.808 |
| arithmetic reasoning | 14.961 | 16.214 |

Gates: exact_tokens_and_finish=True, fixed_placement=True, baseline_timing_stable=True, suite_case_regression_bound=True.

## Identities, cleanup and validation

Original engine source: 89ae0ee6123597636ef162dec826230186c00f3b. Final owned candidate source: 84864456256b0e8fb4d933b7dcb67550daafaf85; clean=True. Each successful build record includes its immutable image and source identities, candidate patch and independently verified native owner cleanup receipt. Generic legacy cleanup labels are retained verbatim.

Reserved GPU processes across both phases: 8 of 16. The stopped graph has no pending cleanup. GPU attempts are reaped; native build owner receipts prove container removal. The read-only export did not change graph events. Candidate engine promotion into a serving runtime: False.

Focused platform regression run: 110 tests passed. git diff --check passed. Offline schema migration retained all 150 entries and 55 composition references; negative probes rejected duplicate identities, missing references, cycles and invalid embedded schemas.

The implemented repairs cover typed interconnect validation, collected results, reusable nested procedures, catalog export, read-only inspection, full history artifact discovery, authorized resume after terminal decisions, and native methodology evidence/budget translation. Full raw custody and comparison checks are retained in Qualification and the evidence package.

## Limits and next review decisions

Accuracy evidence is exact canonical token IDs and finish reasons on three fixed prompts with paired warmups, unchanged arithmetic, unchanged quantization and model assets, full six-expert engagement and fixed placement. It is not a general task accuracy benchmark. The operator permits quantization changes, but this run did not evaluate one.

The metric is generated tokens per measured decode time. It does not establish faster prefill, complete requests or client latency. The process sample is small; there is no population confidence bound or held-out workload generalization claim. The comparisons test each full candidate against the original engine; they do not isolate the causal contribution of each scheduling change. The screen selected a candidate on this suite; a broader promotion decision needs a separately frozen untouched workload suite and appropriate quality checks.

The ARM64 hardware-hint hypothesis was based on inspected source and the [official Arm ACLE hint documentation](https://arm-software.github.io/acle/main/acle.html). A hardware hint is not a promise of performance. The independent measurements, rather than the hint description, determine this run’s conclusion.

Keep the compact shared contract and single execution authority. Add optional composite input semantics, independently allocated scope budgets or more transformations only when an actual procedure requires them. For a changed-quantization experiment, freeze a representative quality gate before selecting the candidate.
