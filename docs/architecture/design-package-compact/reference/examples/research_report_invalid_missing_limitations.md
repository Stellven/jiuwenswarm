# Research report: bounded index lookup

Run: run:science. Verdict source: evaluation_verdict.json. This report is synthetic. It illustrates the format and does not claim a real experiment.

## 1. Objective

Reduce retrieval latency while preserving answer quality. Constraints: one GPU, unchanged answer-quality metric. Source: lifecycle_research_brief.json.

## 2. Opportunity and citations

Opportunity idea:001, bounded index lookup. Repeated lookup may be a retrieval bottleneck. An index could remove the repeated work, so test whether it lowers latency without changing answer quality. Source: opportunity_card.json.

| Citation | Source | Locator | Excerpt |
|---|---|---|---|
| citation:index | academic_source.txt | academic_source.txt, sentence 1 | indexed lookup may reduce repeated retrieval work |

## 3. Hypothesis and registered criteria

Claim: Indexing lowers retrieval latency by at least 10% with no answer-quality loss. Mechanism: Avoid repeated lookup work. Independent variable: Bounded index lookup patch. Repeats: 3. Seed: 42. The rules below were registered before any measurement. Source: hypothesis_blueprint.json.

| Metric | Unit | Aggregation | Success rule | Falsification rule | Otherwise |
|---|---|---|---|---|---|
| latency_ms | ms | median | treatment <= baseline x 0.9 | treatment >= baseline x 1 | INCONCLUSIVE |
| quality | fraction | mean | treatment >= baseline x 1 | treatment < baseline x 1 | INCONCLUSIVE |

## 4. Method and POC

The unmodified baseline ran first. The treatment ran second with the same resources, configuration and seed. The treatment changes only the lookup patch in poc_patch.py. The POC bundle is poc_artifact_bundle.zip. It contains requirements.txt, poc_patch.py and run_benchmark.py. Sources: poc_manifest.json, benchmark_payload.json.

## 5. Results: baseline vs treatment

| Metric | Unit | Baseline | Treatment | Delta |
|---|---|---|---|---|
| latency_ms | ms | 100 | 105 | 5 |
| quality | fraction | 0.9 | 0.9 | 0 |

Observation: treatment latency is 5 ms above baseline. Quality is equal to baseline. Raw repeats: baseline_execution.txt and treatment_execution.txt.

## 6. Scientific verdict and reasoning

Classification: FAIL
Completeness: complete
Plausibility: plausible

- latency_ms: FAIL. Treatment median 105 ms is at or above the falsification threshold 100 ms. Success needed 90 ms or less.
- quality: PASS. Treatment mean 0.9 meets the success threshold 0.9, so quality is preserved.

The verdict is the saved evaluation_verdict.json. This report does not change it.

## 8. Follow-up recommendations

- Recommendation: Investigate why index maintenance offsets retrieval savings in a separately authorized new experiment.

## 9. Reproducibility

Seed 42. Repeats 3. Hardware and runtime: run_configuration.json. Install with the pinned lock, extract the bundle, then run run_benchmark.py under the same configuration and seed.

| Item | Id | sha256 |
|---|---|---|
| Research brief | lifecycle_research_brief.json | 428ee0972f41abeeb67eda32c295e17311bfcb0b01dac6d5e66aeeae77adb20d |
| Hypothesis blueprint | hypothesis_blueprint.json | 4b8c45a9c35991556402dd2353dced138f89689a5d60cae24efe3306e9d51ff0 |
| POC manifest | poc_manifest.json | 5256dfa86a4212a05fec6d5db23211322e4d4e136f687a5bb69dc648d23f0e6b |
| POC bundle | poc_artifact_bundle.zip | 95a3c10da5f0b0bb6c8df9c0865b1062e675992209a8bc01670da458692013c1 |
| Environment lock | environment_lock.json | e94243e5b3b3b196962158fc9587cffdeaa24acbc27d96a9521f352906ea17df |
| Run configuration | run_configuration.json | 73986166bce89a44950b5fea962af99e56e86f0f1ef41f881dc523d6c51bee72 |
| Benchmark payload | benchmark_payload.json | cfc5e075b052346568b09fe13c52b8d5d6e7398b86c74b7b653a23cc9931a1aa |
| Evaluation verdict | evaluation_verdict.json | 1279dd59a9999c7ee9323ea05c01d8b0e74b87308e90dd8bf9950ba773dcbb1c |
