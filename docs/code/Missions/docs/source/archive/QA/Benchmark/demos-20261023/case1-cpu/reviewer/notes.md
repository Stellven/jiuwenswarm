# Reviewer only — never upload this file

This is a small demonstration, not M1 acceptance. Expected outcome: full CPU workflow, predictions.csv, supported claim if the measured gap is at least 5 percentage points.

Manual checklist (leave unchecked until a human reviews the saved evidence):
- [ ] The actual host, checkout commit, installed build and observed model are recorded.
- [ ] Expected stages: Intent → Requirements → Planner → Search → Screening → Hypothesis → Builder → Benchmark → Evaluation → Delivery. Record missing stages and the earliest stop reason.
- [ ] Capsule verifiers and deterministic gates advanced or blocked for a documented reason.
- [ ] Claims cite only the supplied public inputs. Reviewer files were not uploaded.
- [ ] Every reported measurement traces to original raw outputs and an actual execution.
- [ ] No missing number, prediction or timing is fabricated.
- [ ] Execution/collection outcomes are distinguished from research quality.

Assessment:

Evidence references:

Review notes:


Private calibration is in reference-measurements.json. Score actual AI4R predictions against test_labels.csv by ID only after collection. The installed runtime currently pins a majority-class baseline and a different root-scored data.json; do not relabel that baseline as 1-NN or use its scores for these CSVs. If the app cannot bind the requested data/baseline, record BLOCKED and preserve its output.
