# Architecture reference

`Tier 3 · Part of: [README](../README.md)`

This layer standardizes consequential information for agents; humans start at [the package README](../README.md). Fields and schemas are architecture, not deferred independent inventions. Use the [contract index](#contract-index) below to find each schema, field definition, producer, consumer and available example.

| Reference | Purpose |
|---|---|
| [Intent and Requirements](intent-and-requirements.md) | Distinct intermediates, required information, checking and consumer rules |
| [Checking and gate records](checking.md) | Mechanical results, semantic verdicts and protected control decisions |
| [CC fields](declaration.md) | The CC declaration: per-field tables, enums, M1 status, what RSI may change, lineage, hashing profile and differences from the historical source |
| [Node/subnode contracts](node-execution.md) | Enclosing field contract and critical protected subnode bindings, authority, limits and dispatch identity |
| [Named field catalog](field-catalog.md) | Required field names and types, and resolvable public contract IDs |
| [Derived records](derived-records.md) | The `records/` layout, the release rule, the Capsule Run Record, and the contract-conformance, capsule-scorecard and sample-run-export records |
| [RSI contracts](rsi-contracts.md) | RSI workbench session, attempt, referee, session result and candidate package records, with the admission checks |
| [Field catalog sections](field-catalog.md) | Plan and node, research, manifest and runtime, client and model, and library records |
| [Import boundary](import-boundary.md) | The hot-path package list, the forbidden packages, the one router client module and the lint config |
| [Catalog](catalog.json) | Versioned schema identities, producer and consumer, and examples |
| [Readable examples](examples/README.md) | Small worked set; accepted, blocked and scientific-negative outcomes |

## Schema and manifest principles

1. A shared artifact has one current field contract, an explicit version and named producers/consumers. JSON Schema Draft 2020-12 governs the seven critical schemas. All references resolve through the local catalog; validation needs no network fetch.
2. Required fields communicate obligations. A nullable value or empty list means explicitly absent/not applicable, not an inferred pass. Describe missing/invalid/uncertain outcomes. Not every optional parameter is required before Intent can advance.
3. Closed core fields prevent incompatible inventions. Optional `ext` keys are producer-namespaced diagnostic data; they cannot change meaning, permissions, requirements or gate authority. Contract-breaking changes require a new version and consumer reconciliation; examples do not create another format.
4. Payload bodies contain substantive content plus format version and source references. The trusted runner attaches run/node/attempt, producing invocation, exact byte hash, schema identity, effective configuration and audience in an artifact envelope. Model-supplied runtime identity is never trusted.
5. `Ref {id, sha256}` identifies exact immutable bytes; the manifest maps it to role, format version and descriptive readable path. Runtime checks resolve and validate expected type/version and scope. A hash is not proof of truth or permission. See [inspection](../platform/inspection.md).
6. Schemas check structure; D20 semantic criteria check declaration/output conformance and internal consistency. Source-span bounds are deterministic; source support and paraphrase fidelity are producer obligations ([D24](../method/decisions.md#d24)). Per-CC contracts: [capsule build references](capsules/README.md), [run plan](run-plan.md). A model readiness flag cannot release work.
7. Keep assessment verdicts, scientific conclusions, library admission and protected gate decisions separate. Valid JSON from an unauthorized writer never becomes protected state.
8. Fixed work has contracts/profiles chosen before execution. Bind complete context before checks; freeze criteria before observations. Do not cache/reuse an old acceptance decision for new evidence.
9. Human-readable JSON and a derived view remain inspectable without anonymous binaries. Raw traces, executable packages and protected RSI fixtures have separate roles and audiences; manifest indirection cannot hide substantive IRs.

## Current critical schemas

The catalog contains CC declaration, Intent IR, Research Brief, deterministic check result, verifier assessment, gate decision and Subnode Execution Contract, plus shared definitions. Other major types have field contracts rather than exact machine schemas. This deliberately replaces the interrupted 60-contract draft. Internal algorithms, adapters, transport routes and classes remain implementation choices.

The examples are synthetic teaching data, not observed runtime evidence. No historical schema, source maturity label or example grants executable support for future composition/RSI features.

## Field tables first

Required information, meaning, consumer, ownership and failure behavior belong in concise tables. Exact schemas are reserved for critical cross-agent serialization and authority: Intent IR, Research Brief, declaration and execution/verification records. Do not generate a schema for every datatype. Implementation agents select private representations and types within the shared contract; changing consequential interchange requires one reconciled interface agreement.


## Capsule and model routing

Use the [shared integration contract](model-routing-contract.md) for trusted exports, protected profiles, frozen decisions and call provenance.

## Contract index

Each row links the schema or the field table that owns the contract. CC output contracts live on the [capsule build pages](capsules/README.md). The records folder layout, the release rule and the three derived records are on [derived records](derived-records.md).

### Critical exact boundaries

| Contract | Version | Authoritative reference | Producer → consumers | Examples |
|---|---|---|---|---|
| capsule-declaration | 1.0.0 | [Schema](schemas/capsule-declaration.schema.json) | CC author/importer → admission, discovery/binder, runner, RSI | [capsule_declaration.json](examples/capsule_declaration.json), [ranking_child_declaration.json](examples/ranking_child_declaration.json) · invalid: [verifier_capsule_invalid_rsi_propose.json](examples/verifier_capsule_invalid_rsi_propose.json) |
| deterministic-check-result | 1.0.0 | [Schema](schemas/deterministic-check-result.schema.json) | protected check runner → review-context builder, protected gate | [intent_checks.json](examples/intent_checks.json), [science_checks.json](examples/science_checks.json) |
| gate-decision | 2.0.0 | [Schema](schemas/gate-decision.schema.json) | protected gate host → durable run-state, scheduler, inspection | [gate_decision.json](examples/gate_decision.json), [gate_science_pass.json](examples/gate_science_pass.json) · invalid: [gate_decision_invalid_advance_on_fail.json](examples/gate_decision_invalid_advance_on_fail.json) |
| intent-ir | 1.0.0 | [Schema](schemas/intent-ir.schema.json) | Intent CC → deterministic checks, Intent verifier, Requirements after acceptance | [intent_ir.json](examples/intent_ir.json) |
| research-brief | 2.0.0 | [Schema](schemas/research-brief.schema.json) | Requirements CC → Requirements verification, static binder/planner, research CCs | [research_brief.json](examples/research_brief.json), [lifecycle_research_brief.json](examples/lifecycle_research_brief.json) |
| subnode-execution-contract | 1.0.0 | [Schema](schemas/subnode-execution-contract.schema.json) | scheduler at dispatch, from the template stored at freeze → runner, check-plan builder, gate | [intention_subnode_contract.json](examples/intention_subnode_contract.json), [science_subnode_contract.json](examples/science_subnode_contract.json) |
| verifier-assessment | 1.0.0 | [Schema](schemas/verifier-assessment.schema.json) | assigned read-only verifier CC → protected gate | [intent_assessment.json](examples/intent_assessment.json), [science_assessment.json](examples/science_assessment.json) |

### Other consequential field contracts

Each row links to the page that owns the fields. CC output contracts live on the [capsule build pages](capsules/README.md).

| Contract | Version | Fields | Producer → consumers | Valid example |
|---|---|---|---|---|
| accepted-output | 2.0.0 | [Fields](field-catalog.md#accepted-output) | protected durable state → scheduler, client | [Examples](examples/README.md) |
| activation-record | 1.0.0 | [Fields](field-catalog.md#activation-record) | authorized human through protected library → future selection, audit | none |
| artifact-envelope | 2.0.0 | [Fields](field-catalog.md#artifact-envelope) | trusted capture → checking, export, runner | [Examples](examples/README.md) |
| benchmark-payload | 2.0.0 | [Fields](capsules/research-benchmark.md#41-benchmark_payload-benchmark-payloadfield-contract2) | Research Benchmark CC (research.benchmark) → Scientific Evaluation CC, checking, Delivery CC | [benchmark_payload.json](examples/benchmark_payload.json) |
| bound-check-plan | 2.0.0 | [Fields](field-catalog.md#bound-check-plan) | protected check runner at dispatch → check runner, review-context builder, gate host | [check_plan.json](examples/check_plan.json), [science_node_check_plan.json](examples/science_node_check_plan.json) |
| build-receipt | 1.0.0 | [Fields](capsules/builder.md#build_receipt) | host check bundle for the Builder (protected) → Benchmark, checking, Delivery | [build_receipt.json](examples/build_receipt.json) · invalid: [build_receipt_invalid_ready_with_forbidden_import.json](examples/build_receipt_invalid_ready_with_forbidden_import.json) |
| candidate-package | 1.0.0 | [Fields](rsi-contracts.md#candidate-package) | RSI workbench packager → admission inbox, admission command, human reviewer | [candidate_package.json](examples/candidate_package.json) · invalid: [candidate_package_invalid_child_outside_may_change.json](examples/candidate_package_invalid_child_outside_may_change.json) |
| candidate-provenance | 1.0.0 | [Fields](rsi-contracts.md#candidate-provenance) | candidate builder with protected capture → library admission, human, RSI | [rsi_child_candidate.json](examples/rsi_child_candidate.json) |
| candidate-set | 2.0.0 | [Fields](capsules/search.md#candidate_set) | Search CC → Screening CC, checking | [candidate_set.json](examples/candidate_set.json) |
| capsule-scorecard | 1.0.0 | [Fields](derived-records.md#capsule-scorecard) | protected scorecard builder (record builder) → CC owners, RSI workbench | none |
| check-bundle | 1.0.0 | [Fields](capsules/verifier.md#check_bundle-contract) | Verifier owner via protected admission → binder, check runner, gate | none |
| checking-profile | 1.0.0 | [Fields](capsules/verifier.md#checking_profile-contract) | Verifier owner via protected admission → binder, verifier host, gate | none |
| client-cancellation | 1.0.0 | [Fields](field-catalog.md#client-cancellation) | client and protected controller → runner, client | [Examples](examples/README.md) |
| client-upload | 1.0.0 | [Fields](field-catalog.md#client-upload) | control plane → protected intake, browser, CLI | [client_upload_validation.json](examples/client_upload_validation.json) |
| client-error | 1.0.0 | [Fields](field-catalog.md#client-error) | application → clients | [Examples](examples/README.md) |
| client-readiness | 1.0.0 | [Fields](field-catalog.md#client-readiness) | application → browser, CLI, platform benchmark runner, sidecar | none |
| client-retrieval | 1.0.0 | [Fields](field-catalog.md#client-retrieval) | scoped client and application → inspection, export | [Examples](examples/README.md) |
| client-status | 1.0.0 | [Fields](field-catalog.md#client-status) | control plane → clients | [Examples](examples/README.md) |
| client-submission | 1.0.0 | [Fields](field-catalog.md#client-submission) | scoped client → control plane | none |
| contract-conformance | 1.0.0 | [Fields](derived-records.md#contract-conformance) | protected conformance builder (record builder) → capsule scorecard builder, sample run export, RSI workbench, CC owners | none |
| default-policy | 1.0.0 | [Fields](field-catalog.md#default-policy) | protected configuration owner → Requirements CC, Requirements verifier | [default_policy.json](examples/default_policy.json) |
| delivery-manifest | 2.0.0 | [Fields](capsules/delivery.md#delivery_manifest) | Delivery CC (research.delivery) → user, checking, client | [delivery_manifest.json](examples/delivery_manifest.json) |
| dispatch-record | 2.0.0 | [Fields](run-plan.md#dispatch-record) | scheduler → run state, check runner, observability, RSI export | [dispatch_record.json](examples/dispatch_record.json) |
| empirical-results | 1.0.0 | [Fields](capsules/research-benchmark.md#421-empirical_results-empirical-resultsfield-contract1) | Protected executor inside research.benchmark → Research Benchmark checks, Scientific Evaluation CC, Delivery CC | [execution_receipt_empirical_results.json](examples/execution_receipt_empirical_results.json) |
| environment-lock | 1.0.0 | [Fields](field-catalog.md#environment-lock) | protected environment preparation → Hypothesis, Builder, provisioner | [environment_lock.json](examples/environment_lock.json) |
| evaluation-profile | 1.0.0 | [Fields](field-catalog.md#evaluation-profile) | protected configuration owner, approved by the benchmark owner → launcher, application, platform benchmark runner | none |
| evaluation-verdict | 2.0.0 | [Fields](capsules/scientific-evaluation.md#41-evaluation_verdict-evaluation-verdictfield-contract2) | Scientific Evaluation CC (research.evaluation) → Delivery CC, checking | [evaluation_verdict.json](examples/evaluation_verdict.json) |
| execution-receipt | 1.0.0 | [Fields](capsules/research-benchmark.md#42-execution_receipt-execution-receiptfield-contract1) | Protected executor inside research.benchmark → Research Benchmark checks, Scientific Evaluation CC, Delivery CC, checking | [execution_receipt.json](examples/execution_receipt.json) |
| gate-decision-index | 1.0.0 | [Fields](capsules/delivery.md#gate_decision_index) | Scheduler (host record built from accepted dispatch records) → Delivery CC, checking | [gate_decision_index.json](examples/gate_decision_index.json) |
| hypothesis-blueprint | 2.0.0 | [Fields](capsules/hypothesis.md#output-field-contract) | Hypothesis CC (research.hypothesis) → Builder, Benchmark, Evaluation, checking | [hypothesis_blueprint.json](examples/hypothesis_blueprint.json) |
| invocation-observation | 3.0.0 | [Fields](field-catalog.md#invocation-observation) | protected CC runner, and for the gate-side fields the gate host (hot path) → review-context builder, run bundle, record export (RSI workbench, platform benchmark runner). Completed, it is the Capsule Run Record | [invocation_observation.json](examples/invocation_observation.json), [science_observation.json](examples/science_observation.json) · invalid: [invocation_observation_invalid_decision_source.json](examples/invocation_observation_invalid_decision_source.json) |
| library-admission | 1.0.0 | [Fields](field-catalog.md#library-admission) | protected library admission → library snapshot, eligibility, human, RSI workbench | [rsi_admission.json](examples/rsi_admission.json), [rsi_parent_admission.json](examples/rsi_parent_admission.json) |
| library-snapshot | 1.0.0 | [Fields](run-plan.md#library-snapshot) | protected library → Planner CC, protected binder | [library_snapshot.json](examples/library_snapshot.json) |
| route-record | 1.0.0 | [Fields](model-routing-contract.md#route-record) | model bridge → model-call records, observations, Run Bundle, platform benchmark runner | [route_record_router_decision.json](examples/route_record_router_decision.json) · invalid: [route_record_invalid_router_without_decision.json](examples/route_record_invalid_router_without_decision.json) |
| model-call | 1.0.0 | [Fields](model-routing-contract.md#model-call) | governed bridge/audit writer → observations, Run Bundle, authorized inspection | [model_call_record.json](examples/model_call_record.json) |
| model-route | 2.0.0 | [Fields](model-routing-contract.md#model-route) | protected RouterPort (CodexRouter or API router) → audited bridge, runner, observations, Run Bundle | [route_decision.json](examples/route_decision.json) |
| model-selection-profile | 1.0.0 | [Fields](model-routing-contract.md#model-selection-profile) | protected configuration owner → binder, RouterPort (CodexRouter or API router), bridge | [model_selection_profile.json](examples/model_selection_profile.json) |
| node-execution-contract | 2.0.0 | [Fields](field-catalog.md#node-execution-contract) | scheduler at dispatch → CC runner, check runner, node gate, inspection | [intention_node_contract.json](examples/intention_node_contract.json), [science_node_contract.json](examples/science_node_contract.json) · invalid: [node_contract_invalid_gate_subject.json](examples/node_contract_invalid_gate_subject.json) |
| node-finalization-profile | 2.0.0 | [Fields](checking.md#node-finalization-profile) | protected configuration owner → scheduler, node gate, check runner | [node_finalization_profile.json](examples/node_finalization_profile.json) |
| opportunity-card | 2.0.0 | [Fields](capsules/screening.md#opportunity_card) | Screening CC → Hypothesis CC, checking | [opportunity_card.json](examples/opportunity_card.json) |
| plan-outcome | 1.0.0 | [Fields](run-plan.md#plan-outcome) | Protected binder and scheduler → host run controller, Intention Compiler (next attempt), audit | none |
| plan-policy | 1.0.0 | [Fields](run-plan.md#plan-policy) | protected configuration owner → Planner CC, protected binder | [plan_policy.json](examples/plan_policy.json) |
| plan-proposal | 3.0.0 | [Fields](capsules/planner.md#output-field-contract) | Planner CC (research.planner) → protected binder, plan gate | none |
| poc-artifact-bundle | 1.0.0 | [Fields](capsules/builder.md#poc_artifact_bundle) | Builder CC (research.builder) → Benchmark | [poc_artifact_bundle.zip](examples/poc_artifact_bundle.zip) |
| poc-manifest | 2.0.0 | [Fields](capsules/builder.md#poc_manifest) | Builder CC (research.builder) → Benchmark, checking, Delivery | [poc_manifest.json](examples/poc_manifest.json) |
| provisioning-receipt | 1.0.0 | [Fields](capsules/research-benchmark.md#43-provisioning_receipt-provisioning-receiptfield-contract1) | Protected provisioner inside research.benchmark → Research Benchmark checks, Scientific Evaluation CC, checking | [provisioning_receipt.json](examples/provisioning_receipt.json) |
| operator-config | 1.0.0 | [Fields](field-catalog.md#operator-config) | operator (protected configuration owner) → app container entrypoint, binder, model bridge, scheduler | the YAML example in the Fields section |
| qualified-intake | 2.0.0 | [Fields](field-catalog.md#qualified-intake) | protected intake → Intent CC, Requirements CC | [qualified_intake.json](examples/qualified_intake.json) |
| research-report | 1.0.0 | [Fields](capsules/delivery.md#research_report) | Delivery CC (research.delivery) → user, checking, client | [Examples](examples/README.md) |
| resource-inventory | 1.0.0 | [Fields](run-plan.md#resource-inventory) | host intake and capture → Planner CC, protected binder | [resource_inventory.json](examples/resource_inventory.json) |
| resource-snapshot | 1.0.0 | [Fields](field-catalog.md#resource-snapshot) | protected resolver → Hypothesis, Builder, Benchmark | [baseline_resource.json](examples/baseline_resource.json), [validation_resource.json](examples/validation_resource.json) |
| review-context | 2.0.0 | [Fields](field-catalog.md#review-context) | protected context builder → protected gate, audit and inspection | [review_context.json](examples/review_context.json) |
| route-request | 1.0.0 | [Fields](model-routing-contract.md#route-request) | protected upstream routing adapter → RouterPort (CodexRouter or API router) | [route_request.json](examples/route_request.json) |
| rsi-attempt | 1.0.0 | [Fields](rsi-contracts.md#rsi-attempt) | protected RSI controller → mutation check, referee, evidence | [rsi_attempt_01.json](examples/rsi_attempt_01.json) |
| rsi-completion-report | 1.0.0 | [Fields](rsi-contracts.md#rsi-completion-report) | RSI workbench report builder → human reviewer, product acceptance | none |
| rsi-evidence-export | 1.0.0 | [Fields](rsi-contracts.md#rsi-evidence-export) | trusted audience-filtered builder → authorized human, library | [rsi_evidence_export.json](examples/rsi_evidence_export.json) |
| rsi-loop-feedback | 1.0.0 | [Fields](rsi-contracts.md#rsi-loop-feedback) | custodian → proposer | none |
| rsi-opportunity | 1.0.0 | [Fields](rsi-contracts.md#rsi-opportunity) | RSI workbench controller, after a human selects the target → human reviewer, RSI controller, evidence export | none |
| rsi-referee-evidence | 1.0.0 | [Fields](rsi-contracts.md#rsi-referee-evidence) | protected independent referee → restricted admission, evidence builder | [rsi_referee_evidence.json](examples/rsi_referee_evidence.json) |
| rsi-session | 1.0.0 | [Fields](rsi-contracts.md#rsi-session) | RSI controller, started by a human → proposer, mutation check, referee, evidence builder, candidate packager | [rsi_session.json](examples/rsi_session.json) |
| rsi-session-result | 1.0.0 | [Fields](rsi-contracts.md#rsi-session-result) | RSI controller → candidate packager, human reviewer, evidence export, admission command | [rsi_session_result.json](examples/rsi_session_result.json) |
| rsi-target-profile | 1.0.0 | [Fields](rsi-contracts.md#rsi-target-profile) | protected target owner → controller, mutation check, referee | [rsi_target_profile.json](examples/rsi_target_profile.json) · invalid: [rsi_target_profile_invalid_wider_than_may_change.json](examples/rsi_target_profile_invalid_wider_than_may_change.json) |
| run-bundle | 1.0.0 | [Fields](field-catalog.md#run-bundle) | protected evidence builder → inspection, authorized export, platform benchmark runner, RSI workbench | [run_bundle.json](examples/run_bundle.json) |
| run-plan | 1.0.0 | [Fields](run-plan.md#run-plan) | protected binder and freeze → scheduler, check runner, run state | [run_plan.json](examples/run_plan.json) · invalid: [run_plan_invalid_uncovered_node.json](examples/run_plan_invalid_uncovered_node.json), [run_plan_invalid_tie_order.json](examples/run_plan_invalid_tie_order.json) |
| sample-run-export | 1.0.0 | [Fields](derived-records.md#sample-run-export) | protected export builder (record builder) → RSI workbench, platform benchmark runner, offline development of the verifier CC | none |
| screening-result | 2.0.0 | [Fields](capsules/screening.md#screening_result) | Screening CC → Hypothesis CC, checking, RSI | [screening_result.json](examples/screening_result.json) |
| screening-rubric | 1.0.0 | [Fields](capsules/screening.md#screening_rubric-field-contract) | CC owner (pinned in the Screening declaration) → Screening CC, checking, RSI referee | [screening_rubric.json](examples/screening_rubric.json) |
| search-scope | 1.0.0 | [Fields](capsules/search.md#search_scope-field-contract) | Protected binder (from run configuration, resource inventory and Planner topic hints) → Search CC, checking | [search_scope.json](examples/search_scope.json) |
| security-clearance | 1.0.0 | [Fields](rsi-contracts.md#security-clearance) | authorized security human through protected RSI controller → new-session eligibility, audit | none |
| selected-capsule-input | 1.0.0 | [Fields](model-routing-contract.md#selected-capsule-input) | protected binder/runner → RouterPort (CodexRouter or API router) | [selected_capsule_input.json](examples/selected_capsule_input.json) |
| static-template | 1.0.0 | [Fields](run-plan.md#static-template) | Architect (hand-authored) → protected binder | [static_template.json](examples/static_template.json) |

### Platform benchmark runner records

The [platform benchmark runner](../side-systems/benchmark-runner.md) defines its own records. They are outside the product, so they are not in `field-contracts.json`.

| Contract ID | Defined in |
|---|---|
| `benchmark-case:1` | [benchmark runner](../side-systems/benchmark-runner.md) |
| `benchmark-referee:1` | [benchmark runner](../side-systems/benchmark-runner.md) |
| `benchmark-campaign:1` | [benchmark runner](../side-systems/benchmark-runner.md) |
| `hardware-inventory:1` | [benchmark runner](../side-systems/benchmark-runner.md) |
| `run-record:1` | [benchmark runner](../side-systems/benchmark-runner.md) |
| `score-record:1` | [benchmark runner](../side-systems/benchmark-runner.md) |
| `benchmark-report:1` | [benchmark runner](../side-systems/benchmark-runner.md) |
