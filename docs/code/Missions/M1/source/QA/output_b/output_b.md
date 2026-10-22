# Training-derived midpoint classifier improves accuracy on a tiny authored held-out split

## 1. Objective

Evaluate whether replacing the majority-class classifier only in poc_patch.py with a threshold at the arithmetic midpoint between training class means improves held-out accuracy on the existing captured train/test data. The baseline, held-out split, accuracy measurement and outcome rules remain fixed. Accuracy is the fraction of correctly classified test examples, with higher values better. The registered improvement claim succeeds only when treatment accuracy > baseline accuracy and is falsified when treatment accuracy <= baseline accuracy. The scope is a local CPU demonstration using only the Python standard library, without dependencies, network, GPUs or external data.

## 2. Opportunity and citations

Constant majority-class prediction misses minority-class cases. A scalar cutoff derived from the two training class means may recover these cases if the separation observed in training transfers to the held-out split and outweighs any newly incorrect majority-class predictions. The selected opportunity was the sole screened candidate, ranked first with compute alignment 5, feasibility 4 and novelty 2, totaling 11. Its modest novelty reflects that the midpoint intervention was already described in the local project source.

The supporting citations are citation:1, citation:2 and citation:3 in candidate_set, blob:e8f3234f8c754e8a4fee0198de6af0cc00ec3a5191132f801859c8472188cebc. All three are overlapping excerpts from the same local document, blob:b2553022a3c66a0418efe59ff48efa6c8d850d6c1e11d3337cc28829404586ba, rather than independent scientific sources. They describe the majority-class baseline, proposed training-derived midpoint, fixed evaluation and resource restrictions. They establish the project context and proposed mechanism, not empirical evidence of improvement.

The opportunity initially depended on unproved premises that the captured data supported a two-class scalar threshold with distinct training means and that separation would transfer to the held-out split. Overlapping classes or outlier-sensitive means could instead make the treatment equal to or worse than the baseline. The reported result supports improvement on this particular captured split; it does not establish generalization to other datasets or splits.

Citation IDs: citation:1, citation:2, citation:3.

## 3. Hypothesis and registered criteria

Replacing the majority-class classifier only in poc_patch.py with a threshold at the midpoint between training class means will increase held-out accuracy on the existing captured train/test data relative to the unchanged baseline.

| Metric | Unit | Aggregation | Success rule | Falsification rule | Otherwise |
| --- | --- | --- | --- | --- | --- |
| accuracy | fraction | mean | success: treatment > 1 * baseline + 0 | falsification: treatment <= 1 * baseline + 0 | INCONCLUSIVE |

## 4. Method and POC

The registered blueprint specifies computing the two class means from captured training data, placing the cutoff halfway between them and assigning each side to the corresponding class using training data only. The classifier intervention is confined to poc_patch.py; the baseline, validation data, measurement functions and outcome rules are protected from change. The supplied POC manifest, blob:add14e35bac61eac30061bc035f9796b1d6f58204f87a82898d196f12b1b4f30, references the treatment code, benchmark runner, empty requirements file and POC archive. The referenced code and raw logs were not independently inspected in the supplied evaluation, so implementation compliance should be understood within that evidence limit.

The execution receipt records three baseline runs followed by three treatment runs, all with seed 42 and exit code 0. Baseline runs invoked /environment/bin/python /resources/baseline/baseline.py; treatment runs invoked /environment/bin/python /resources/poc/run_benchmark.py. The provisioning receipt reports Python 3.12.15, no installed packages, network policy none and zero unlisted network requests. The execution inventory records a local CPU environment with zero GPUs. These records support the intended standard-library local CPU execution protocol.

The supplied benchmark payload, blob:f600d5f8f757ec0c810e68a66eac10898d45e0f8cd3b3043e0aaebf2f5cf3627, reports baseline accuracy fractions of 0.5, 0.5 and 0.5, and treatment fractions of 1.0, 1.0 and 1.0. Their respective means are 0.5 and 1.0, an improvement of 0.5 fraction units. All values lie within the registered bounds of 0 and 1. The supplied evaluation verdict, blob:35a341078b08297ab41283ec78bc708866c9e0cce16338523949281ad04f4246, classifies the result as PASS because 1.0 > 1 * 0.5 + 0. The less-than-or-equal falsification condition is not met. This reports the supplied scientific verdict and does not authorize acceptance.

Perfect treatment accuracy is limited to this tiny authored held-out split. Repeating the same split with the same seed does not provide independent evidence of robustness, and the reported accuracies alone do not establish which individual prediction changes produced the gain. Broader generalization would require a separately authorized evaluation on independent datasets or splits; no such follow-up was executed or authorized here.

Observed hardware: Intel(R) Core(TM) i7-14650HX; CPU cores: 24; RAM: 7824 MB; GPU count: 0.

## 5. Results: baseline vs treatment

| Metric | Unit | Baseline | Treatment | Delta |
| --- | --- | --- | --- | --- |
| accuracy | fraction | 0.5 | 1.0 | 0.5 |

## 6. Scientific verdict and reasoning

Classification: PASS
Completeness: complete
Plausibility: plausible
- accuracy: PASS. Treatment mean accuracy 1.0 exceeds the registered threshold of 1 * 0.5 + 0 = 0.5. The reported improvement is 0.5 fraction units; all three repeats on each side match their reported mean.

## 7. Limitations and risks

- This tiny authored demonstration does not establish generalization across independent datasets or splits.
- Repeating the same fixed split with the same seed does not provide independent evidence of robustness.
- Referenced code and raw logs were not independently inspected in this evaluation.
- The sole registered metric, accuracy, has nonnull baseline and treatment values and three repeats per side.
- The payload records three baseline runs before three treatment runs, with seed 42.
- All accuracy values lie within the registered bounds [0, 1]; reported means and delta agree with the repeats.
- Perfect treatment accuracy is plausible on this tiny authored held-out split; identical repeats are consistent with the fixed data and seed.
- Risk from the opportunity card: Overlapping classes or outlier-sensitive training means could place the midpoint poorly, producing treatment accuracy equal to or below baseline and falsifying the improvement claim.
- Risk from the opportunity card: The tiny authored demonstration may not represent other datasets; three repeats with fixed seed 42 would not establish generalization across independent splits.

## 8. Follow-up recommendations

- Recommendation: For any broader generalization claim, consider a separately authorized evaluation on independent datasets or splits; no additional evaluation is executed or authorized here.

## 9. Reproducibility

| Item | Id | sha256 |
| --- | --- | --- |
| Research brief | blob:457585abc82be47910571f018bbd07816ff6d606b15d13e37072a1f78fd5158e | 457585abc82be47910571f018bbd07816ff6d606b15d13e37072a1f78fd5158e |
| Hypothesis blueprint | blob:7d3206f23b6122dd59c8556cc40a10dd0dc6d814a910545ee7a26724643a9292 | 7d3206f23b6122dd59c8556cc40a10dd0dc6d814a910545ee7a26724643a9292 |
| POC manifest | blob:add14e35bac61eac30061bc035f9796b1d6f58204f87a82898d196f12b1b4f30 | add14e35bac61eac30061bc035f9796b1d6f58204f87a82898d196f12b1b4f30 |
| POC bundle | blob:4d51b2387bc6bcd0cac9716af7ddea981fc555f1f8a0781641e344aebc1e7d4e | 4d51b2387bc6bcd0cac9716af7ddea981fc555f1f8a0781641e344aebc1e7d4e |
| Environment lock | blob:69c30f8f9e627138ecfb453b50ef60e3d2b04a64cb2cf39e928d91acdd988bb8 | 69c30f8f9e627138ecfb453b50ef60e3d2b04a64cb2cf39e928d91acdd988bb8 |
| Run configuration | blob:5d4d3869c35347de30794fa7abc266f5a3cd7e50660e8e578d52a6a78833d201 | 5d4d3869c35347de30794fa7abc266f5a3cd7e50660e8e578d52a6a78833d201 |
| Benchmark payload | blob:f600d5f8f757ec0c810e68a66eac10898d45e0f8cd3b3043e0aaebf2f5cf3627 | f600d5f8f757ec0c810e68a66eac10898d45e0f8cd3b3043e0aaebf2f5cf3627 |
| Evaluation verdict | blob:35a341078b08297ab41283ec78bc708866c9e0cce16338523949281ad04f4246 | 35a341078b08297ab41283ec78bc708866c9e0cce16338523949281ad04f4246 |

Seed: 42. Repeats per arm: 3. Seed policy: fixed_same_for_all_runs.
Run order: baseline, baseline, baseline, treatment, treatment, treatment.