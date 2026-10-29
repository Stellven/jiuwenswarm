# Reviewer only — never upload this file

This is a small demonstration, not M1 acceptance. Expected outcome: paper summary completes; all three factual answers agree with the original paper and citations point to the right sections/tables.

Manual checklist (leave unchecked until a human reviews the saved evidence):
- [ ] The actual host, checkout commit, installed build and observed model are recorded.
- [ ] Expected stages: Intent → Requirements → Planner → Summary → Delivery (not the experimental DAG). Record missing stages and the earliest stop reason.
- [ ] Capsule verifiers and deterministic gates advanced or blocked for a documented reason.
- [ ] Claims cite only the supplied public inputs. Reviewer files were not uploaded.
- [ ] Every reported measurement traces to original raw outputs and an actual execution.
- [ ] No missing number, prediction or timing is fabricated.
- [ ] Execution/collection outcomes are distinguished from research quality.

Assessment:

Evidence references:

Review notes:


Reviewer-only oracle supplied by the user:
1. CDC failed on 4 of 62 Chinese articles — Abstract and Section V.
2. Fixed-size recomputed 68.4% Chinese and 57.4% English embedding workload — Section V/Table I.
3. Primary benchmark: 120 revision pairs (149 total); common-success pool: 116 articles — Section IV.
Spare check: 2000 paired-bootstrap resamples, Section IV.
Also inspect fixed-size 304 tokens, recursive target 400, CDC 176–352, frozen BGE-M3, and recall@2048 differences below two points within each language. Do not put this oracle into task text, setup scripts, public descriptions or uploaded artifacts.
New publication alone does not prove the model lacked prior knowledge. Verify the uploaded PDF hash, captured extraction and output citations; this is evidence of document use, not proof about model training.
