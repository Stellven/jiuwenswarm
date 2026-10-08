# Contract index

**AI reference.** Find an artifact by name, then read its definition and consumer rules. Start with [reference principles](README.md); humans start with [the package README](../README.md). Current contract version is `1.0.0`.

## Exact schemas

| Contract | Definition | Producer → consumers | Examples |
|---|---|---|---|
| `capsule-declaration` | [Schema](schemas/capsule-declaration.schema.json) | CC author/importer → admission, discovery/binder, runner, RSI | [Capsule_Declaration.json](examples/Capsule_Declaration.json) |
| `deterministic-check-result` | [Schema](schemas/deterministic-check-result.schema.json) | protected check runner → review-context builder, protected gate | [Intent_Checks.json](examples/Intent_Checks.json), [Topic_Checks.json](examples/Topic_Checks.json), [Science_Checks.json](examples/Science_Checks.json), [Requirements_Checks.json](examples/Requirements_Checks.json) |
| `gate-decision` | [Schema](schemas/gate-decision.schema.json) | protected gate host → durable run-state, scheduler, inspection | [Gate_Decision.json](examples/Gate_Decision.json), [Gate_Topic_Halt.json](examples/Gate_Topic_Halt.json), [Gate_Science_Pass.json](examples/Gate_Science_Pass.json), [Gate_Requirements_Pass.json](examples/Gate_Requirements_Pass.json) |
| `intent-ir` | [Schema](schemas/intent-ir.schema.json) | Intent CC → deterministic checks, Intent verifier, Requirements after acceptance | [Intent_IR.json](examples/Intent_IR.json), [Intent_Topic_Only.json](examples/Intent_Topic_Only.json), [Intent_Contradictory.json](examples/Intent_Contradictory.json) |
| `node-execution-contract` | [Schema](schemas/node-execution-contract.schema.json) | protected binder → runner, check-plan builder, gate | [Node_Contract.json](examples/Node_Contract.json), [Requirements_Node_Contract.json](examples/Requirements_Node_Contract.json), [Topic_Node_Contract.json](examples/Topic_Node_Contract.json), [Science_Node_Contract.json](examples/Science_Node_Contract.json) |
| `research-brief` | [Schema](schemas/research-brief.schema.json) | Requirements CC → Requirements verification, static binder/planner, research CCs | [Research_Brief.json](examples/Research_Brief.json) |
| `verifier-assessment` | [Schema](schemas/verifier-assessment.schema.json) | assigned read-only verifier CC → protected gate | [Intent_Assessment.json](examples/Intent_Assessment.json), [Topic_Assessment.json](examples/Topic_Assessment.json), [Science_Assessment.json](examples/Science_Assessment.json), [Requirements_Assessment.json](examples/Requirements_Assessment.json) |

[Shared schema definitions](schemas/common.schema.json) provide exact-byte references, source spans and common shapes. Schema validity alone establishes neither authorship, permission, scientific truth nor runtime eligibility.

## Major field contracts

These define required fields and behavior without an exact schema for every type. Missing or incompatible mandatory content blocks the named consumer. An absent example below is not an untested runtime PASS.

| Artifact | Fields and behavior | Producer → consumers | Worked record |
|---|---|---|---|
| `accepted-output` | [Definition](field-catalog.md#accepted-output) | protected durable state → scheduler, client | Field contract; no dedicated fixture |
| `activation-record` | [Definition](field-catalog.md#activation-record) | authorized human through protected library → future selection, audit | [RSI_Activation.json](examples/RSI_Activation.json), [RSI_Rollback.json](examples/RSI_Rollback.json) |
| `artifact-envelope` | [Definition](field-catalog.md#artifact-envelope) | trusted capture → checking, export, runner | Field contract; no dedicated fixture |
| `benchmark-payload` | [Definition](field-catalog.md#benchmark-payload) | Benchmark with protected provisioner/executor → Evaluation, checking, Delivery | [Benchmark_Payload.json](examples/Benchmark_Payload.json) |
| `bound-check-plan` | [Definition](field-catalog.md#bound-check-plan) | protected guard resolver → checks, review builder, gate | [Check_Plan.json](examples/Check_Plan.json), [Requirements_Check_Plan.json](examples/Requirements_Check_Plan.json), [Science_Check_Plan.json](examples/Science_Check_Plan.json), [Topic_Check_Plan.json](examples/Topic_Check_Plan.json) |
| `candidate-provenance` | [Definition](field-catalog.md#candidate-provenance) | candidate builder with protected capture → library admission, human, RSI | [RSI_Child_Candidate.json](examples/RSI_Child_Candidate.json) |
| `candidate-set` | [Definition](field-catalog.md#candidate-set) | Search and Ideation CC → Screening, checking | [Candidate_Set.json](examples/Candidate_Set.json) |
| `client-cancellation` | [Definition](field-catalog.md#client-cancellation) | client and protected controller → runner, client | Field contract; no dedicated fixture |
| `client-error` | [Definition](field-catalog.md#client-error) | application → clients | Field contract; no dedicated fixture |
| `client-readiness` | [Definition](field-catalog.md#client-readiness) | application → browser, CLI, benchmarker, sidecar | Field contract; no dedicated fixture |
| `client-retrieval` | [Definition](field-catalog.md#client-retrieval) | scoped client and application → inspection, export | Field contract; no dedicated fixture |
| `client-status` | [Definition](field-catalog.md#client-status) | control plane → clients | Field contract; no dedicated fixture |
| `client-submission` | [Definition](field-catalog.md#client-submission) | scoped client → control plane | Field contract; no dedicated fixture |
| `delivery-manifest` | [Definition](field-catalog.md#delivery-manifest) | Delivery CC with trusted export → user, checking, client | [Delivery_Manifest.json](examples/Delivery_Manifest.json) |
| `environment-lock` | [Definition](field-catalog.md#environment-lock) | protected environment preparation → Hypothesis, Builder, provisioner | [Environment_Lock.json](examples/Environment_Lock.json) |
| `evaluation-verdict` | [Definition](field-catalog.md#evaluation-verdict) | Scientific Evaluation CC → Delivery, checking | [Evaluation_Verdict.json](examples/Evaluation_Verdict.json) |
| `frozen-graph` | [Definition](field-catalog.md#frozen-graph) | protected freeze → scheduler, binder | Field contract; no dedicated fixture |
| `hypothesis-blueprint` | [Definition](field-catalog.md#hypothesis-blueprint) | Hypothesis CC → Builder, Benchmark, Evaluation, checking | [Hypothesis_Blueprint.json](examples/Hypothesis_Blueprint.json) |
| `invocation-observation` | [Definition](field-catalog.md#invocation-observation) | protected runner → gate, review, Run Bundle | [Invocation_Observation.json](examples/Invocation_Observation.json), [Topic_Observation.json](examples/Topic_Observation.json), [Science_Observation.json](examples/Science_Observation.json), [Requirements_Invocation_Observation.json](examples/Requirements_Invocation_Observation.json) |
| `library-admission` | [Definition](field-catalog.md#library-admission) | protected library admission → eligibility, human | [RSI_Admission.json](examples/RSI_Admission.json), [RSI_Parent_Admission.json](examples/RSI_Parent_Admission.json) |
| `model-route` | [Definition](field-catalog.md#model-route) | protected router → audited bridge, observations | Field contract; no dedicated fixture |
| `opportunity-card` | [Definition](field-catalog.md#opportunity-card) | Screening CC → Hypothesis, checking | [Opportunity_Card.json](examples/Opportunity_Card.json) |
| `plan-proposal` | [Definition](field-catalog.md#plan-proposal) | static template or bounded planner → binder, plan checking | Field contract; no dedicated fixture |
| `poc-manifest` | [Definition](field-catalog.md#poc-manifest) | Builder CC with trusted capture → Benchmark, checking, Delivery | [POC_Manifest.json](examples/POC_Manifest.json) |
| `qualified-intake` | [Definition](field-catalog.md#qualified-intake) | protected intake → Intent CC, Requirements CC | [Qualified_Intake.json](examples/Qualified_Intake.json), [Topic_Qualified_Intake.json](examples/Topic_Qualified_Intake.json) |
| `resource-snapshot` | [Definition](field-catalog.md#resource-snapshot) | protected resolver → Hypothesis, Builder, Benchmark | [Baseline_Resource.json](examples/Baseline_Resource.json), [Validation_Resource.json](examples/Validation_Resource.json) |
| `review-context` | [Definition](field-catalog.md#review-context) | protected context builder → read-only verifier | [Review_Context.json](examples/Review_Context.json), [Topic_Review_Context.json](examples/Topic_Review_Context.json), [Science_Review_Context.json](examples/Science_Review_Context.json), [Requirements_Review_Context.json](examples/Requirements_Review_Context.json) |
| `rsi-attempt` | [Definition](field-catalog.md#rsi-attempt) | protected RSI controller → guard, referee, evidence | [RSI_Attempt_01.json](examples/RSI_Attempt_01.json) |
| `rsi-evidence-export` | [Definition](field-catalog.md#rsi-evidence-export) | trusted audience-filtered builder → authorized human, library | [RSI_Evidence_Export.json](examples/RSI_Evidence_Export.json) |
| `rsi-loop-feedback` | [Definition](field-catalog.md#rsi-loop-feedback) | custodian → proposer | [RSI_Loop_Feedback.json](examples/RSI_Loop_Feedback.json) |
| `rsi-referee-evidence` | [Definition](field-catalog.md#rsi-referee-evidence) | protected independent referee → restricted admission, evidence builder | [RSI_Referee_Evidence.json](examples/RSI_Referee_Evidence.json) |
| `rsi-target-profile` | [Definition](field-catalog.md#rsi-target-profile) | protected target owner → controller, guard, referee | [RSI_Target_Profile.json](examples/RSI_Target_Profile.json) |
| `run-bundle` | [Definition](field-catalog.md#run-bundle) | protected evidence builder → inspection, authorized export | Field contract; no dedicated fixture |
| `scorecard` | [Definition](field-catalog.md#scorecard) | derived observation builder → analysis, planner | Field contract; no dedicated fixture |
| `screening-result` | [Definition](field-catalog.md#screening-result) | Screening CC and deterministic helper → selection, checking, RSI | [Screening_Result.json](examples/Screening_Result.json) |
| `security-clearance` | [Definition](field-catalog.md#security-clearance) | authorized security human through protected RSI controller → new-session eligibility, audit | [RSI_Security_Clearance.json](examples/RSI_Security_Clearance.json) |

[Connected planning nodes](examples/Planning_Nodes.json) show accepted Brief inputs and compatible future named ports; they are a partial typed example, not a complete accepted research plan.

## Shared types

[Citation](field-catalog.md#citation) · [ComparisonRule](field-catalog.md#comparisonrule) · [FutureInput](field-catalog.md#futureinput) · [Idea](field-catalog.md#idea) · [IdeaScore](field-catalog.md#ideascore) · [Limits](field-catalog.md#limits) · [MetricFinding](field-catalog.md#metricfinding) · [MetricObservation](field-catalog.md#metricobservation) · [MetricRule](field-catalog.md#metricrule) · [MissingEvidence](field-catalog.md#missingevidence) · [ModelIdentity](field-catalog.md#modelidentity) · [NamedFile](field-catalog.md#namedfile) · [PlanInput](field-catalog.md#planinput) · [PlanNode](field-catalog.md#plannode) · [PlanOutput](field-catalog.md#planoutput) · [Prerequisite](field-catalog.md#prerequisite) · [RSIPair](field-catalog.md#rsipair) · [RSIScore](field-catalog.md#rsiscore) · [Ranking](field-catalog.md#ranking) · [Ref](field-catalog.md#ref) · [SplitIdentities](field-catalog.md#splitidentities) · [Usage](field-catalog.md#usage)

## Read by responsibility

| Responsibility | Start here |
|---|---|
| Intent and Requirements | [Meaning, checks and consumer obligations](intent-and-requirements.md) |
| Verification and control | [Check / assessment / protected decision](checking.md) |
| Execution and typed connections | [Node contract](node-execution.md), [planning fields](field-catalog.md#plan-proposal) |
| Research artifacts | [Field family](field-catalog.md#research-artifacts), [linked negative-science example](examples/README.md#linked-research-path) |
| Clients and model routing | [Field family](field-catalog.md#client-and-model-boundaries) |
| RSI, admission and clearance | [Field family](field-catalog.md#offline-rsi-records), [security clearance](field-catalog.md#security-clearance), [linked RSI example](examples/README.md#linked-offline-rsi-path) |

[Machine catalog](catalog.json) records exact IDs, versions and applicable phases. [Named inventory](field-contracts.json) is authoritative for field spelling/types. [Other contracts](other-contracts.md) prescribe relational and failure behavior.
