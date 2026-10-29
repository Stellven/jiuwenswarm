# Worked example: one run, every node

`Tier 2 · Part of: [Pipeline](README.md) · Serves: Knowledge`

This page expands [diagram F of 1. System](../1-system.md#worked-example) as tables. The example request is: "Can a learned sparse index cut retrieval latency on our local corpus without losing recall?" Every node follows the [node pattern](stages.md#the-node-pattern). Host records that Delivery reads (`gate_decision_index`, `screening_result`, the receipts, `environment_lock`, `run_configuration`) are built by the scheduler from accepted records ([run plan](../reference/run-plan.md#freeze)).

## Counts in this run

| Node | Work CC | Outputs | Verifier calls | Output gate decisions |
|---|---|---|---|---|
| intent | `intent.compiler` | `intent_ir` | 1 | 1 |
| requirements | `requirements.compiler` | `research_brief` | 1 | 1 |
| planner | `research.planner` | `plan_proposal` | 1 | 1 |
| search | `research.search` | `candidate_set` | 1 | 1 |
| screening | `research.screening` | `screening_result`, `opportunity_card` | 2 | 2 |
| hypothesis | `research.hypothesis` | `hypothesis_blueprint` | 1 | 1 |
| builder | `research.builder` | `poc_manifest`, `poc_artifact_bundle` | 2 | 2 |
| benchmark | `research.benchmark` | `benchmark_payload`, `execution_receipt`, `provisioning_receipt` | 3 | 3 |
| evaluation | `research.evaluation` | `evaluation_verdict` | 1 | 1 |
| delivery | `research.delivery` | `delivery_manifest`, `research_report` | 2 | 2 |

Each node also writes one node gate decision. Kahn order for the research nodes: search, screening, hypothesis, builder, benchmark, evaluation, delivery.

## Artifact on each edge

| From | To | Accepted artifact on the edge |
|---|---|---|
| User | intent | request and local files |
| intent | requirements | `intent_ir` |
| requirements | planner | `research_brief` |
| planner | binder | `plan_proposal` (the binder checks it, the plan gate accepts it, the plan is frozen) |
| search | screening, delivery | `candidate_set` |
| screening | hypothesis, delivery | `opportunity_card` |
| hypothesis | builder, benchmark, evaluation, delivery | `hypothesis_blueprint` |
| builder | benchmark, delivery | `poc_manifest`, and `poc_artifact_bundle` to benchmark |
| benchmark | evaluation, delivery | `benchmark_payload` |
| evaluation | delivery | `evaluation_verdict`. A scientific `FAIL` is still a correctly completed node |
| delivery | output directory | `research_report`, `delivery_manifest` |

Exact fields of each artifact are on the [CC build pages](../reference/capsules/README.md).
