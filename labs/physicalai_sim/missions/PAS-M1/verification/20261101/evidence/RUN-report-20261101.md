# Verification run: RUN-report-20261101
Stored in the selected feature's evidence/ (not committed). Document check over runtime evidence; it never replaces that evidence.

## 1. Execution identity
| Field | Actual value |
| --- | --- |
| TASK ID / run ID / UTC time | PAS-M1-001 / RUN-report-20261101 / 2026-11-01 |
| Level and V IDs | Document: V-REPORT (AC-022) |
| Candidate identity | `missions/PAS-M1/reports/PAS-M1_Phase1_Completion_Report.md`; snapshot `missions/PAS-M1/verification/20261101/` (75 files, SHA-256 per file in `INDEX.json`) |
| Baseline / component revisions | Evidence records RUN-x11, RUN-cg, RUN-bench, RUN-x14b, RUN-ops, RUN-x16-rehearsal (all 20261101) |
| PRD, spec, plan and IF versions | Sources r0.4.3 (test plan "Reports and evidence"); spec r1 AC-022 |
| Working directory / platform / runtime / dependency versions | N/A (document check) |
| Input/fixture/dataset/model/prompt/configuration versions | N/A |
| Dependency mode and actual services | N/A |
| Command or reproducible manual procedure | A script checked that the report has every required section (scope and exits; commit, images and hardware; results per exit; test bench errors; results per family; official benchmarks; deviations; retained failures and negative controls; blocked items; capability gaps; limitations; owner approval) and ends with a compute summary, that all six exits appear, and that every relative link resolves; the snapshot was written with failures beside passes |

## 2. Per-check observations
| V ID / AC references | Expected outcome / threshold source | Actual outcome | Exit code / counts including skips | Result | Raw artifact location |
| --- | --- | --- | --- | --- | --- |
| V-REPORT (AC-022) | Every section the test plan lists; compute summary last (totals, heaviest runs, peak memory against 6 GB WSL and 6 GB GPU); claims linked to evidence; failures kept in the snapshot | 13 of 13 sections present, compute summary last, 26 links, 0 broken; snapshot holds the X1.1 failures, negative controls and a failing development run beside the passes | N/A | PASS (document check); owner approval pending | report and snapshot paths above |

## 3. Scope and validity
- Behavior established: the report and snapshot exist and are complete in form; their numbers were taken from the evidence records and corrected where a first draft did not match them (TB-06 energy drift, TB-08 drift and penetration).
- Behavior not established / failures / blockers: owner approval; the report itself states phase 1 is not complete (X1.1 FAIL, X1.2 and X1.6 BLOCKED).
- Candidate/input changes after this run: none.
