# Workbook changes: CC and Architecture rows (October 14)

**Input:** `AI4Research_Project_v1.2 (3).xlsx`, sheet Main Table. **Scope:** Capability Capsules (1.x) and Architecture (8.x) rows only. Other components are out of scope. **Use:** hand this list to the agent that edits the workbook. Take a fresh snapshot before editing, and keep other contributors' edits.

## Why these changes

- RSI and Router get no human effort before the October 30 core gate (D22).
- The design package now needs a one-shot readiness pass before coding starts on October 16. See [one-shot readiness](oneshot-readiness.md).
- The static fixed DAG runs first, then the Planner (D26).
- The Architecture timeline has empty windows between October 23 and 28, and in mid-November.

## Fixes across all rows

| Problem | Change |
|---|---|
| Rows 8.0, 8.1, 8.2 and 8.3 show start and end as serial numbers (46308) | Format those cells as dates |
| Most rows repeat one boilerplate risk ("Missing output, access or evidence blocks the affected claim...") | Replace with the row-specific risks given below. Keep the boilerplate only where no specific risk exists |
| Rows longer than three working days are listed as subtasks (8.4.1, 8.5.1, 8.6.1, 8.7.1, 8.8.1, 8.9.1) | Make them task rows (x.y) with no subtasks yet. They get split at the freeze before each month |

## Capability Capsules (1.x)

| Row | Change | Field values |
|---|---|---|
| 1.1.3 Align Planner contract and frozen-DAG checks | Edit metric | Metric: Planner page and run plan contracts exist; a cycle, an incompatible port and a missing check bundle are each rejected by a named check |
| 1.1.4 Align downstream CC contracts and interfaces | Edit metric and risk | Metric: each of the eight downstream CCs has a declaration, field table with constraints, check bundle and verifier criteria; names are lowercase. Risk: a field that conflicts with the PRD keeps that CC open; resolve with the PRD owner before Oct 16 |
| 1.1.5 Align shared assessment and gate profile | Edit metric | Metric: every verifier criterion is answerable from declaration and output only; no example or page gives the verifier worker input |
| 1.1.2 Package reduced scope for coding handoff | Replace dependency 8.1.2 with 8.1.7 | Risk: an unaligned PRD section blocks the affected CC, not the whole package |
| 1.1.14 M1 coding starts | Rename | Name: One-shot coding starts from the readiness-checked package |
| 1.2.1 Investigate runnable code and gaps | Edit metric | Metric: static template path runs one request to Delivery or an attributable halt before planned-mode work is reviewed; each gap has evidence, owner role and disposition |
| 1.2.2 Hand off pinned parent to offline RSI | Move out of October | Start Nov 9, end Nov 10, depends on 1.3. Mark optional. It pairs with 1.12.1 |
| 1.2.5 Offline RSI comparison artifacts | Delete from October | Fold into 1.12.1 as its RSI handoff evidence |
| 1.2.4 Benchmark workflow and limitations | Edit metric, add dependency 8.1.5 | Metric: the M1 pilot cases run end to end and their results are stored as the baseline for later milestones; scores are recorded, not targeted |
| 1.3 Demonstrate the working main path and benchmark verdict | Edit expected result | Expected result: working bounded Compiler-to-Delivery path, benchmark baseline report and indexed artifacts |
| 1.4 and 1.4.1 | Remove duplication | Keep 1.4 as the parent. Rename 1.4.1 to "Integrate Generalist through declared ports and assigned checks" |

## Architecture (8.x)

| Row | Change | Field values |
|---|---|---|
| 8.1.4 Integrate RSI and Router interface handoffs | Rename, close today | Name: Record RSI and Router seams as non-blocking. End Oct 14. Metric: future-seam table in the core build page; no core dependency on either |
| 8.1.2 Finalize RSI and Router integration | Delete | No human effort on RSI or Router before the core gate |
| **New 8.1.7** | Add, Oct 15 to 16, Architect | Name: Close one-shot readiness blockers. Expected result: design package that a coding agent can build from without inventing shared names or fields. Metric: blockers B1 to B14 closed or dispositioned; `validate.py` passes; compact synced; one adversarial review done. Resources: one-shot readiness plan, PRD, design package. Depends on 1.1.3, 1.1.4, 1.1.5. Risk: a PRD gap found in review stays open and blocks only the affected CC |
| 8.1.6 Integrate handed-off benchmark sidecar interface | Edit metric | Metric: benchmark runner page defines case, campaign, hardware inventory, run record, outcome mapping and the evaluation-profile entry points; open items sent to the Benchmark owner |
| 8.1.5 Finalize benchmark sidecar/test-interface handoff | Keep | Risk: Benchmark owner disagreement on M1 acceptance scope keeps 1.2.4 open, not coding start |
| 8.1.3 M1 package ready for coding | Replace dependency 8.1.2 with 8.1.7 and 8.1.5 | none |
| **New 8.2.5** | Add, Oct 19 to 20, Architect | Name: Classify design defects from generated code. Expected result: list separating design defects from implementation defects. Metric: each item links to a contract and an observed output. Depends on 1.1.14. Feeds 1.2.1 and 8.2.6 |
| 8.2.6 Draft next-cycle architecture and interface DAG | Move to Oct 21 to 23 | Depends on 8.2.5 instead of 1.2.1 (1.2.1 ends Oct 20, so the current Oct 20 start breaks its own dependency) |
| **New 8.2.7** | Add, Oct 26 to 28, Architect | Name: Revise architecture draft from verifier and benchmark results. Metric: each finding from 1.2.3 and 1.2.4 has a design disposition. Depends on 1.2.3, 1.2.4, 8.2.6. Fills the empty Oct 26 to 28 window |
| 8.2.2 Draft and release architecture feedback form | Add dependency 8.2.7 | none |
| **New 8.3.5** | Add, Nov 12 to 13, Architect | Name: Review admission contract against the generated candidate. Depends on 1.12.1. Metric: eligibility record fields confirmed or changed with a decision |
| **New 8.3.6** | Add, Nov 19 to 20, Architect | Name: Review Planner and MCTS interface changes. Depends on 1.13.1. Metric: plan proposal type and binder unchanged, or the change is recorded as a decision |

## Not changed

- The Nov 2 to 3 review session and the conditional freeze (8.2.10, 8.2.4) stay as they are. The freeze stays conditional on an aligned PRD.
- The optional integrity-report skill (8.2.8) stays on Nov 5 to 6.
- Composition stays in December (1.5 and 8.4).
