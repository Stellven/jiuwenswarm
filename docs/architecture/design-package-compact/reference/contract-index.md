# Contract index

Find the shared fields and purpose here. [Compiler build](../builds/intention-compiler/README.md), [verification obligations](compiler-verification.md), [field tables](field-catalog.md) and [examples](examples/README.md) explain use. Exact schemas are selected critical boundaries, not a schema inventory for every internal datatype.

## Critical exact boundaries

| Contract | Version | Authoritative reference | Producer → consumers | Examples |
|---|---|---|---|---|
| capsule-declaration | 1.0.0 | [Schema](schemas/capsule-declaration.schema.json) | CC author/importer → admission, discovery/binder, runner, RSI | [capsule_declaration.json](examples/capsule_declaration.json) |
| deterministic-check-result | 1.0.0 | [Schema](schemas/deterministic-check-result.schema.json) | protected check runner → review-context builder, protected gate | [intent_checks.json](examples/intent_checks.json), [topic_checks.json](examples/topic_checks.json), [science_checks.json](examples/science_checks.json), [requirements_checks.json](examples/requirements_checks.json) |
| gate-decision | 2.0.0 | [Schema](schemas/gate-decision.schema.json) | protected gate host → durable run-state, scheduler, inspection | [gate_decision.json](examples/gate_decision.json), [gate_topic_halt.json](examples/gate_topic_halt.json), [gate_science_pass.json](examples/gate_science_pass.json), [gate_requirements_pass.json](examples/gate_requirements_pass.json), [gate_intention_compiler_pass.json](examples/gate_intention_compiler_pass.json), [gate_compiler_no_output.json](examples/gate_compiler_no_output.json) |
| intent-ir | 1.0.0 | [Schema](schemas/intent-ir.schema.json) | Intent CC → deterministic checks, Intent verifier, Requirements after acceptance | [intent_ir.json](examples/intent_ir.json), [intent_topic_only.json](examples/intent_topic_only.json), [intent_contradictory.json](examples/intent_contradictory.json) |
| research-brief | 2.0.0 | [Schema](schemas/research-brief.schema.json) | Requirements CC → Requirements verification, static binder/planner, research CCs | [research_brief.json](examples/research_brief.json), [research_brief_defaults.json](examples/research_brief_defaults.json), [lifecycle_research_brief.json](examples/lifecycle_research_brief.json) |
| subnode-execution-contract | 1.0.0 | [Schema](schemas/subnode-execution-contract.schema.json) | protected binder → runner, check-plan builder, gate | [intention_subnode_contract.json](examples/intention_subnode_contract.json), [requirements_subnode_contract.json](examples/requirements_subnode_contract.json), [topic_subnode_contract.json](examples/topic_subnode_contract.json), [science_subnode_contract.json](examples/science_subnode_contract.json) |
| verifier-assessment | 1.0.0 | [Schema](schemas/verifier-assessment.schema.json) | assigned read-only verifier CC → protected gate | [intent_assessment.json](examples/intent_assessment.json), [topic_assessment.json](examples/topic_assessment.json), [science_assessment.json](examples/science_assessment.json), [requirements_assessment.json](examples/requirements_assessment.json) |

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
| model-route | 2.0.0 | [Fields](capsule-model-routing.md#model-route) | protected router/static adapter → audited bridge, runner, observations | [Examples](examples/README.md) |
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

| selected-capsule-input | 1.0.0 | [Fields](capsule-model-routing.md#selected-capsule-input) | protected binder/runner → router/static adapter | [Examples](examples/README.md) |

| model-selection-profile | 1.0.0 | [Fields](capsule-model-routing.md#model-selection-profile) | protected configuration owner → binder, router/static adapter, bridge | [Examples](examples/README.md) |

| route-request | 1.0.0 | [Fields](capsule-model-routing.md#route-request) | protected upstream routing adapter → router/static adapter | [Examples](examples/README.md) |

| model-call | 1.0.0 | [Fields](capsule-model-routing.md#model-call) | governed bridge/audit writer → observations, Run Bundle, authorized inspection | [Examples](examples/README.md) |
