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

## 7. Limitations and risks

- Synthetic linked illustration only. No measured experiment.
- Both registered metrics have baseline and treatment values for all 3 repeats.
- A 5% latency increase is within the range expected for added index maintenance.
- Risk from the opportunity card: Index maintenance could offset lookup gains

## 8. Follow-up recommendations

- Recommendation: Investigate why index maintenance offsets retrieval savings in a separately authorized new experiment.

## 9. Reproducibility

Seed 42. Repeats 3. Hardware and runtime: run_configuration.json. Install with the pinned lock, extract the bundle, then run run_benchmark.py under the same configuration and seed.

| Item | Id | sha256 |
|---|---|---|
| Research brief | lifecycle_research_brief.json | 925f37d264242392bd1b5bde837db52bcc99568fb0274dd3ef6e9fa229d4fe00 |
| Hypothesis blueprint | hypothesis_blueprint.json | 6ea05257d6a754f3619b2d580330cf7f926719ce8c494d4fc204e8af2a3cbef9 |
| POC manifest | poc_manifest.json | 66639995c3502b87354e13873778bcdabb4213a8220cc116bd868b65a75e7a33 |
| POC bundle | poc_artifact_bundle.zip | 95a3c10da5f0b0bb6c8df9c0865b1062e675992209a8bc01670da458692013c1 |
| Environment lock | environment_lock.json | 28f223d79c9dd33b40417aa1799cf85fc355b086f93eba287387e269de64d0fd |
| Run configuration | run_configuration.json | f0790faad1c5ec93ce5c42ff3d1797edf29f935cffa1197931636ce070703fb9 |
| Benchmark payload | benchmark_payload.json | 9fcfc29bf95cec03e972fdcab2c074f7bb51aae1d502ff0148a9f55f33240cfb |
| Evaluation verdict | evaluation_verdict.json | ddb92be8d8bde4b065305f77232cacab0a48869c91679e8b55b20cc4cba7db3d |
