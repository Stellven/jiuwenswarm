# Workbook handoff: Capability Capsules and Architecture rows

**For:** the agent that edits the live team workbook. **Prepared:** October 14, 2026. **Source snapshot:** `AI4Research_Project_v1.2 (3).xlsx`, sheet Main Table, rows 5 to 42 (component Capability Capsules, WBS 1.x) and rows 308 to 339 (component Architecture, WBS 8.x).

This page gives the full target state of the 1.x and 8.x rows. Apply it row by row. Do not rebuild the sheet.

## 1. Rules for editing the live sheet

1. **Snapshot first.** Before any edit, export the current Main Table rows to a local file. Others edit the workbook at the same time. Never upload a whole workbook over the live one. Edit cells in place.
2. **Scope.** Change only rows whose Component is Capability Capsules or Architecture. In other components, change nothing except the dependency IDs listed in section 6, and report those to the user before you save them.
3. **Columns.** Main Table columns are: Component, WBS, Name, Owner, Status, Start, End / due, Expected result, Work details, Metric, Resources, Depends on, Item type, Duration (days), Schedule, Risk / response. Duration, rollups and the Timeline tab are formulas. Never type over a formula. Enter dates only on subtask rows (x.y.z). Component (x.0) and task (x.y) rows roll up.
4. **Owners are roles.** Use CC owner, Architect, Verifier owner, Benchmark owner (the code verification owner), RSI owner, Router owner, PRD owner. No personal names in these rows.
5. **No repeated dates in text.** Start and End carry the dates. Expected result, Metric and Risk must not restate them.
6. **SMART check per subtask.** Each subtask needs a concrete result, a measurable metric, an owner role, resources, start and end, exact dependency IDs, and a risk with a response. A subtask lasts at most three working days. A milestone is zero days.
7. **Status.** Use the existing values. Rows ending by October 14 that are done stay In progress until the user confirms. New rows are Planned.
8. **After editing,** run the checks in section 7 and send the user a short report: rows added, changed, deleted, dependency edits in other components, and any check that failed.

## 2. Why the plan changes

- **October 30 target is the bounded core.** The Intention Compiler, a static fixed DAG, then a Planner-made fixed DAG, verifiers, gates, Delivery and a benchmark run. RSI and new Router work get no human effort before that gate. The design package now has one build page per capsule, so coding can start on October 16.
- **October gaps are deliberate.** The person in the CC owner and Architect roles also has assigned verifier rows on October 21 to 23 (Verifier 4.1.8 to 4.2.3). Architecture leaves those days free. October 19 is the day the one-shot output arrives, and it goes to CC investigation first.
- **November adds one feature at a time.** Generalist, then generated capsules, then automatic admission, then better planning, then MCTS. Each one has its own acceptance before the next starts.
- **Automatic admission is a reliability, speed and cost trade-off.** A strict gate admits fewer bad capsules but slows development and costs more per admission. The CC owner, the RSI owner and the Benchmark owner decide the strictness together before admission is built. The decision is revisited with data.
- **Architecture works one block ahead.** From November on, each month the Architect designs the next block while the current block is built. Every month follows the same step order and rough time split (section 5). Design can start before the PRD is final, but it cannot freeze until the PRD for that block is final.
- **Later months are provisional.** The Architect role may rotate. Dates may shift by a few days. The order of steps stays.

## 3. Capability Capsules (1.x), target state

Rows are in display order. "New" means insert. "Edit" means change only the named fields. "Keep" means no change.

### 1.0 and 1.1: October core design (keep parent rows)

| WBS | Action | Name | Start | End | Expected result | Metric | Resources | Depends on | Risk / response |
|---|---|---|---|---|---|---|---|---|---|
| 1.0.1 | Keep | Review IntentCompiler preflight snapshots and gaps | Oct 13 | Oct 14 | keep | keep | keep | keep | keep |
| 1.1.1 | Keep | Review Compiler contract and preflight findings | Oct 13 | Oct 14 | keep | keep | keep | keep | Compiler code copies worker input into the verifier call. Record it as a code follow-up for 1.2.1, not a design blocker |
| 1.1.3 | Edit | Align Planner contract and frozen-DAG checks | Oct 13 | Oct 14 | keep | Planner and run-plan pages exist. A cycle, an incompatible port and a missing check bundle are each rejected by a named check | keep | keep | Binder and dispatch are new code. If the run-plan mapping is unclear at review, fix it in 8.1.7 before coding starts |
| 1.1.4 | Edit | Align downstream CC contracts and interfaces | Oct 13 | Oct 15 | keep | Each of the eight downstream CCs has a declaration, a field table with constraints, a check bundle and verifier criteria. All internal names are lowercase | keep | keep | A field that conflicts with the PRD keeps that CC open. Raise it with the PRD owner the same day |
| 1.1.5 | Edit | Align shared assessment and gate profile | Oct 13 | Oct 15 | keep | Every verifier criterion is answerable from the declaration and the output alone. No page or example gives the verifier the worker input | keep | keep | keep |
| 1.1.2 | Edit | Package reduced scope for coding handoff | Oct 15 | Oct 16 | keep | keep | keep | 1.1.1; 1.1.3; 1.1.4; 1.1.5; 8.1.7; 6.1.2 | An unaligned PRD section blocks only the affected CC. Coding starts on the rest |
| 1.1.14 | Edit | One-shot coding starts from the checked package | Oct 16 | Oct 16 | keep | keep | keep | 1.1.2; 8.1.3 | keep |

### 1.2: October build review (keep parent)

| WBS | Action | Name | Start | End | Expected result | Metric | Resources | Depends on | Risk / response |
|---|---|---|---|---|---|---|---|---|---|
| 1.2.1 | Edit | Investigate runnable code and gaps | Oct 19 | Oct 20 | keep | The static path runs one request to Delivery or to a recorded halt before planned-mode code is reviewed. Each gap has evidence, owner role and disposition | keep | 1.1.14; 7.1.3 | Oct 19 is the busiest day. If the output arrives late, shift 1.2.1 and 8.2.5 by the same delay. Do not compress 1.2.3 |
| 1.2.2 | Edit, conditional | Export pinned Screening parent for offline RSI | Oct 20 | Oct 20 | Pinned Screening ranking parent, its contract and baseline evidence handed to the RSI owner | Parent version, check bundle and evidence refs recorded | Runnable Screening CC; RSI interface | 1.2.1 | Conditional: only if Screening runs by Oct 20. Otherwise the RSI owner uses the synthetic parent and this row is marked Not needed. It never blocks the core |
| 1.2.3 | Keep | Run existing verifier assignments | Oct 21 | Oct 23 | keep | keep | keep | keep | These are the same cases as Verifier 4.1.8 to 4.2.3. Count the effort once |
| 1.2.4 | Edit | Benchmark workflow and limitations | Oct 26 | Oct 28 | keep | The M1 pilot cases run end to end and their results are stored as the baseline for later blocks. Scores are recorded, not targeted | keep | 1.2.3; 4.1.8; 4.1.9; 4.1.11; 6.1.4; 6.1.6; 8.1.5 | Partial runs still count as evidence. Missing cases are listed with the reason |
| 1.2.5 | Delete | Offline RSI comparison artifacts | | | | | | | The RSI owner's mini pilot (3.2.8) covers this |
| 1.3 | Edit | Demonstrate the working main path and benchmark verdict | Oct 30 | Oct 30 | Working bounded Compiler-to-Delivery path, benchmark baseline report and indexed artifacts | keep | keep | 1.2.4; 4.1.10; 4.2.6; 6.2 | keep |

### 1.4, 1.12, 1.13: November, one feature at a time (M2)

| WBS | Action | Name | Start | End | Expected result | Metric | Resources | Depends on | Risk / response |
|---|---|---|---|---|---|---|---|---|---|
| 1.4.1 | Edit | Integrate Generalist through declared ports and assigned checks | Nov 4 | Nov 6 | Generalist capsule admitted and runnable in one bounded plan | One bounded request passes its declared ports and assigned checks. Limits recorded | Frozen M2 design; library; check bundles | 1.3; 8.2.4 | Conditional on the M2 freeze (8.2.4). If the freeze slips, shift every November CC row by the same delay |
| 1.12.3 | New | Agree admission gate strictness with RSI owner and Benchmark owner | Nov 9 | Nov 9 | Admission policy decision: which checks every automatic admission must pass, the cost and time ceiling per admission, the rollback rule and who may override | Decision recorded and accepted by the three roles. Each tier lists its checks and pass threshold. Estimated cost per admission written down | M1 benchmark cost and failure data; verifier false-pass rates (6.5.5); RSI admission integration (3.2.6) | 1.3; 3.2.9; 6.2.8 | Too strict slows November. Too loose lets weak capsules into plans. Start strict for planner-selectable capsules and lighter for sandbox-only ones. Revisit in 1.13.3 |
| 1.12.1 | Edit | Generate one capsule with the Generalist and hand it to RSI | Nov 10 | Nov 11 | One generated candidate with declaration, implementation and provenance, plus an offline RSI handoff | Candidate passes its own check bundle. RSI handoff recorded or marked unavailable | Generalist; RSI interface | 1.4.1; 1.12.3 | RSI unavailability does not block generation. Record it and continue |
| 1.12.2 | Edit | Add automatic library admission | Nov 12 | Nov 13 | Admission writes eligibility records at the agreed strictness | A valid candidate is admitted, an invalid one is rejected, and the admitted version becomes selectable in new plans only | Admission contract (8.3.5) | 1.12.1; 8.3.5 | No admission may change a running plan or widen permissions. A failure keeps the human activation path |
| 1.13.1 | Edit | Improve Planner selection and binding | Nov 16 | Nov 18 | Planner uses newly admitted capsules in valid frozen plans | Valid-plan rate, rejection reasons, time and cost compared with the October baseline on fixed cases | Fixed plan cases; library snapshot | 1.12.2 | A worse valid-plan rate keeps the October planner as default |
| 1.13.2 | Edit | Add bounded MCTS plan ordering | Nov 19 | Nov 20 | MCTS orders candidate plans under a fixed search budget | Same case set and limits as 1.13.1. Required outcomes met or the improved planner stays default | Search budget; fixed cases | 1.13.1 | MCTS cannot waive checks or edit a frozen plan |
| 1.13.3 | Edit | Run November regression and revisit admission strictness | Nov 23 | Nov 24 | Regression results for every November feature, and a keep or change decision on admission strictness | Each agreed case has expected and observed result, gate trace and pins. Strictness decision updated with measured cost and failure data | Benchmark runner; M2 cases | 1.13.2; 1.12.2; 1.4.1 | Failures stay visible. A strictness change needs the same three roles as 1.12.3 |
| 1.13.4 | Edit | Revise December scope and shared resources | Nov 26 | Nov 26 | December CC scope revised from November evidence | Scope lists features, entry criteria and owner roles | November evidence | 1.13.3 | keep |
| 1.13.5 | Keep | November evidence and next-block gate | Nov 30 | Nov 30 | keep | keep | keep | 1.13.3; 1.13.4 | keep |

### 1.5: December, composition and offline fusion (M3)

December follows the monthly CC pattern in section 5: CC work on Wednesday to Friday, Architecture on Monday and Tuesday.

| WBS | Action | Name | Start | End | Expected result | Metric | Resources | Depends on | Risk / response |
|---|---|---|---|---|---|---|---|---|---|
| 1.5.1 | Edit | Revise CC contracts for composite nodes | Dec 2 | Dec 4 | Composite-node contracts for two member CCs | Declarations validate. Member checks still run per member | Frozen M3 design | 1.13.5; 8.3.4 | Conditional on the M3 freeze |
| 1.5.2 | Edit | Run bounded composition cases | Dec 9 | Dec 11 | Composed node runs inside a frozen plan | Fixed composition cases pass or fail with recorded reasons | Composition cases | 1.5.1 | Members keep their own gates. No merged gate |
| 1.5.5 | New | Evaluate isolated fusion candidate with the RSI owner | Dec 16 | Dec 18 | One fused candidate compared with its unfused parents offline | Paired comparison on fixed cases under unchanged criteria | RSI isolated runner | 1.5.2; 3.4 | No fused version enters live plans this month |
| 1.5.3 | Edit | Benchmark December against the November baseline | Dec 30 | Dec 30 | December benchmark report with deltas against November | Same case set and repeats as November. Deltas reported per feature | Benchmark runner | 1.5.5 | Holiday week. If runs are incomplete, report what ran |
| 1.5.4 | Keep | December CC outcome gate | Dec 31 | Dec 31 | keep | keep | keep | 1.5.3 | keep |

### 1.6 to 1.11: 2027 blocks (convert to task rows with monthly subtasks)

Each month uses the same CC pattern. Replace the long 1.6 to 1.10 rows with task rows and these subtasks. Dates follow section 5.

| Month | Task (WBS, theme) | Subtask pattern (same order every month) |
|---|---|---|
| January | 1.6 Spatiotemporal composability: capsules that depend on when and where they run | 1.6.1 Revise CC contracts for the block (W1 Wed to Fri). 1.6.2 Integrate first increment (W2 Wed to Fri). 1.6.3 Integrate second increment or admit new capsules (W3 Wed to Fri). 1.6.4 Benchmark against the previous block (W4 Wed to Thu). 1.6.5 Block outcome gate (last working day) |
| February | 1.7 Lifecycle and compensation: install, drain, replace and undo capsule versions safely | Same five subtasks, 1.7.1 to 1.7.5 |
| March | 1.8 Sandboxed external ingestion: install capsules from outside stores and repositories | Same, 1.8.1 to 1.8.5 |
| April | 1.9 Automatic conversion and admission: turn external tools and skills into admitted capsules | Same, 1.9.1 to 1.9.5 |
| May | 1.10 Goal-directed tool use | Same, 1.10.1 to 1.10.4. Then 1.11 Roadmap evidence acceptance on May 31 |
| June (new, provisional) | 1.14 Reliability and cost hardening | Same five subtasks. Theme set at the May review |

Per-subtask field template for 2027 CC rows:

| Field | Value |
|---|---|
| Owner | CC owner |
| Expected result | Revise: updated contracts for the block theme. Integrate: the increment runs in a frozen plan. Benchmark: block report with deltas against the previous block |
| Metric | Revise: declarations and field tables validate. Integrate: fixed cases pass or fail with recorded reasons. Benchmark: same case set and repeats as the previous block |
| Resources | Frozen design for the block; library; benchmark runner |
| Depends on | First subtask: previous block gate and the Architecture freeze for this block. Others: the previous subtask |
| Risk / response | Themes past March may change at the review session. Keep the step order and update the theme text only |

## 4. Architecture (8.x), target state

### 8.1: Fold interfaces into the coding package (October)

| WBS | Action | Name | Start | End | Expected result | Metric | Resources | Depends on | Risk / response |
|---|---|---|---|---|---|---|---|---|---|
| 8.1.4 | Edit | Record RSI and Router seams as non-blocking | Oct 13 | Oct 14 | Future-seam table in the core build page. No core dependency on RSI or the Router | Each seam names what is kept now and what later work plugs in | Received RSI and Router designs; core build page | 1.0.1; 6.1.2 | No human effort on either before the core gate |
| 8.1.6 | Edit | Integrate returned benchmark interface | Oct 13 | Oct 14 | Benchmark runner design with case, campaign, hardware inventory, run record, outcome mapping and evaluation-profile entry points | Every interface the October 14 benchmark requirements need is named with fields, or listed as an open item for the Benchmark owner | Benchmark requirements (Oct 14); sidecar and test-runner designs | 1.0.1; 6.1.2 | Open items: M1 acceptance scope, model pin, 16 GB host. They stay with the Benchmark owner |
| 8.1.2 | Delete | Finalize RSI and Router integration | | | | | | | Replaced by 8.1.4. Re-point RSI 3.1.3 (section 6) |
| 8.1.5 | Edit | Finalize benchmark runner handoff | Oct 15 | Oct 15 | Benchmark runner page agreed with the Benchmark owner | Open items answered or recorded with an owner role | Benchmark runner design | 8.1.6; 6.1.2 | The runner is never a product dependency |
| 8.1.7 | New | Close one-shot readiness blockers and sync the compact package | Oct 15 | Oct 16 | Design package a coding agent can build from without inventing shared names or fields | Readiness blockers B1 to B14 closed or recorded. Validator passes. Adversarial review findings fixed. Compact package synced | One-shot readiness plan; PRD; design package | 1.1.3; 1.1.4; 1.1.5 | A PRD gap found here stays open and blocks only the affected CC |
| 8.1.3 | Edit | Package ready for coding | Oct 16 | Oct 16 | keep | keep | keep | 1.1.2; 8.1.5; 8.1.7 | keep |

### 8.2: Implementation feedback and M2 design (October 16 to November 6)

| WBS | Action | Name | Start | End | Expected result | Metric | Resources | Depends on | Risk / response |
|---|---|---|---|---|---|---|---|---|---|
| 8.2.1 | Keep | Launch coding and outline next-cycle inputs | Oct 16 | Oct 16 | keep | keep | keep | 8.1.3 | keep |
| 8.2.5 | New | Classify design defects from generated code | Oct 20 | Oct 20 | List separating design defects from implementation defects | Each item links to a contract and an observed output. Design defects get a fix owner | One-shot code; 1.2.1 first-day findings | 1.1.14 | Oct 19 belongs to CC investigation. If the output is late, shift with 1.2.1 |
| 8.2.6 | Edit | Revise M2 architecture draft and interface DAG | Oct 26 | Oct 27 | M2 draft for Generalist, generation, admission and better planning, aligned with the M2 PRD draft | One acyclic interface DAG with ports, check duties, resource needs and open issues | M2 PRD draft (5.2.3); post-code findings; module interfaces | 8.2.5; 5.2.4 | Oct 21 to 23 is left free for verifier assignments. A missing or conflicting PRD section keeps that part of the draft open |
| 8.2.7 | New | Revise draft from verifier and benchmark results | Oct 28 | Oct 28 | M2 draft updated with M1 verification and benchmark findings | Each finding from 1.2.3 and the midweek benchmark review has a design disposition | Verifier results; benchmark midweek review (6.2.6) | 8.2.6; 1.2.3; 6.2.6 | Partial benchmark data is enough. Record what is missing |
| 8.2.2 | Edit | Draft and release architecture feedback form | Oct 29 | Oct 29 | keep | keep | keep | 8.2.7 | keep |
| 8.2.3 | Keep | Index final M1 evidence | Oct 30 | Oct 30 | keep | keep | keep | 1.3; 6.2 | keep |
| 8.2.10 | Edit | Hold M2 architecture review session and revise the package | Nov 2 | Nov 3 | keep | keep | keep | 8.2.2; 8.2.3; 8.2.6; 5.2.7; 1.3; 6.2 | keep |
| 8.2.4 | Edit | Conditional M2 architecture freeze | Nov 3 | Nov 3 | keep | keep | keep | 8.2.10; 5.2.7 | Condition: M2 PRD published (5.2.7) and every blocking item dispositioned. Otherwise the freeze moves and 1.4.1 moves with it |
| 8.2.8 | Keep, optional | Build optional design and PRD integrity report skill | Nov 5 | Nov 6 | keep | keep | keep | 8.2.4 | keep |

### 8.3: November, M3 design (composition) and M2 support

November follows the monthly Architecture pattern, with two support rows placed where critical CC work happens.

| WBS | Action | Name | Start | End | Expected result | Metric | Resources | Depends on | Risk / response |
|---|---|---|---|---|---|---|---|---|---|
| 8.3.1 | Edit | Revise M3 draft for composition and fusion, and share it | Nov 9 | Nov 10 | M3 draft shared with module owners | Draft names composite-node contracts, fusion boundaries and open questions | M2 freeze; M3 PRD scope (5.3.2) | 8.2.4; 1.4.1 | M3 PRD is still a draft. Mark dependent parts open. If one person holds both the CC owner and Architect roles in November, the Architect also joins 1.12.3 on Nov 9, so this row may slip one day |
| 8.3.5 | New | Revise admission contract from the agreed strictness | Nov 11 | Nov 11 | Admission and eligibility contract updated to the 1.12.3 decision | Eligibility record fields and admission checks match the decision | 1.12.3 decision; library contracts | 1.12.3 | Must land before 1.12.2 builds admission |
| 8.3.2 | Edit | Merge module-owner designs and feedback into the M3 draft | Nov 16 | Nov 17 | M3 draft with RSI, Verifier and Router module designs merged | Every module seam has one definition. Conflicts listed with owner roles | RSI 3.3; Verifier 4.3; Router module designs | 8.3.1 | Late module designs are merged at 8.3.7 |
| 8.3.6 | New | Revise Planner and MCTS interface notes | Nov 19 | Nov 19 | Plan proposal and binder contracts confirmed or changed | Plan proposal type and binder unchanged, or the change is recorded as a decision | 1.13.1 results | 1.13.1 | Any type change needs a decision before 1.13.2 uses it |
| 8.3.7 | New | Adjust M3 draft from M2 results and release it for review | Nov 25 | Nov 25 | Revised M3 draft and feedback form released, review session held | Each regression finding has a design disposition. Feedback form sent to every module owner role | 1.13.3 regression; M2 benchmark checkpoint (6.2.9) | 8.3.2; 1.13.3 | No response is not approval |
| 8.3.3 | Edit | Revise from review and align with the M3 PRD | Nov 26 | Nov 27 | M3 package revised from feedback | Every blocking comment has a disposition. PRD alignment checked clause by clause | Review responses; M3 PRD (5.3.3) | 8.3.7; 5.3.3 | Design may be ready before the PRD. It does not freeze until the PRD is final |
| 8.3.4 | Edit | Conditional M3 architecture freeze | Nov 30 | Nov 30 | keep | keep | keep | 8.3.3; 5.3.4; 1.13.5 | Condition: M3 PRD approved (5.3.4). Otherwise the freeze and 1.5.1 move together |

### 8.4 to 8.9: monthly design blocks (December to May)

Replace the long 8.4.1, 8.5.1, 8.6.1, 8.7.1, 8.8.1 and 8.9.1 rows with task rows, each holding the six subtasks below. The month designs the next block. Use the dates in section 5.

| Step | Subtask name (fill in the block) | Expected result | Metric | Depends on |
|---|---|---|---|---|
| 1 | Revise the next-block draft from the last freeze and the PRD scope, and share it | Draft shared with module owners | Draft lists components, seams, carried issues and open PRD questions | Previous freeze; PRD scope row for the next block |
| 2 | Merge module-owner designs and feedback | One merged draft | Every seam has one definition. Conflicts listed with owner roles | Step 1 |
| 3 | Adjust the draft from current-block results and benchmark | Draft reflects measured behaviour | Each finding from the current block has a design disposition | Step 2; current block's integrate subtasks; benchmark checkpoint |
| 4 | Release the revised draft and feedback form, and hold the review session | Review held | Form sent to every module owner role. Responses logged | Step 3 |
| 5 | Revise from review and align with the final PRD | Package ready to freeze | Every blocking comment dispositioned. PRD alignment checked | Step 4; PRD finalized row |
| 6 | Conditional freeze for the next block (milestone) | Frozen package | PRD final and no blocking item open, or the freeze moves | Step 5; PRD milestone; current block's CC gate |

Owner: Architect. Risk / response for every step: "The Architect role may rotate. Dates may shift by a few days. Keep the step order. Design does not freeze until the PRD for the block is final." The PRD rows for 2027 do not exist yet. Write the dependency as "PRD for <block> (row to be added by PRD owner)" and flag it in your report.

## 5. Monthly calendar (December 2026 to June 2027)

Architecture works Monday and Tuesday. CC works Wednesday to Friday. Gaps between Architecture steps are deliberate. Module owners write their designs then, and the PRD owner works in parallel.

| Month (Arch WBS designs the next block) | Arch 1 | Arch 2 | Arch 3 | Arch 4 | Arch 5 | Freeze | CC W1 | CC W2 | CC W3 | CC benchmark | CC gate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Dec 2026 (8.4, designs Jan) | Dec 7 to 8 | Dec 14 to 15 | Dec 21 | Dec 22 | Dec 28 to 29 | Dec 31 | Dec 2 to 4 | Dec 9 to 11 | Dec 16 to 18 | Dec 30 | Dec 31 |
| Jan 2027 (8.5, designs Feb) | Jan 4 to 5 | Jan 11 to 12 | Jan 18 | Jan 19 | Jan 25 to 26 | Jan 29 | Jan 6 to 8 | Jan 13 to 15 | Jan 20 to 22 | Jan 27 to 28 | Jan 29 |
| Feb 2027 (8.6, designs Mar) | Feb 1 to 2 | Feb 8 to 9 | Feb 15 | Feb 16 | Feb 22 to 23 | Feb 26 | Feb 3 to 5 | Feb 10 to 12 | Feb 17 to 19 | Feb 24 to 25 | Feb 26 |
| Mar 2027 (8.7, designs Apr) | Mar 1 to 2 | Mar 8 to 9 | Mar 15 | Mar 16 | Mar 22 to 23 | Mar 31 | Mar 3 to 5 | Mar 10 to 12 | Mar 17 to 19 | Mar 24 to 25 | Mar 31 |
| Apr 2027 (8.8, designs May) | Apr 5 to 6 | Apr 12 to 13 | Apr 19 | Apr 20 | Apr 26 to 27 | Apr 30 | Apr 7 to 9 | Apr 14 to 16 | Apr 21 to 23 | Apr 28 to 29 | Apr 30 |
| May 2027 (8.9, designs Jun) | May 3 to 4 | May 10 to 11 | May 17 | May 18 | May 24 to 25 | May 31 | May 5 to 7 | May 12 to 14 | May 19 to 21 | May 26 to 27 | May 31 |
| Jun 2027 (8.10, new, provisional, designs the next roadmap) | Jun 7 to 8 | Jun 14 to 15 | Jun 21 | Jun 22 | Jun 28 to 29 | Jun 30 | Jun 9 to 11 | Jun 16 to 18 | Jun 23 to 25 | Jun 28 to 29 | Jun 30 |

December note: December 24 to January 1 is a holiday period, and December 1 falls on a Tuesday after the November 30 freeze. December therefore starts Architecture in week 2 and shortens the CC benchmark to one day on December 30. Flag both in the Risk column.

May note: 8.9 also holds the roadmap review that feeds 1.11 on May 31. Keep 8.9.2 "May roadmap evidence gate" as the step 6 milestone.

## 6. Dependency edits outside 1.x and 8.x

Report these to the user before saving. Change only the "Depends on" cell.

| Row | Current | Change to | Reason |
|---|---|---|---|
| RSI 3.1.3 | 3.1.1; 3.1.2; 8.1.2 | 3.1.1; 3.1.2; 8.1.4 | 8.1.2 is deleted |
| RSI 3.2.1 | 3.1.3; real integration: 1.2.2 | 3.1.3; optional: 1.2.2 | 1.2.2 is conditional |
| Verifier 4.2.7 | mentions optional Cluster Mode | no change, flag only | The Planner is now in the core. The Verifier owner may want to drop "optional" |

## 7. Checks before you finish

1. Every WBS ID is unique. Every ID in a Depends on cell exists, except the flagged 2027 PRD placeholders.
2. No dependency cycle. No subtask starts before a finish-to-start dependency ends, except the documented October 20 overlap (8.2.5 uses 1.2.1 first-day findings).
3. No subtask is longer than three working days. Milestones are zero days.
4. Parent rows roll up and show dates, not serial numbers. Rows 8.0, 8.1, 8.2 and 8.3 currently show numbers such as 46308. Fix the cell format.
5. The Timeline tab shows a bar for every subtask and nothing for deleted rows.
6. Expected result, Metric and Risk text contains no dates.
7. No personal names in 1.x or 8.x rows.
8. The boilerplate risk "Missing output, access or evidence blocks the affected claim..." no longer appears on rows that have a specific risk above.
9. Architecture has a row or a documented gap on every working day from October 13 to November 30. The documented gaps are October 19 and October 21 to 23, plus the module-owner design weeks in November.

## 8. Things that are conditional

| Row | Condition | If not met |
|---|---|---|
| 1.2.2 | Screening runs by October 20 | Mark Not needed. RSI uses the synthetic parent |
| 8.2.4 | M2 PRD published and blocking items dispositioned | Freeze moves. November CC rows move by the same delay |
| 8.3.4 | M3 PRD approved | Freeze moves. 1.5.1 moves |
| 8.4 to 8.10 step 6 | PRD for the next block final | Freeze moves. The next block's CC W1 subtask moves |
| 8.2.8 | Spare capacity in early November | Drop it. It blocks nothing |
| 1.13.3 strictness | Measured admission cost or failure rate differs from the 1.12.3 estimate | Re-decide with the CC owner, RSI owner and Benchmark owner |
