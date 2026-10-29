# Research nodes, subnodes and gates

`Tier 2 · Part of: [Pipeline](README.md)`

The [system overview](../1-system.md) gives the whole journey. The shared checking pattern is in [Checking](../checking/README.md), execution in [Workflow: planning and execution](../platform/planning-and-freeze.md#tasks-nodes-and-verification) and per-CC contracts in [capsule build references](../reference/capsules/README.md).

## The node pattern

Every research node follows diagram D of the [system overview](../1-system.md#inside-a-node). Each M1 research node holds one work subnode. A **work subnode** is one work CC plus its checks.

1. The work CC writes its outputs. Each output is a candidate until the gate accepts it.
2. The check bundle runs once over all outputs of the work subnode.
3. If any mandatory check fails, no verifier runs for any output. The gate host writes one halting decision.
4. Otherwise one verifier CC call runs per output. Its input is the pinned declaration and that exact output only. It assesses declared-output conformance and internal consistency. It has no input replay, no edits and no acceptance authority. The host validates the assessment schema and the exact subject identity.
5. The gate host writes one gate decision per output. `output_port` names the reviewed port.
6. The node gate advances only when every decision advances. The outputs are stored durably, then released to the next nodes.

A halt keeps the candidate and its evidence. The failed node and every node that depends on it stop. Independent nodes continue ([D49](../method/decisions.md#d49)). Inputs arrive as accepted artifacts from earlier nodes or as protected host records.

## What is specific to each node

| Node | Accepted outputs (one gate decision each) | Unique facts | Contract page |
|---|---|---|---|
| Search | `candidate_set` | Fixed query strategy over local extracted documents and permitted academic sources. Keeps exact excerpts and citations. 1 to 3 grounded ideas | [Search](../reference/capsules/search.md) |
| Screening | `screening_result`, `opportunity_card` | One pass. Scores novelty, feasibility and compute alignment from 1 to 5. Filters forbidden dependencies. Selects one Top-1 opportunity under a fixed tie and missing-score policy. Reads a pinned `screening_rubric` | [Screening](../reference/capsules/screening.md) |
| Hypothesis | `hypothesis_blueprint` | One testable claim. Freezes mechanism, variables, baseline, fixed measures, thresholds and the middle-region rule before any code exists. Baseline and validation resources arrive as protected resource snapshots | [Hypothesis](../reference/capsules/hypothesis.md) |
| Builder | `poc_manifest`, `poc_artifact_bundle` | Packages a bounded intervention. Runs no trial and installs no dependency. Checks syntax, forbidden modules, pinned dependencies and output format. Benchmark becomes ready only after the Builder node gate advanced | [Builder](../reference/capsules/builder.md) |
| Research Benchmark | `benchmark_payload`, `execution_receipt`, `provisioning_receipt` | A `tool` CC. Provisions frozen dependencies, then runs baseline first and treatment second on the same data and settings. Does not interpret results. Not the platform benchmark. The Builder `build_receipt` arrives as a host record | [Research Benchmark](../reference/capsules/research-benchmark.md) |
| Scientific Evaluation | `evaluation_verdict` | Applies pre-registered criteria. Checks empirical origin, metric completeness and validity. A scientific negative is a research result, not a gate failure | [Scientific Evaluation](../reference/capsules/scientific-evaluation.md) |
| Delivery | `delivery_manifest`, `research_report` | The leaf node, exactly one per M1 plan. Reads every accepted artifact plus host records such as `gate_decision_index`. Checks report structure, evidence links, reference hashes and verdict agreement | [Delivery](../reference/capsules/delivery.md) |
