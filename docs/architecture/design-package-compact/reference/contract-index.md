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

Each row links to the page that owns the fields. CC output contracts live on the [capsule build pages](capsules/README.md).

| Contract | Version | Fields | Producer → consumers | Valid example |
|---|---|---|---|---|
| accepted-output | 2.0.0 | [Fields](field-catalog.md#accepted-output) | protected durable state → scheduler, client | [Examples](examples/README.md) |
| activation-record | 1.0.0 | [Fields](field-catalog.md#activation-record) | authorized human through protected library → future selection, audit | [rsi_activation.json](examples/rsi_activation.json), [rsi_rollback.json](examples/rsi_rollback.json) |
| artifact-envelope | 2.0.0 | [Fields](field-catalog.md#artifact-envelope) | trusted capture → checking, export, runner | [Examples](examples/README.md) |
| benchmark-payload | 2.0.0 | [Fields](capsules/research-benchmark.md#41-benchmark_payload-benchmark-payloadfield-contract2) | Research Benchmark CC (research.benchmark) → Scientific Evaluation CC, checking, Delivery CC | [benchmark_payload.json](examples/benchmark_payload.json) |
| bound-check-plan | 2.0.0 | [Fields](field-catalog.md#bound-check-plan) | protected guard resolver → checks, review builder, gate | [check_plan.json](examples/check_plan.json), [requirements_check_plan.json](examples/requirements_check_plan.json) |
| build-receipt | 1.0.0 | [Fields](capsules/builder.md#build_receipt) | host check bundle for the Builder (protected) → Benchmark, checking, Delivery | [build_receipt.json](examples/build_receipt.json) |
| candidate-provenance | 1.0.0 | [Fields](field-catalog.md#candidate-provenance) | candidate builder with protected capture → library admission, human, RSI | [rsi_child_candidate.json](examples/rsi_child_candidate.json) |
| candidate-set | 2.0.0 | [Fields](capsules/search.md#candidate_set) | Search CC → Screening CC, checking | [candidate_set.json](examples/candidate_set.json) |
| check-bundle | 1.0.0 | [Fields](capsules/verifier.md#check_bundle-contract) | Verifier owner via protected admission → binder, check runner, gate | [check_bundle.json](examples/check_bundle.json) |
| checking-profile | 1.0.0 | [Fields](capsules/verifier.md#checking_profile-contract) | Verifier owner via protected admission → binder, verifier host, gate | [checking_profile.json](examples/checking_profile.json) |
| client-cancellation | 1.0.0 | [Fields](field-catalog.md#client-cancellation) | client and protected controller → runner, client | [Examples](examples/README.md) |
| client-error | 1.0.0 | [Fields](field-catalog.md#client-error) | application → clients | [Examples](examples/README.md) |
| client-readiness | 1.0.0 | [Fields](field-catalog.md#client-readiness) | application → browser, CLI, benchmarker, sidecar | [Examples](examples/README.md) |
| client-retrieval | 1.0.0 | [Fields](field-catalog.md#client-retrieval) | scoped client and application → inspection, export | [Examples](examples/README.md) |
| client-status | 1.0.0 | [Fields](field-catalog.md#client-status) | control plane → clients | [Examples](examples/README.md) |
| client-submission | 1.0.0 | [Fields](field-catalog.md#client-submission) | scoped client → control plane | [Examples](examples/README.md) |
| default-policy | 1.0.0 | [Fields](field-catalog.md#default-policy) | protected configuration owner → Requirements CC, Requirements verifier | [default_policy.json](examples/default_policy.json) |
| delivery-manifest | 2.0.0 | [Fields](capsules/delivery.md#delivery_manifest) | Delivery CC (research.delivery) → user, checking, client | [delivery_manifest.json](examples/delivery_manifest.json) |
| dispatch-record | 2.0.0 | [Fields](run-plan.md#dispatch-record) | scheduler → run state, guard resolver, observability, RSI export | [dispatch_record.json](examples/dispatch_record.json) |
| environment-lock | 1.0.0 | [Fields](field-catalog.md#environment-lock) | protected environment preparation → Hypothesis, Builder, provisioner | [environment_lock.json](examples/environment_lock.json) |
| evaluation-verdict | 2.0.0 | [Fields](capsules/scientific-evaluation.md#41-evaluation_verdict-evaluation-verdictfield-contract2) | Scientific Evaluation CC (research.evaluation) → Delivery CC, checking | [evaluation_verdict.json](examples/evaluation_verdict.json) |
| execution-receipt | 1.0.0 | [Fields](capsules/research-benchmark.md#42-execution_receipt-execution-receiptfield-contract1) | Protected executor inside research.benchmark → Research Benchmark checks, Scientific Evaluation CC, Delivery CC, checking | [execution_receipt.json](examples/execution_receipt.json) |
| gate-decision-index | 1.0.0 | [Fields](capsules/delivery.md#gate_decision_index) | Scheduler (host record built from accepted dispatch records) → Delivery CC, checking | [gate_decision_index.json](examples/gate_decision_index.json) |
| hypothesis-blueprint | 2.0.0 | [Fields](capsules/hypothesis.md#output-field-contract) | Hypothesis CC (research.hypothesis) → Builder, Benchmark, Evaluation, checking | [hypothesis_blueprint.json](examples/hypothesis_blueprint.json) |
| invocation-observation | 2.0.0 | [Fields](field-catalog.md#invocation-observation) | protected runner → gate, review, Run Bundle | [invocation_observation.json](examples/invocation_observation.json), [topic_observation.json](examples/topic_observation.json) |
| library-admission | 1.0.0 | [Fields](field-catalog.md#library-admission) | protected library admission → eligibility, human | [rsi_admission.json](examples/rsi_admission.json), [rsi_parent_admission.json](examples/rsi_parent_admission.json) |
| library-snapshot | 1.0.0 | [Fields](run-plan.md#library-snapshot) | protected library → Planner CC, protected binder | [library_snapshot.json](examples/library_snapshot.json), [library_snapshot_unbundled.json](examples/library_snapshot_unbundled.json) |
| model-call | 1.0.0 | [Fields](capsule-model-routing.md#model-call) | governed bridge/audit writer → observations, Run Bundle, authorized inspection | [model_call_record.json](examples/model_call_record.json) |
| model-route | 2.0.0 | [Fields](capsule-model-routing.md#model-route) | protected router/static adapter → audited bridge, runner, observations, Run Bundle | [route_decision.json](examples/route_decision.json) |
| model-selection-profile | 1.0.0 | [Fields](capsule-model-routing.md#model-selection-profile) | protected configuration owner → binder, router/static adapter, bridge | [model_selection_profile.json](examples/model_selection_profile.json) |
| node-execution-contract | 2.0.0 | [Fields](field-catalog.md#node-execution-contract) | protected node binder → subnode binder, runner, node gate, inspection | [intention_node_contract.json](examples/intention_node_contract.json), [topic_node_contract.json](examples/topic_node_contract.json) |
| opportunity-card | 2.0.0 | [Fields](capsules/screening.md#opportunity_card) | Screening CC → Hypothesis CC, checking | [opportunity_card.json](examples/opportunity_card.json) |
| plan-outcome | 1.0.0 | [Fields](run-plan.md#plan-outcome) | Protected binder and scheduler → host run controller, Intention Compiler (next attempt), audit | [plan_outcome.json](examples/plan_outcome.json) |
| plan-policy | 1.0.0 | [Fields](run-plan.md#plan-policy) | protected configuration owner → Planner CC, protected binder | [plan_policy.json](examples/plan_policy.json) |
| plan-proposal | 3.0.0 | [Fields](capsules/planner.md#output-field-contract) | Planner CC (research.planner) → protected binder, plan checks, plan verifier | [plan_proposal.json](examples/plan_proposal.json) |
| poc-artifact-bundle | 1.0.0 | [Fields](capsules/builder.md#poc_artifact_bundle) | Builder CC (research.builder) → Benchmark | [Examples](examples/README.md) |
| poc-manifest | 2.0.0 | [Fields](capsules/builder.md#poc_manifest) | Builder CC (research.builder) → Benchmark, checking, Delivery | [poc_manifest.json](examples/poc_manifest.json) |
| provisioning-receipt | 1.0.0 | [Fields](capsules/research-benchmark.md#43-provisioning_receipt-provisioning-receiptfield-contract1) | Protected provisioner inside research.benchmark → Research Benchmark checks, Scientific Evaluation CC, checking | [provisioning_receipt.json](examples/provisioning_receipt.json) |
| qualified-intake | 2.0.0 | [Fields](field-catalog.md#qualified-intake) | protected intake → Intent CC, Requirements CC | [qualified_intake.json](examples/qualified_intake.json), [topic_qualified_intake.json](examples/topic_qualified_intake.json) |
| research-report | 1.0.0 | [Fields](capsules/delivery.md#research_report) | Delivery CC (research.delivery) → user, checking, client | [Examples](examples/README.md) |
| resource-inventory | 1.0.0 | [Fields](run-plan.md#resource-inventory) | host intake and capture → Planner CC, protected binder | [resource_inventory.json](examples/resource_inventory.json) |
| resource-snapshot | 1.0.0 | [Fields](field-catalog.md#resource-snapshot) | protected resolver → Hypothesis, Builder, Benchmark | [baseline_resource.json](examples/baseline_resource.json), [validation_resource.json](examples/validation_resource.json) |
| review-context | 2.0.0 | [Fields](field-catalog.md#review-context) | protected context builder → protected gate, audit and inspection | [review_context.json](examples/review_context.json), [topic_review_context.json](examples/topic_review_context.json) |
| route-request | 1.0.0 | [Fields](capsule-model-routing.md#route-request) | protected upstream routing adapter → router/static adapter | [route_request.json](examples/route_request.json) |
| rsi-attempt | 1.0.0 | [Fields](field-catalog.md#rsi-attempt) | protected RSI controller → guard, referee, evidence | [rsi_attempt_01.json](examples/rsi_attempt_01.json) |
| rsi-evidence-export | 1.0.0 | [Fields](field-catalog.md#rsi-evidence-export) | trusted audience-filtered builder → authorized human, library | [rsi_evidence_export.json](examples/rsi_evidence_export.json) |
| rsi-loop-feedback | 1.0.0 | [Fields](field-catalog.md#rsi-loop-feedback) | custodian → proposer | [rsi_loop_feedback.json](examples/rsi_loop_feedback.json) |
| rsi-referee-evidence | 1.0.0 | [Fields](field-catalog.md#rsi-referee-evidence) | protected independent referee → restricted admission, evidence builder | [rsi_referee_evidence.json](examples/rsi_referee_evidence.json) |
| rsi-target-profile | 1.0.0 | [Fields](field-catalog.md#rsi-target-profile) | protected target owner → controller, guard, referee | [rsi_target_profile.json](examples/rsi_target_profile.json) |
| run-bundle | 1.0.0 | [Fields](field-catalog.md#run-bundle) | protected evidence builder → inspection, authorized export | [Examples](examples/README.md) |
| run-plan | 1.0.0 | [Fields](run-plan.md#run-plan) | protected binder and freeze → scheduler, guard resolver, run state | [run_plan.json](examples/run_plan.json) |
| scorecard | 1.0.0 | [Fields](field-catalog.md#scorecard) | derived observation builder → analysis, planner | [Examples](examples/README.md) |
| screening-result | 2.0.0 | [Fields](capsules/screening.md#screening_result) | Screening CC → Hypothesis CC, checking, RSI | [screening_result.json](examples/screening_result.json) |
| screening-rubric | 1.0.0 | [Fields](capsules/screening.md#screening_rubric-field-contract) | CC owner (pinned in the Screening declaration) → Screening CC, checking, RSI referee | [screening_rubric.json](examples/screening_rubric.json) |
| search-scope | 1.0.0 | [Fields](capsules/search.md#search_scope-field-contract) | Protected binder (from run configuration, resource inventory and Planner topic hints) → Search CC, checking | [search_scope.json](examples/search_scope.json) |
| security-clearance | 1.0.0 | [Fields](field-catalog.md#security-clearance) | authorized security human through protected RSI controller → new-session eligibility, audit | [rsi_security_clearance.json](examples/rsi_security_clearance.json) |
| selected-capsule-input | 1.0.0 | [Fields](capsule-model-routing.md#selected-capsule-input) | protected binder/runner → router/static adapter | [selected_capsule_input.json](examples/selected_capsule_input.json) |
| static-template | 1.0.0 | [Fields](run-plan.md#static-template) | Architect (hand-authored) → protected binder | [static_template.json](examples/static_template.json) |

