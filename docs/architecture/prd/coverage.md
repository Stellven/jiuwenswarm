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
