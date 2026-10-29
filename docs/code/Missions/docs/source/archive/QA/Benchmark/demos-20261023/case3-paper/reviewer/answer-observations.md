# Reviewer observations: delivered text against the supplied PDF

This is a manual comparison of the three requested facts, not an automatic judge or final human quality score. Human Assessment, Evidence references and Review notes remain open in the runner report.

| Question | Delivered summary | PDF location |
| --- | --- | --- |
| Chinese CDC failures | Results: 4 of the 62 Chinese primary articles | Abstract and Section V/Table I |
| Fixed-size workload recomputed | Results: 68.4% Chinese and 57.4% English, common-success pool | Section V/Table I |
| Primary pairs and common-success pool | Method/Results: 120 primary pairs; 116 articles | Section IV |

The Method also states fixed-size 304, recursive target 400, CDC 176/352 tokens, frozen BGE-M3, and 2,000 bootstrap resamples. Results reports each recall value; the within-language spreads are below two points. The summary distinguishes observed recall from equivalence and describes limitations in labeling, scope, settings and causal interpretation. It does not explicitly state the 149 total sampled pairs; the requested primary count is present.

The original and readable paper_summary.md bytes match. See run-manifest.json for SHA-256 and exact artifact location. Cite section/table wording in the actual summary and check against public/chunk-recomputation-2610.31019.pdf. These observations do not prove what the model knew before the run or constitute an exhaustive review of every summary claim.
