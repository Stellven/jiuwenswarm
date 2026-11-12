# Node vocabulary and an expert-readiness instance

These are records in the existing factory store, not a new planning service.
The engine vocabulary is [ONTOLOGY.yaml](../../../jiuwenswarm/factory/ccs/expert_streaming/ONTOLOGY.yaml).
The operator replaces every `<run5:...>` placeholder with actual evidence IDs;
this example makes no live-run claim.

| Vocabulary | Record or field implementing it |
|---|---|
| Task contract | Task `objective`, `constraints`, `contract_id`; attempt request snapshots the versioned evaluation contract. |
| Plan revision | Immutable observation `kind=taskgraph_patch`, `values.rev`, `parent_rev`, `decision_rev`, `patch`. |
| Work node | Graph `nodes[]`: `node_id`, `kind`, `outcome`, `entities`, `capability`, `requires_evidence`, `resources`, `state`. |
| Attempt | Store `attempts`: `attempt_id`, `request`, `state`, `result_refs`; linked by node `attempt_ids` and optional request `node_id`. |
| Dependency | Node `depends_on`; every dependency must be done before an explicitly node-linked submission. |
| Observation | Store `observations`: `obs_id`, `kind`, `values`, `source_artifacts`; engagement counter `labels` carry quantity, unit and phase. |
| Assessment | Store `evaluations`: correctness, evidence completeness, execution outcome; A/B `inputs.acceptance` and observation `values.acceptance`. |
| Decision | Store `decisions`: hypothesis, evidence IDs, action, revision lineage; optional atomic `plan_patch`. |
| Resource claim | Node `resources.class` expresses requested class; attempt `resources.job_class` records the actual queue class. The host/jobq owns allocation. |

Objective: **make selected expert weights ready before use**. Candidate component
`expert_fill` implements `expert_streaming.demand_fill`; `expert_pregate`
implements `expert_streaming.predictive_read`. These are component capability
identities, not newly callable engine-execution tools. `modifies_region` and
`quantities` describe their mechanisms and evidence in the ontology.

The following is the `patch` of a decision-linked `plan_patch` call. Supply the
current `expected_graph_rev` and an existing `decision_rev` from Run 5 separately.

```json
{
  "add": [
    {
      "node_id": "<run5:build_node_id>",
      "kind": "build",
      "title": "Build selected expert-readiness mechanism",
      "outcome": "An admitted image containing the selected component source",
      "entities": ["engine_revision:<run5:engine_revision>", "source_tree:<run5:source_tree>", "component:expert_fill", "component:expert_pregate"],
      "capability": "factory.builder.submit",
      "resources": {"class": "build"},
      "state": "proposed"
    },
    {
      "node_id": "<run5:measure_node_id>",
      "kind": "measure",
      "title": "Measure readiness before selected expert use",
      "outcome": "Make selected expert weights ready before use, with comparable evidence",
      "entities": ["image:<run5:image_id>", "model:<run5:model_id>", "quantization:<run5:quantization>", "workload:<run5:workload>", "contract:<run5:contract_id>", "region:M.readiness"],
      "capability": "factory.lab_client.ab_submit",
      "depends_on": ["<run5:build_node_id>"],
      "requires_evidence": [
        "readiness.ready_bytes_predicted", "readiness.missing_bytes_predicted",
        "readiness.ready_bytes_unpredicted", "readiness.missing_bytes_unpredicted",
        "readiness.duplicate_demand_bytes", "readiness.wasted_async_bytes"
      ],
      "resources": {"class": "gpu"},
      "state": "proposed"
    }
  ]
}
```

Submit the build with `node_id=<run5:build_node_id>`, retain
`<run5:build_attempt_id>` in that node's `attempt_ids`, and attach its result
evidence before marking it done. Then submit measurement with
`node_id=<run5:measure_node_id>`. Dispatch refuses unknown, superseded, cancelled,
done or failed nodes, and nodes with unfinished dependencies. Calls without
`node_id` retain the existing behavior. Submission records `node_id` in the
attempt request; it does not automatically patch node state or attempt links.

Pass the measurement node's `requires_evidence` to `expert_streaming.engagement`
with `<run5:measurement_attempt_id>`. Missing required counters are returned in
`missing_required`, per run and across runs; a printed zero is measured. Node
requirements describe evidence obligations; they do not change the scoring
contract or automatically establish acceptance. Entity references are descriptive.

Acceptance follows the pinned component material's module type:

| Module type | Acceptance |
|---|---|
| Performance (`expert_fill`, `expert_pregate`, `inflight_join`, `mmap_advice`, `router_prefetch`) | Valid complete comparable ABBA, byte-identical correctness, passing engagement and gate `improved`. |
| Observability (`expert_readiness`, `phase_stats`, `thread_names`) | Correctness and every engagement check pass; overhead `1/ratio - 1 <= max(overhead_bound, gate threshold)`. Missing capture is invalid. |
| Prerequisite | Retain dormant only with an explicit `keep_dormant` decision, source dependencies and runtime switches off; no enabled performance win is claimed. |

Record `<run5:evaluation_id>` and `<run5:decision_rev>` with the assessment.
Recall, readiness, faults and decode time remain distinct evidence: a readiness
improvement alone does not establish a decode speedup.
