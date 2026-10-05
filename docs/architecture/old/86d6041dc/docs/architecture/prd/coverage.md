---
type: index
status: draft
version: 2
owner: muk
sources: [../../product/prd-m1-full-2026-10-02.txt, ../../product/SOURCE_FREEZE.md]
provides: [architecture.prd_coverage]
consumes: [m1.run_plan, system.seams]
depends_on: [../m1/pipeline.md, ../seams.md, ../system/coder-requirements.md]
tags: [prd, coverage, ownership, m1]
---

# Frozen M1 clause and responsibility coverage

The [source freeze](../../product/SOURCE_FREEZE.md) fixes scope. This map is navigation, not executed acceptance. Exact numbered headings are in [clause inventory](clause-inventory.md). The source blacklist applies even when a heading contains whitelist items. [Coder requirements](../system/coder-requirements.md) checks engineering completeness.

| Source area | Track | Canonical design owners | Required observation |
|---|---|---|---|
| 1 product goals and ownership | all | [architecture](../architecture.md), [policies](../policies.md), [tracks](../system/experiments.md) | fixed production, required RSI and isolated experiments separately identified |
| 2 domain, integrity, autonomy, evidence and non-goals | all | [Brief](../types/research-brief.md), [pipeline](../m1/pipeline.md), [environment](../system/environment.md), [Gate](../capsule/gate-host.md), [RSI](../capsule/rsi-engine.md) | bounded scientific lane and no autonomous repair or unapproved scope |
| 3.0 Codex adapter | production | [integration](../system/integration.md), [model bridge](../system/environment.md#model-bridge) | protected local subscription route and bounded failure |
| 3.1 intake | production | [intake](../types/intake.md), [extraction](../m1/extract-text.md), [workstation](../system/workstation.md) | permitted local request/assets, deduplication and provenance |
| 3.2 requirement compilation | production | [Brief capability](../m1/requirement-capsule.md), [intent hints](../m1/intent-capsule.md), [Brief type](../types/research-brief.md), [Brief Gate](../m1/brief-gate.md) | objective, ambiguities, constraints and acceptance compiled faithfully |
| 3.3 search/ideation | production | [search](../m1/search-capsule.md), [ideas](../types/idea-set.md), [search Gate](../m1/search-gate.md) | bounded local/scholarly evidence and referenced candidate ideas |
| 3.4 screening | production | [Screening](../m1/screening.md), [ranking](../m1/op-rank-opportunities.md), [card](../types/opportunity-card.md), [Screening Gate](../m1/screening-gate.md) | fixed dimensions, deterministic selection and rejection evidence |
| 3.5 hypothesis | production | [Hypothesis](../m1/hypothesis.md), [Blueprint](../types/hypothesis-blueprint.md), [protocol](../m1/measurement-protocol.md) | baseline/treatment and scientific boundaries pre-registered |
| 3.6 POC | production | [POC](../m1/poc.md), [bundle](../types/poc-bundle.md), [workspace](../m1/op-workspace-io.md) | permitted files and requirements packaged; Builder does not install or perform science |
| 3.7 scientific execution | production | [benchmark](../m1/benchmark.md), [payload](../types/benchmark-payload.md), [measurement](../m1/measurement-protocol.md), [process boundary](../capsule/process-boundary.md) | one frozen provision, both arms, trusted samples and raw capture |
| 3.8 scientific evaluation | production | [Evaluation](../m1/evaluation.md), [verdict](../types/evaluation-verdict.md), [research Gates](../m1/research-gates.md) | frozen classification, scientific failure separate from infrastructure failure |
| 3.9 report and delivery | production | [report/publication](../m1/delivery.md), [report type](../types/research-report.md), [storage](../system/storage.md) | negative/inconclusive science reported; atomic publication and retrieval |
| 4.1 CC | shared | [Declaration](../capsule/fields.md), [tools](../capsule/tools.md), [admission](../capsule/admission.md), [library](../capsule/library.md), [runner](../capsule/runner.md) | admitted exact versions and whitelist enforcement separated from future fields |
| 4.2 Gate/Verifier | shared | [evidence](../types/evidence-bundle.md), [shared verifier](../capsule/gate-capsules.md), [Gate host](../capsule/gate-host.md), [Verification](../schemas/verification-record.md) | checks and routing verdicts persisted before release |
| 4.3 models/routing | baseline / isolated | [routing adaptation](../model-routing/README.md), [experiments](../system/experiments.md), [model client](../capsule/runner.md#the-model-client-contract-m05) | endpoint choice never selects a capability; access gating preserved |
| 4.4.1–4.4.10 RSI, hidden evaluation and adversarial guardrails | required offline | [RSI engine](../capsule/rsi-engine.md), [oracle](../capsule/fixture-oracle.md), [Candidate](../schemas/candidate.md), [activation](../capsule/library.md) | quota/mutation limits, private evaluation, violations and manual activation |
| 4.5 Data Foundation | shared | [seam](../seams.md#data-foundation), [storage](../system/storage.md), [records](../system/records.md), [benchmark export](../system/benchmark-export.md) | lossless required evidence; rebuildable views/export |
| 4.6 Harness | production / shared | [nodes](../system/nodes.md), [lifecycle](../system/lifecycle.md), [runner](../capsule/runner.md) | frozen execution, durable release and explicit restart |
| 4.7 intention | production / isolated | [Brief](../m1/requirement-capsule.md), [planner](../system/planner.md), [experiments](../system/experiments.md) | static compiler; experimental dialogue remains pre-dispatch |
| 4.8 planner | isolated | [planner](../system/planner.md), [run plan](../types/run-plan.md), [freeze](../capsule/toolchain.md) | native Leader proposal and validation; no live mutation/cycles/peer-agent redteam |
| 4.9 Builder | production / isolated | [POC](../m1/poc.md), [process boundary](../capsule/process-boundary.md), [Code Mode](../system/experiments.md) | executable synthesis isolated from analytical stages |
| 5.1 visibility | workstation | [observability](../system/observability.md), [workstation](../system/workstation.md) | run state, trace, statistics and artifact joins |
| 5.2 installation | workstation | [environment](../system/environment.md), [workstation](../system/workstation.md) | reproducible install/bootstrap/doctor/startup |
| 5.3 local interfaces | workstation | [workstation](../system/workstation.md), [integration](../system/integration.md) | CLI/Web/TUI/tmux share run APIs |
| 5.4 accounts/security | shared | [environment](../system/environment.md), [workstation](../system/workstation.md), [oracle](../capsule/fixture-oracle.md) | local tokens and credentials; generated code cannot read protected material |
| 5.5 channels | workstation | [workstation](../system/workstation.md), [entry](../system/integration.md) | local supported interfaces; external messaging excluded |
| 5.6 configuration/evaluation | shared / isolated | [configuration](../system/environment.md), [experiments](../system/experiments.md), [manifest](../system/records.md), [headless export](../system/benchmark-export.md) | effective frozen settings; ablation cannot satisfy production acceptance |
| 5.3.1 headless entry and 5.6.5 development/evaluation integration | shared / isolated | [benchmark export](../system/benchmark-export.md), [headless lifecycle](../system/lifecycle.md), [experiments](../system/experiments.md) | standard invocation and labelled deviations; mandatory-control ablations cannot satisfy production acceptance |
| 6 implementation order | all | [build order](../system/build-order.md), [handoff](../system/handoff.md), [verification](../system/verification.md) | connected slices, full baseline, required RSI, then isolated experiments |

## Workstream reconciliation

The explicit Docker deployment amendment is traced separately from unchanged frozen-source clauses in [SOURCE_FREEZE](../../product/SOURCE_FREEZE.md) and [R10](../decisions.md). [Deployment](../system/deployment.md), [model auth](../system/model-auth.md) and [benchmark transport](../system/benchmark-export.md) own image/process/credential/endpoints. R11/R12 record the dedicated credential profile and source-permitted isolated ablations. These are architecture choices with implementation checks, not claims that source files were rewritten or runtime mechanisms were tested.

Muk owns architecture and CC shared interfaces. Ramika's frozen PRD supplies research and Gate intent; Xiaoyang's router supplies catalog/endpoint design; Suraj supplies Data Foundation views; Saurav supplies RSI and external benchmark inputs. Adopted boundaries compare both proposals without waiting for routine owner permissions.

The [Verifier model-selection proposal](../../product/verifier-model-selection-proposal-2026-10-02.md) permits isolated recommendation and unmodified-model integration after access approval. Training, quality claims from functional examples and production-route replacement are excluded. It consumes the existing semantic-assessment contract and cannot change Gate authority.

Each source heading maps to the relevant row here; its individual whitelist/blacklist and expected observation are checked during fresh source review. A row is not proof that every linked contract is checked. Remaining runtime/platform/method evidence is tracked in [validation obligations](../open-issues.md). Saurav's pending schema changes the provisional export adapter only.

## Phases and implementation stages

These rows account for the frozen PRD's separate phase and construction-stage axes. They route to the owning design; they do not replace its rules or assert implementation acceptance.

| PRD phase (1.3) | Owning design and handoff | Acceptance boundary |
|---|---|---|
| Track 1: Phase 1 static research baseline | [Fixed pipeline](../m1/pipeline.md), [Codex bridge](../system/environment.md#model-bridge), [lifecycle](../system/lifecycle.md), [production story](../stories/01-research-workflow.md) | Release-critical static route and workflow; valid negative science reaches delivery |
| Track 2: required offline RSI validation | [RSI engine](../capsule/rsi-engine.md), [oracle](../capsule/fixture-oracle.md), [RSI story](../stories/06-offline-rsi.md) | Required M1 acceptance; isolated from live DAG and active-alias mutation |
| Track 3: Phase 2 dynamic test tracks | [Experimental whitelist](../system/experiments.md), [planner](../system/planner.md), [planner story](../stories/07-experimental-planner.md) | Isolated, non-blocking; external access approval precedes real alternate-model integration |

| PRD implementation stage | Design routing | Boundary that must be demonstrated by implementation |
|---|---|---|
| 0 (6.3): runtime unblocker and local configuration | [Integration](../system/integration.md), [environment](../system/environment.md), [auth](../system/model-auth.md), [deployment](../system/deployment.md) | Bounded Codex request under the selected secured configuration |
| 1 (6.4): governed execution backbone | [Runner](../capsule/runner.md), [Gate](../capsule/gate-host.md), [storage](../system/storage.md), [records](../system/records.md), [lifecycle](../system/lifecycle.md) | Valid A releases B; invalid A blocks B; headless halt returns durable machine status |
| 2 (6.5): intake, Brief and static DAG | [Intake](../types/intake.md), [Brief capability](../m1/requirement-capsule.md), [fixed plan](../m1/pipeline.md) | Submitted assets become validated Brief and frozen static bindings |
| 3 (6.6): evidence to hypothesis | [Search](../m1/search-capsule.md), [Screening](../m1/screening.md), [Hypothesis](../m1/hypothesis.md) | Referenced ideas, one selected opportunity and pre-registered hypothesis cross real Gates |
| 4 (6.7): Builder and POC | [POC](../m1/poc.md), [workspace](../m1/op-workspace-io.md), [process boundary](../capsule/process-boundary.md) | Bounded valid executable bundle and build evidence; no autonomous repair |
| 5 (6.8): benchmarking and scientific evaluation | [Benchmark](../m1/benchmark.md), [protocol](../m1/measurement-protocol.md), [Evaluation](../m1/evaluation.md), [science story](../stories/04-scientific-execution.md) | Positive and negative valid execution preserve separate scientific/infrastructure verdicts |
| 6 (6.9): delivery and complete research run | [Delivery](../m1/delivery.md), [publication/recovery story](../stories/03-durable-recovery.md), [production story](../stories/01-research-workflow.md) | Complete request-to-report evidence and committed final result |
| 7 (6.10): operational shell | [Workstation](../system/workstation.md), [observability](../system/observability.md), [benchmark endpoints](../system/benchmark-export.md), [client story](../stories/08-benchmark-and-workstation.md) | Install, initialize, execute, inspect and retrieve through supported local interfaces |
| 8 (6.11): offline RSI | [RSI engine](../capsule/rsi-engine.md), [oracle](../capsule/fixture-oracle.md), [admission](../capsule/admission.md), [library activation](../capsule/library.md) | Bounded improvement, hidden-data defense, guardrail evidence, human activation and rollback |
| 9 (6.12): isolated Phase 2 tests | [Experiments](../system/experiments.md), [planner](../system/planner.md), [routing](../model-routing/README.md) | Permitted variants compared against operational baseline without modifying production acceptance |
| Handoff (6.13) | [Authority index](../authority.md), [coder requirements](../system/coder-requirements.md), [module handoff](../system/handoff.md) | Every boundary has canonical fields, behavior, placement, evidence and validation hooks |

[Build order](../system/build-order.md) owns the detailed construction dependencies. Its numbered engineering slices are not PRD stage identifiers; use the clause IDs above when allocating downstream tasks. [Clause inventory](clause-inventory.md) remains the exact numbered-heading list, including excluded/future headings. Whitelist/blacklist checks require reading each heading's body, not assuming every inventoried heading is active M1 work.

### Coverage audit limitations, October 5

The architecture has owner links for all nine research stages, all three tracks and all ten construction stages. This navigation audit reread the frozen phase model and section 6 stage bodies. It does not turn the existing grouped map into a claim of line-by-line requirement satisfaction. In particular, stage 8 explicitly requires protected-set separation, guardrail execution and rollback evidence; stage 9 preserves the external-access gate and non-blocking status. Their linked designs and implementation obligations remain subject to fresh contract/source review. [Boundary cases](../system/boundary-cases.md) routes negative scenarios; actual commands/results belong to the coding workstream.
