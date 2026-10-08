# Contract index

Find the shared fields and purpose here. [Compiler build](../builds/intention-compiler/README.md), [verification obligations](compiler-verification.md), [field tables](field-catalog.md) and [examples](examples/README.md) explain use. Exact schemas are selected critical boundaries, not a schema inventory for every internal datatype.

## Critical exact boundaries

| Contract | Version | Authoritative reference | Producer → consumers | Examples |
|---|---|---|---|---|
| capsule-declaration | 1.0.0 | [Schema](schemas/capsule-declaration.schema.json) | CC author/importer → admission, discovery/binder, runner, RSI | [Capsule_Declaration.json](examples/Capsule_Declaration.json) |
| deterministic-check-result | 1.0.0 | [Schema](schemas/deterministic-check-result.schema.json) | protected check runner → review-context builder, protected gate | [Intent_Checks.json](examples/Intent_Checks.json), [Topic_Checks.json](examples/Topic_Checks.json), [Science_Checks.json](examples/Science_Checks.json), [Requirements_Checks.json](examples/Requirements_Checks.json) |
| gate-decision | 2.0.0 | [Schema](schemas/gate-decision.schema.json) | protected gate host → durable run-state, scheduler, inspection | [Gate_Decision.json](examples/Gate_Decision.json), [Gate_Topic_Halt.json](examples/Gate_Topic_Halt.json), [Gate_Science_Pass.json](examples/Gate_Science_Pass.json), [Gate_Requirements_Pass.json](examples/Gate_Requirements_Pass.json), [Gate_Intention_Compiler_Pass.json](examples/Gate_Intention_Compiler_Pass.json), [Gate_Compiler_No_Output.json](examples/Gate_Compiler_No_Output.json) |
| intent-ir | 1.0.0 | [Schema](schemas/intent-ir.schema.json) | Intent CC → deterministic checks, Intent verifier, Requirements after acceptance | [Intent_IR.json](examples/Intent_IR.json), [Intent_Topic_Only.json](examples/Intent_Topic_Only.json), [Intent_Contradictory.json](examples/Intent_Contradictory.json) |
| research-brief | 2.0.0 | [Schema](schemas/research-brief.schema.json) | Requirements CC → Requirements verification, static binder/planner, research CCs | [Research_Brief.json](examples/Research_Brief.json), [Research_Brief_Defaults.json](examples/Research_Brief_Defaults.json), [Lifecycle_Research_Brief.json](examples/Lifecycle_Research_Brief.json) |
| subnode-execution-contract | 1.0.0 | [Schema](schemas/subnode-execution-contract.schema.json) | protected binder → runner, check-plan builder, gate | [Intention_Subnode_Contract.json](examples/Intention_Subnode_Contract.json), [Requirements_Subnode_Contract.json](examples/Requirements_Subnode_Contract.json), [Topic_Subnode_Contract.json](examples/Topic_Subnode_Contract.json), [Science_Subnode_Contract.json](examples/Science_Subnode_Contract.json) |
| verifier-assessment | 1.0.0 | [Schema](schemas/verifier-assessment.schema.json) | assigned read-only verifier CC → protected gate | [Intent_Assessment.json](examples/Intent_Assessment.json), [Topic_Assessment.json](examples/Topic_Assessment.json), [Science_Assessment.json](examples/Science_Assessment.json), [Requirements_Assessment.json](examples/Requirements_Assessment.json) |

## Other consequential field contracts

| Contract | Version | Fields | Producer → consumers |
|---|---|---|---|
| accepted-output | 2.0.0 | [Fields](field-catalog.md#accepted-output) | protected durable state → scheduler, client |
| activation-record | 1.0.0 | [Fields](field-catalog.md#activation-record) | authorized human through protected library → future selection, audit |
| artifact-envelope | 2.0.0 | [Fields](field-catalog.md#artifact-envelope) | trusted capture → checking, export, runner |
| benchmark-payload | 1.0.0 | [Fields](field-catalog.md#benchmark-payload) | Benchmark with protected provisioner/executor → Evaluation, checking, Delivery |
| bound-check-plan | 2.0.0 | [Fields](field-catalog.md#bound-check-plan) | protected guard resolver → checks, review builder, gate |
| candidate-provenance | 1.0.0 | [Fields](field-catalog.md#candidate-provenance) | candidate builder with protected capture → library admission, human, RSI |
| candidate-set | 1.0.0 | [Fields](field-catalog.md#candidate-set) | Search and Ideation CC → Screening, checking |
| client-cancellation | 1.0.0 | [Fields](field-catalog.md#client-cancellation) | client and protected controller → runner, client |
| client-error | 1.0.0 | [Fields](field-catalog.md#client-error) | application → clients |
| client-readiness | 1.0.0 | [Fields](field-catalog.md#client-readiness) | application → browser, CLI, benchmarker, sidecar |
| client-retrieval | 1.0.0 | [Fields](field-catalog.md#client-retrieval) | scoped client and application → inspection, export |
| client-status | 1.0.0 | [Fields](field-catalog.md#client-status) | control plane → clients |
| client-submission | 1.0.0 | [Fields](field-catalog.md#client-submission) | scoped client → control plane |
| default-policy | 1.0.0 | [Fields](field-catalog.md#default-policy) | protected configuration owner → Requirements CC, Requirements verifier |
| delivery-manifest | 1.0.0 | [Fields](field-catalog.md#delivery-manifest) | Delivery CC with trusted export → user, checking, client |
| environment-lock | 1.0.0 | [Fields](field-catalog.md#environment-lock) | protected environment preparation → Hypothesis, Builder, provisioner |
| evaluation-verdict | 1.0.0 | [Fields](field-catalog.md#evaluation-verdict) | Scientific Evaluation CC → Delivery, checking |
| frozen-graph | 2.0.0 | [Fields](field-catalog.md#frozen-graph) | protected freeze → scheduler, binder |
| hypothesis-blueprint | 1.0.0 | [Fields](field-catalog.md#hypothesis-blueprint) | Hypothesis CC → Builder, Benchmark, Evaluation, checking |
| invocation-observation | 2.0.0 | [Fields](field-catalog.md#invocation-observation) | protected runner → gate, review, Run Bundle |
| library-admission | 1.0.0 | [Fields](field-catalog.md#library-admission) | protected library admission → eligibility, human |
| model-route | 1.0.0 | [Fields](field-catalog.md#model-route) | protected router → audited bridge, observations |
| node-execution-contract | 2.0.0 | [Fields](field-catalog.md#node-execution-contract) | protected node binder → subnode binder, runner, node gate, inspection |
| opportunity-card | 1.0.0 | [Fields](field-catalog.md#opportunity-card) | Screening CC → Hypothesis, checking |
| plan-proposal | 2.0.0 | [Fields](field-catalog.md#plan-proposal) | static template or bounded planner → binder, plan checking |
| poc-manifest | 1.0.0 | [Fields](field-catalog.md#poc-manifest) | Builder CC with trusted capture → Benchmark, checking, Delivery |
| qualified-intake | 2.0.0 | [Fields](field-catalog.md#qualified-intake) | protected intake → Intent CC, Requirements CC |
| resource-snapshot | 1.0.0 | [Fields](field-catalog.md#resource-snapshot) | protected resolver → Hypothesis, Builder, Benchmark |
| review-context | 2.0.0 | [Fields](field-catalog.md#review-context) | protected context builder → read-only verifier |
| rsi-attempt | 1.0.0 | [Fields](field-catalog.md#rsi-attempt) | protected RSI controller → guard, referee, evidence |
| rsi-evidence-export | 1.0.0 | [Fields](field-catalog.md#rsi-evidence-export) | trusted audience-filtered builder → authorized human, library |
| rsi-loop-feedback | 1.0.0 | [Fields](field-catalog.md#rsi-loop-feedback) | custodian → proposer |
| rsi-referee-evidence | 1.0.0 | [Fields](field-catalog.md#rsi-referee-evidence) | protected independent referee → restricted admission, evidence builder |
| rsi-target-profile | 1.0.0 | [Fields](field-catalog.md#rsi-target-profile) | protected target owner → controller, guard, referee |
| run-bundle | 1.0.0 | [Fields](field-catalog.md#run-bundle) | protected evidence builder → inspection, authorized export |
| scorecard | 1.0.0 | [Fields](field-catalog.md#scorecard) | derived observation builder → analysis, planner |
| screening-result | 1.0.0 | [Fields](field-catalog.md#screening-result) | Screening CC and deterministic helper → selection, checking, RSI |
| security-clearance | 1.0.0 | [Fields](field-catalog.md#security-clearance) | authorized security human through protected RSI controller → new-session eligibility, audit |
