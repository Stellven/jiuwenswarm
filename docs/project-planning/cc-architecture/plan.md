# Human plan: CC architecture and M1 coordination

**Planning date:** October 14, 2026. **October 30 target:** demonstrate the bounded main path from Compiler through Planner and selected downstream CCs to Delivery, using the existing fixed Codex execution route, with a benchmark report and indexed artifact dataset. RSI and new Model Router integration are excluded from this date’s acceptance criteria; neither may block the demo. This is a bounded demonstration target, not evidence that the confirmed PRD’s broader M1 completion gate has been met. **Current status:** the available main path uses generic Leader/SwarmFlow and is not yet an integrated AI4Research Planner. The one-shot trial uses four fixed roles and worker-data replay, not interactive conversation; its baseline evidence does not replace the target. This is a coordination plan, not a coding-task register. Product requirements remain owned by their authors; use the maintained design and supplied PRD for implementation authority.

## October path

| Dates | Outcome | Owner roles | Inputs and evidence | Risk and boundary |
|---|---|---|---|---|
| Oct 13–14 | Close the October core design and benchmark-runner/test interfaces. Retain the already received RSI and Model Router designs as future references; record their non-blocking boundaries without further feature design or implementation before core acceptance. | Architect; Benchmark owner; Verifier owner | Existing module designs; supplied PRD; returned benchmark/test interfaces; shared gates | Benchmark interface work serves the core. No human effort is allocated to Router or RSI changes before the core gate; existing designs remain available and non-blocking. |
| Oct 13–14 | Align four CC planning groups: Compiler (Intent and Requirement), Planner, bounded downstream CCs (Search through Delivery), and shared checking/gates. Link the shared checking profile once. | Architect; CC owner | Existing design records and task register | Represent the groups as subtasks in the top CC section. This replaces eleven schedule references only; it does not replace existing task identities. |
| Oct 15–16 | Finalize and freeze the bounded core architecture; leave Router and RSI implementation for after core acceptance. | Architect | Oct13–14 core-alignment findings; supplied PRD; core module interfaces | One core architecture handoff with blocking gaps resolved or dispositioned. Architecture consumes but does not author the PRD. |
| Oct 15–16 | Finalize benchmark-runner architecture and freeze the product implementation package before coding starts. | Architect; Benchmark owner; Verifier owner | Returned benchmark/test interfaces; independent cases; shared checking profile | Keep the Dockerized benchmark sidecar as separate development tooling and an ordinary client; it does not block product startup or acceptance. |
| Oct 16 | Start the one-shot M1 implementation with pinned inputs and record its configuration. | CC owner; Architect | Frozen package; revised integrated main-path design; agent runtime and access | The replay baseline is evidence about current status, not completion of the integrated main-path target. |
| Oct 19–20 | Review visible implementation output and record post-code findings. | CC owner; Architect | Pinned input, output, generated code and run evidence | Link each issue to expected and observed behavior, owner role, and disposition. Missing output is not completion. |
| Oct 21–23 | Complete existing verifier assignments and capture architecture findings. | CC owner; Verifier owner | Nine existing checks; independent expected cases; actual logs | Investigation notes are subtasks linked to these assignments; do not count shared evidence review twice. Required checks take priority. |
| Oct 26–28 | Review test and benchmark results; record post-test findings. | CC owner; Benchmark owner; Architect | Independent cases/labels, verifier records and runner output | Distinguish design gaps, implementation defects, environment blocks and accepted limits. RSI results are not needed for the October 30 verdict. |
| Oct 29 | Draft and release the M1 feedback form; request team inputs for the review. | Architect; CC owner | Post-code, verifier and post-test records | Form distinguishes design gaps, implementation defects, environment blocks and limits. Do not claim full fidelity from declaration/output checks alone. |
| Oct 30 | Demonstrate the bounded Compiler → Planner → selected downstream CCs → Delivery path over the existing fixed Codex route, publish its benchmark report, and index evidence for this bounded target. | CC owner; Architect; Benchmark owner | Pinned implementation/configuration; artifact dataset; run outputs; protected checks; benchmark report | RSI and new Model Router integration are explicitly out of scope for this acceptance gate. Record what is integrated and any shortfall. The four-role replay is not interactive conversation. The approved semantic assessment deviation reduces fidelity assurance. Do not label this bounded demonstration as full PRD M1 completion. |
| Nov 2–3 | Review M1 findings and returned team feedback; conditionally freeze the next architecture package. | Architect; CC owner; module-owner roles | M1 evidence; feedback returned after Oct30; available, aligned M2 PRD from its product owner | Freeze only if PRD and blocking interfaces are available and aligned. Otherwise keep the gate open and move dependent implementation work. |

The approved PRD deviation limits semantic assessment to declared information and produced output. It does not establish source-level or full intent-fidelity review, so fidelity assurance is reduced. Record this limit with M1 evidence and the verdict.

## November delivery sequence: 15 human-days

Each subtask has a one-to-three working-day window and a stop/go evidence boundary. Work proceeds in order; do not start a dependent feature before the previous boundary is accepted. The dates allocate 15 human-days total.

| Dates | Subtask and outcome | Owner roles | Acceptance evidence and dependency |
|---|---|---|---|
| Nov 4–6 | Integrate the Generalist with accepted interfaces and close blocking gaps. | CC owner | One bounded request passes declared I/O and assigned checks; record limits. Requires conditional architecture freeze and available Generalist output. |
| Nov 9–10 | Generate one capsule candidate and hand it to isolated RSI evaluation. | CC owner; RSI owner | Pin source, declaration, output and parent/check profile; record RSI result or attributable blocked/no-gain result. RSI cannot block the core path. |
| Nov 12–13 | Automate protected library eligibility/admission for the candidate. | CC owner; Verifier owner | Durable eligible/ineligible result with provenance and required check evidence. Under the approved November planning scope, an eligible candidate becomes selectable by future plans without a separate human activation step; confirm this boundary in the aligned M2 PRD/design before implementation. Frozen-run checks and dispatch authority remain protected. |
| Nov 16–18 | Improve bounded planning over eligible candidates. | CC owner; Benchmark owner | Compare with the October baseline on fixed feasible and invalid cases; record valid-plan rate, failures, time/cost and exact pins. Deterministic validation and freeze remain authoritative. |
| Nov 19–20 | Add bounded MCTS candidate ordering and evaluate it against the improved planner. | CC owner; Benchmark owner | Fixed search/time limits and same case set; retain baseline if candidate misses required outcomes. MCTS cannot waive checks or edit a frozen/in-flight DAG. |
| Nov 23–24 | Run integrated regression and publish the feature evidence index. | Verifier owner; Benchmark owner | Each agreed case has an expected/observed result, gate trace, pins and limitation; failures remain visible. |
| Nov 26 | Set December M3 scope, entry criteria, dependencies and owners by role. | Architect | Readiness record based on November evidence. Composition is reserved for December M3, not implied by November acceptance. |

**Optional integrity-check skill:** Nov5–6 is a shared, deferrable window for a minimal report-only skill using pinned PRD/design sources and seeded cases. It adds no committed human-days to the 15-day sequence; use only residual shared capacity, and defer or drop it if verifier or integration work needs that capacity. It is not a product, delivery, architecture-freeze or feature-acceptance prerequisite.

**Nov 30 gate:** review the M1 main-path evidence, November feature records and December readiness. The gate judges recorded outcomes, not task labels. Missing prerequisites keep the affected decision open.

## Capacity and scheduling rules

- Dates are work windows, not proof that every parallel label consumes a full day. Reuse shared outputs and agent-produced drafts; record human review effort once.
- Keep each implementation, investigation or review subtask within three working days. Split longer work at an acceptance boundary; use role labels until availability is confirmed.
- Investigation notes are subtasks linked to the evidence-producing work, not standalone resource rows that duplicate effort.
- If required code, access, cases or interfaces are missing, hold the dependent gate, reduce optional scope or move the dates. Do not claim unavailable evidence as a pass.
- The October benchmark sidecar remains development tooling and does not become a product startup, test, or release prerequisite. RSI and new Model Router integration receive no human implementation or feature-refinement allocation before the core gate; already received design material remains reference-only during that period.

## Combined capacity and live merge

The CC feature sequence allocates 15 working days. Architecture-only windows add the review session (Nov2–3), draft completion (Nov11) and package preparation (Nov25 and Nov27): five further working days. Architecture review on overlapping feature dates consumes the same evidence-review work, not another full allocation. The integrity skill remains optional residual-capacity tooling and is deferred before core feature work. Milestones are decision points, not additional multi-day builds.

The CC and Architecture changes were merged into the live workbook. A later whole-workbook replacement added/changed PRD resources, and those edits were preserved. Before any further sheet change, take a fresh identity snapshot and reconcile by record identity; external predecessor IDs still resolve in the team workbook.
