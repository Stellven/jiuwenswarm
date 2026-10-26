# Demo results: 23 October 2026

These are demos, not M1 acceptance. One CPU attempt and one paper attempt were run sequentially on LAPTOP-MFQ6O7IF using the existing 5175 app. GPU execution was explicitly deferred. No repeat or automatic quality judge was run. The CPU blocker and the requested small scope made additional attempts inappropriate here.

| Case folder | Actual execution | Outcome |
| --- | --- | --- |
| [case1-cpu](case1-cpu/README.md) | HALTED; evidence collected | Intent advanced; Requirements verifier rejected comparison=null alongside the five-point target. No training, predictions or scoring. [Details](case1-cpu/RESULT.md). |
| [case2-gpu](case2-gpu/README.md) | NOT_RUN | Spec, timing script and environment-blocking preflight built. No GPU execution or timing, per user instruction. [Details](case2-gpu/RESULT.md). |
| [case3-paper](case3-paper/README.md) | COMPLETED; evidence collected | Compiler, Planner, Summary and Delivery completed. Three requested numeric answers match the supplied PDF; formal human assessment remains open. [Details](case3-paper/RESULT.md). |

[Actual campaign report](../results/demo-cpu-paper-20261023-103800/report.md) | [Machine records](../results/demo-cpu-paper-20261023-103800/report.json) | [Delivered paper summary](../results/demo-cpu-paper-20261023-103800/runs/case3-paper-r1/artifacts/readable/paper_summary.md)

Campaign ID: demo-cpu-paper-20261023-103800. CLI exit code 2 reflects the CPU halt; paper execution and both evidence collections completed. The report leaves human quality fields blank. Each case has its own run-manifest.json and reviewer-only notes/checklist. run-manifest.json records physical host, source checkout commit, immutable installed build/image, observed model and exact output paths. The runner itself stores build identity/native model evidence, but does not natively capture the checkout commit and physical Windows hostname; reviewer-side provenance supplies those separately.

Both executed cases observed gpt-6.1-sol. Checkout f7b31c6796191c5a80804a9484b031bc671bc6db is distinct from installed app build db45a807a314ef5aab1f69090b1a5bd8d0f7c1eed878cc857885518ef4780ca4. No app, runner source, baseline, protected dataset or approved environment was changed to force a case to pass.

Private test_labels.csv, reference predictions, expected paper answers, reviewer extraction and the fixture builder remain under this demos directory, outside mounted cases/inputs/results. Uploaded public copies only: train.csv, test.csv, data-description.md for CPU, and chunk-recomputation-2610.31019.pdf for paper. Provenance helpers use upload:false. GPU never entered this campaign. Do not upload reviewer folders or this full demos folder.

Human review: Case 1 cannot be scored because actual predictions are absent (reviewer/scoring-status.json); use its reviewer/score_predictions.py only against actual future app predictions. Case 2 requires a later approved CUDA/PyTorch executor with latency support, then an independent rerun on the same host; current app lacks that environment. Case 3 reviewer/answer-observations.md records the source comparison; humans should still review the complete summary against the PDF and fill the report fields.
